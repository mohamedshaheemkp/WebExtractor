from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import aiohttp
from rich.console import Console

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.components import ComponentAnalyzer
from webextractor.analysis.framework import FrameworkDetector
from webextractor.analysis.interactions import InteractionAnalyzer
from webextractor.analysis.routes import RouteAnalyzer
from webextractor.assets import AssetDiscovery, AssetDownloader, AssetOrganizer
from webextractor.capture.crawler import WebsiteCrawler
from webextractor.config import config
from webextractor.generator.project import ReactProjectGenerator
from webextractor.har.normalizer import HARNormalizer
from webextractor.har.parser import HARParser
from webextractor.model.asset import Asset
from webextractor.model.route import Route
from webextractor.model.site_ir import SiteIR
from webextractor.verification.report import VerificationReport
from webextractor.verification.visual_diff import VisualDiffScorer

console = Console(legacy_windows=False)


async def execute_rip(target: str, output_dir: Path | None = None) -> None:
    is_url = target.startswith("http://") or target.startswith("https://")
    target_path = Path(target) if not is_url else None

    # Derive Project / Site Name
    if is_url:
        parsed_url = urlparse(target)
        site_name = parsed_url.netloc.replace(".", "-").replace(":", "-")
    else:
        site_name = target_path.stem if target_path else "website"

    dest_dir = output_dir if output_dir else Path("./output") / site_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    console.print("\n[bold cyan]WebExtractor — Deep Reverse Engineering Engine[/bold cyan]")
    console.print("────────────────────────────────────────────\n")

    html_content = ""
    css_contents: list[str] = []
    js_contents: list[str] = []
    assets: list[Asset] = []
    routes: list[Route] = [Route(path="/", url=target, name="Home")]
    interactions = []
    capture: dict[str, Any] = {}
    entries: list[dict[str, Any]] = []

    # [1/6] INGESTION & EVIDENCE CAPTURE
    if is_url:
        console.print("[bold cyan][1/6] Launching browser & capturing site[/bold cyan]")
        try:
            crawler = WebsiteCrawler(dest_dir / "capture")
            capture = await crawler.crawl(target)
            console.print("      [green]✓[/green] Browser snapshot captured")

            html_content = capture.get("html", "")
            routes = RouteAnalyzer.analyze_routes(html_content, site_name)
            console.print(f"      [green]✓[/green] {len(routes)} routes discovered")
            console.print(f"      [green]✓[/green] {len(capture.get('requests', []))} network requests recorded")
        except Exception as e:
            console.print(f"      [yellow]Browser capture notice:[/yellow] {e}")
            console.print("      Falling back to direct HTTP ingestion...")
            try:
                headers = {"User-Agent": config.user_agent}
                timeout = aiohttp.ClientTimeout(total=config.timeout)
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(target, timeout=timeout) as resp:
                        html_content = await resp.text()
                        capture = {
                            "url": target,
                            "html": html_content,
                            "dom": None,
                            "requests": [{"url": target, "method": "GET", "resource_type": "document"}],
                            "viewports": {},
                        }
                        routes = RouteAnalyzer.analyze_routes(html_content, site_name)
                        console.print("      [green]✓[/green] Direct HTTP capture successful")
            except Exception as fallback_err:
                console.print(f"      [bold red]HTTP fallback failed:[/bold red] {fallback_err}")
                return
    elif not is_url and target_path and target_path.exists():
        console.print(f"[bold cyan][1/6] Loading archive:[/bold cyan] {target_path.name}")
        parser = HARParser(target_path)
        entries = parser.get_entries()
        console.print(f"      [green]✓[/green] Ingested {len(entries)} HAR entries")
    else:
        console.print(f"[bold red]Error:[/bold red] Target not found or invalid: {target}")
        return

    # [2/6] UNIFIED ASSET DISCOVERY
    console.print("\n[bold cyan][2/6] Discovering resources & assets[/bold cyan]")
    if is_url or capture:
        assets = AssetDiscovery.from_crawler(capture, base_url=target)
    elif entries:
        assets = AssetDiscovery.from_har(entries)

    console.print(f"      [green]✓[/green] {len(assets)} canonical assets discovered")

    # [3/6] DOWNLOADING & ORGANIZING ASSETS INTO public/
    console.print("\n[bold cyan][3/6] Downloading & organizing assets into public/[/bold cyan]")
    raw_cache_dir = dest_dir / ".cache" / "raw_assets"
    raw_cache_dir.mkdir(parents=True, exist_ok=True)
    downloader = AssetDownloader(output_dir=raw_cache_dir, workers=config.workers)
    await downloader.download_all(assets, raw_cache_dir)

    manifest = AssetOrganizer.organize_assets(assets, dest_dir)
    downloaded_cnt = sum(1 for a in assets if a.downloaded)
    console.print(f"      [green]✓[/green] {downloaded_cnt}/{len(assets)} assets downloaded and organized into public/")

    # [4/6] ANALYZING INTERFACE & DESIGN SYSTEM
    console.print("\n[bold cyan][4/6] Analyzing interface & design system[/bold cyan]")
    framework = FrameworkDetector.detect(assets, html_content)
    components = ComponentAnalyzer.analyze_components(html_content)

    if not interactions:
        interactions = InteractionAnalyzer.analyze_interactions(
            "\n".join(css_contents),
            "\n".join(js_contents),
        )

    console.print(f"      [green]✓[/green] Framework: [bold]{framework}[/bold]")
    console.print(f"      [green]✓[/green] {len(components)} semantic components detected")

    # [5/6] COMPILING CANONICAL SITE IR WITH AUTHORITATIVE BINDINGS
    console.print("\n[bold cyan][5/6] Compiling canonical Site IR[/bold cyan]")
    if not capture:
        capture = {
            "url": target,
            "html": html_content,
            "dom": {"tag": "body", "children": []},
            "viewports": {},
            "requests": [],
            "css": "\n".join(css_contents),
        }

    analyzer = SiteAnalyzer()
    site_model = analyzer.analyze(capture, assets=assets, asset_manifest=manifest)

    site_ir = SiteIR(
        metadata={
            "url": site_model.url,
            "title": site_model.title,
            "viewport_count": len(getattr(site_model, "viewports", {})),
        },
        routes=site_model.routes,
        design_system=getattr(site_model, "design_system", {}),
        responsive_rules=getattr(site_model, "responsive_rules", []),
        pages=getattr(site_model, "pages", []),
        reusable_components=getattr(site_model, "reusable_components", []),
        component_styles=getattr(site_model, "component_styles", {}),
        data=getattr(site_model, "data", {}),
        components=site_model.components,
        assets=manifest,
        asset_bindings=getattr(site_model, "asset_bindings", []),
        typography=getattr(site_model, "typography", {}),
        layout=getattr(site_model, "layout", {}),
        raw_tokens=site_model.tokens,
    )

    site_ir.save(dest_dir / "analysis")
    num_components = len(site_ir.pages[0].get("components", [])) if site_ir.pages else len(components)
    console.print(f"      [green]✓[/green] Semantic component hierarchy compiled ({num_components} components)")
    console.print(f"      [green]✓[/green] Route graph constructed ({len(site_ir.routes)} routes)")
    console.print(f"      [green]✓[/green] {len(site_ir.asset_bindings)} authoritative asset bindings established")
    console.print("      [green]✓[/green] Canonical SiteIR persisted to analysis/")

    # [6/6] GENERATING REACT & NEXT.JS AND VERIFYING INTEGRITY
    console.print("\n[bold cyan][6/6] Generating React & Next.js App Router[/bold cyan]")
    generator = ReactProjectGenerator(site_ir, dest_dir)
    generated_path = generator.generate()
    console.print("      [green]✓[/green] TypeScript + Tailwind CSS configured")
    console.print("      [green]✓[/green] App Router (app/layout.tsx, app/page.tsx, sub-routes)")
    console.print(f"      [green]✓[/green] Reusable components placed in components/")
    console.print("      [green]✓[/green] Design-system tokens placed in styles/tokens.css")

    # Verification & Artifact Integrity Audit
    public_files = [f for f in (dest_dir / "public").rglob("*") if f.is_file()]
    colors_count = len(site_ir.design_system.get("colors", {}))
    similarity = VisualDiffScorer.calculate_score(
        components_count=num_components,
        downloaded_assets=downloaded_cnt,
        total_assets=len(assets) if assets else 1,
        tokens_count=colors_count,
    )
    VerificationReport.write_report(
        dest_dir / "analysis",
        similarity_score=similarity,
        components_count=num_components,
        assets_count=len(assets),
        tokens_count=colors_count,
    )

    console.print("\n[bold cyan]Artifact Integrity Audit:[/bold cyan]")
    console.print(f"      • Public files physically present: [bold]{len(public_files)}[/bold]")
    console.print(f"      • Assets downloaded: [bold]{downloaded_cnt}/{len(assets)}[/bold]")
    console.print(f"      • Component count: [bold]{num_components}[/bold]")
    console.print(f"      • Structural similarity heuristic: [bold]{similarity}%[/bold]")

    console.print("\n[bold green]Project generated successfully![/bold green]")
    console.print(f"  [cyan]{generated_path.resolve()}[/cyan]\n")
    console.print("[bold]Next steps to run the reconstructed site:[/bold]")
    console.print(f"  cd {dest_dir}")
    console.print("  npm install")
    console.print("  npm run dev\n")
