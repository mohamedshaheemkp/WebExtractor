from __future__ import annotations

from pathlib import Path
from collections import Counter
from urllib.parse import urlparse
from rich.console import Console
from rich.table import Table

from webextractor.analysis.framework import FrameworkDetector
from webextractor.har.entries import HAREntryExtractor
from webextractor.har.normalizer import HARNormalizer
from webextractor.har.parser import HARParser
from webextractor.model.asset import Asset, AssetType

console = Console(legacy_windows=False)


def execute_inspect(har_path: Path) -> None:
    if not har_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {har_path}")
        return

    parser = HARParser(har_path)
    entries = parser.get_entries()

    domains: set[str] = set()
    assets: list[Asset] = []
    api_endpoints: list[str] = []
    html_content = ""

    for entry in entries:
        url = HAREntryExtractor.get_url(entry)
        if not url:
            continue
        clean_url = HARNormalizer.normalize_url(url)
        mime = HAREntryExtractor.get_mime_type(entry)
        asset_type = HARNormalizer.classify_asset_type(clean_url, mime)

        parsed = urlparse(clean_url)
        if parsed.netloc:
            domains.add(parsed.netloc)

        if asset_type == AssetType.HTML and not html_content:
            body = HAREntryExtractor.get_response_body(entry)
            if isinstance(body, str):
                html_content = body

        if asset_type == AssetType.API or "api" in clean_url.lower():
            if clean_url not in api_endpoints:
                api_endpoints.append(clean_url)

        assets.append(
            Asset(
                url=clean_url,
                domain=parsed.netloc,
                asset_type=asset_type,
                mime_type=mime,
            )
        )

    framework = FrameworkDetector.detect(assets, html_content)
    type_counts = Counter(a.asset_type.value for a in assets)

    console.print("\n[bold cyan]WebExtractor — Website Analysis[/bold cyan]")
    console.print("─" * 40)
    console.print(f"[bold]Source:[/bold]    {har_path}")
    console.print(f"[bold]Framework:[/bold] [green]{framework}[/green]")

    console.print("\n[bold]Domains:[/bold]")
    for d in sorted(domains):
        console.print(f"  • {d}")

    console.print("\n[bold]Resources:[/bold]")
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Type", width=16)
    table.add_column("Count", justify="right")
    for res_type, count in sorted(type_counts.items()):
        table.add_row(res_type, str(count))
    console.print(table)

    console.print("[bold]API Endpoints:[/bold]")
    if api_endpoints:
        for ep in api_endpoints[:10]:
            console.print(f"  • {ep}")
    else:
        console.print("  None detected")
    console.print()
