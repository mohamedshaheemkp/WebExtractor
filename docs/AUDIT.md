# WebExtractor Architecture & Generalization Audit

## Executive Summary
1. **Current State**: WebExtractor is an advanced hybrid scraper/generator that successfully captures 15 routes, 448 assets, and achieves 93.9% fidelity on Framer sites, but possesses deep site-specific coupling that breaks non-Framer sites.
2. **Coupling Reality**: Hardcoded Framer selectors (`.framer-zecFa`, `data-framer-*`), Framer-only SPA manifest regexes, synthetic portfolio fallbacks, and hardcoded coordinates/social links exist across capture, analysis, and generation.
3. **Dual/Dead Code**: Duplicate downloaders (`downloader/download.py` vs `assets/downloader.py`), dead state explorers (`capture/states.py`), and an orphaned generator (`generator/nextjs.py`) fragment the architecture.
4. **Capture Deficits**: No HTTP Archive (HAR) recording during live crawls, no response body persistence, and subpage viewports/behaviors are completely unprobed (only desktop homepage is multi-viewport and behaviorally probed).
5. **Discovery Deficits**: Route discovery relies on static HTML `<a>` tags and Framer bundle scanning; zero support exists for `sitemap.xml`, standard SPA route manifests (Next.js, Nuxt, Remix), or paginated/tabbed views.
6. **Interaction Deficits**: `BehaviorProbe` is restricted to 12 elements on the homepage; forms, dialogs, accordions, tabs, and drag/hover micro-interactions are either mocked or uncaptured.
7. **IR Deficits**: `SiteIR` stores routes as flat strings, lacks per-route asset scopes, cannot represent component-level responsive rules or multi-step animations, and suffers from an un-reconciled dual animation model.
8. **Generator Deficits**: Synthesizes custom components with hardcoded project markup and lacks standard Next.js conventions (`generateStaticParams`, Next `Metadata` API, `next/font`, image optimization).
9. **Porto Root Cause**: Traced to `analysis/animations.py:43-55` and `generator/project.py:1145-1267`, where `StandardCssMotionAdapter` and `FramerMotionAdapter` simultaneously attach conflicting WAAPI animations to the same targets without deduplication.
10. **Generalization Path**: Decouple framework logic into swappable adapters, unify capture around Playwright HAR recording, upgrade SiteIR to v2, implement multi-route AST diffing, and introduce an automated repair loop.
11. **Verification Status**: 158 tests passing (100%), but 0% integration coverage on non-Framer sites (WordPress, Webflow, Shopify, Next.js).
12. **Scope Constraint**: Read-only audit; zero implementation changes applied until approved.

---

## 1. Current Architecture & Data Flow

### 1.1 Module Inventory & Data Flow
The current system follows a linear 6-stage pipeline orchestrated by `src/webextractor/cli/commands/rip.py:30`:

```
Target (URL / HAR)
  │
  ├─ [1/6] Ingestion & Evidence Capture ──► WebsiteCrawler (capture/crawler.py:77)
  │                                         └─ BrowserCapture (capture/browser.py:41)
  │                                         └─ MultiViewportCapture (capture/multi_viewport.py:164)
  │                                         └─ BehaviorProbe (capture/behavior.py:174)
  │
  ├─ [2/6] Unified Asset Discovery ──────► AssetDiscovery (assets/discovery.py:23)
  │
  ├─ [3/6] Download & Organization ──────► AssetDownloader (assets/downloader.py:16)
  │                                         └─ AssetOrganizer (assets/organizer.py:17)
  │
  ├─ [4/6] Interface & Design System ────► FrameworkDetector (analysis/framework.py:7)
  │                                         └─ ComponentAnalyzer (analysis/components.py:9)
  │                                         └─ InteractionAnalyzer (analysis/interactions.py:15)
  │
  ├─ [5/6] Canonical Site IR Compilation ─► SiteAnalyzer (analysis/analyzer.py:23)
  │                                         └─ SiteIR (model/site_ir.py:10)
  │
  └─ [6/6] Generation & Audit ───────────► ReactProjectGenerator (generator/project.py:44)
                                            └─ DomToJsxEmitter (generator/dom_emitter.py:119)
                                            └─ StaticProjectGenerator (generator/static.py:17)
                                            └─ VisualDiffScorer (verification/visual_diff.py:329)
```

- **Entry Points** [VERIFIED]:
  - `src/webextractor/cli/main.py:108`: Primary CLI dispatching `rip`, `extract`, and `inspect`.
  - `src/webextractor/cli/commands/rip.py:30`: Authoritative end-to-end extraction and generation pipeline.
  - `src/webextractor/__main__.py:4`: Package entry point invoking `cli.main.main()`.

### 1.2 Dead & Duplicate Code
- **Duplicate Downloader Stack** [VERIFIED]:
  - `src/webextractor/downloader/download.py:15` (`AssetDownloader`) vs `src/webextractor/assets/downloader.py:16` (`AssetDownloader`).
  - `src/webextractor/downloader/concurrency.py:9` (`ConcurrencyManager`) vs `src/webextractor/assets/concurrency.py:8` (`ConcurrencyManager`).
  - `src/webextractor/downloader/reports.py:11` is only imported by `src/webextractor/cli/commands/extract.py:9`, while `rip.py` uses `assets/organizer.py`.
- **Orphaned Next.js Generator** [VERIFIED]:
  - `src/webextractor/generator/nextjs.py:11` (`NextJSGenerator`): Defines an older Pages-Router-style generator taking `SiteModel`. It is imported only in `generator/__init__.py:3` and never called anywhere in the active pipeline (`rip.py` calls `generator/project.py:215`).
- **Dead State Explorer** [VERIFIED]:
  - `src/webextractor/capture/states.py:7` (`StateExplorer`): Implements `discover_interactions()` which synthesizes dummy selectors like `button:nth-of-type(1)`. It is imported nowhere in `src/` or `tests/`.
- **Dual Representation Models** [VERIFIED]:
  - `src/webextractor/analysis/site.py:12` (`SiteModel`): Intermediate struct returned by `SiteAnalyzer.analyze()`.
  - `src/webextractor/model/site_ir.py:10` (`SiteIR`): Dataclass serialized to disk. `rip.py:171-193` manually maps fields between them with repetitive `getattr()` calls.

---

## 2. Framer & Site-Specific Coupling

The codebase contains extensive hardcoded assumptions targeting Framer architectures and the `glad-service` reference site:

### 2.1 Hardcoded Selectors & Class Names [VERIFIED]
- `src/webextractor/capture/browser.py:285`: Hamburger probe hardcodes `.framer-zecFa`.
- `src/webextractor/generator/project.py:2020`: Navigation overlay event listener hardcodes `target.closest(".framer-zecFa, [data-framer-name='Menu']...")`.
- `src/webextractor/capture/behavior.py:112`: Excludes editor bars using `/__framer-(editor|badge)/i`.
- `src/webextractor/capture/behavior.py:127, 155, 241, 418`: Generates selectors targeting `[data-framer-name]`.
- `src/webextractor/capture/multi_viewport.py:82, 164, 387-401`: Extracts and matches responsive diffs using `data-framer-name` and `data-framer-appear-id`.
- `src/webextractor/analysis/analyzer.py:429, 538, 559, 576`: Animates elements by targeting `data-framer-appear-id`.
- `src/webextractor/generator/dom_emitter.py:289, 395, 451`: Extracts component names and motion IDs from `data-framer-name` and `data-framer-appear-id`.
- `src/webextractor/generator/project.py:1128`: MotionRuntime queries `[data-framer-appear-id="${targetId}"]`.
- `src/webextractor/generator/project.py:1921`: CursorRuntime attaches hover triggers to `[data-framer-cursor]`.

### 2.2 Hardcoded Domains & Framework Checks [VERIFIED]
- `src/webextractor/analysis/framework.py:12-18`: Detects Framer by checking `framerusercontent.com`, `events.framer.com`, `framer.app`, `__framer__`, `framercms`.
- `src/webextractor/analysis/motion_adapters/framer.py:21-24`: Activates Framer motion adapter whenever `"framer" in html.lower()` or `"data-framer-" in html`.
- `src/webextractor/capture/browser.py:257`: SPA router discovery restricts script bundle evaluation to `s.includes('script_main') || s.includes('framer') || s.includes('routes')`.
- `src/webextractor/generator/project.py:2882`: Verification invariant hardcodes regex `https?://[^\s"'\\)>]*framerusercontent\.com`.

### 2.3 Hardcoded Site Content & Components [VERIFIED]
- `src/webextractor/generator/project.py:2042`: Hardcodes geographic coordinates `LOCAL/ 46° 28' 58.6272" N` into the generated `NavigationOverlay.tsx`.
- `src/webextractor/generator/project.py:2060`: Hardcodes `©2024 All RIGHTS Reserved` into `NavigationOverlay.tsx`.
- `src/webextractor/generator/project.py:2075-2083`: Hardcodes specific social links:
  - `https://www.instagram.com/`
  - `https://dribbble.com/`
  - `https://x.com/MandroDesign`
- `src/webextractor/generator/project.py:1921`: Hardcodes project routes `a[href*='/work/']`, `a[href*='/motion/']` and hover badge text `"VIEW"` directly into `CursorRuntime.tsx`.

---

## 3. Capture Architecture: Current vs Missing

### 3.1 What is Captured Today [VERIFIED]
- **Rendered DOM**: Full DOM tree serialized to JSON via `capture/dom.py:10` with tags, computed styles, text, attributes, and bounding client rects.
- **HTML**: Outer HTML post-hydration captured via `page.content()` (`capture/browser.py:215`).
- **CSS**: Inline `<style>` content and readable `document.styleSheets[].cssRules` (`capture/browser.py:190-211`).
- **Screenshots**: Full-page screenshots via `page.screenshot(full_page=True)` (`capture/browser.py:224`).
- **Network Metadata**: Basic request logging via `page.on("request")` recording `url`, `method`, and `resource_type` (`capture/browser.py:67-75`).
- **Scroll Reveal Signals**: Pre/post scroll diffing recording opacity and transform deltas (`capture/browser.py:90-185`).
- **Responsive Viewports**: Multi-viewport screenshots (375, 768, 1024, 1440, 1920) captured on the root homepage (`capture/crawler.py:163-167`).

### 3.2 What is Missing [VERIFIED]
1. **No HAR Recording**: Live Playwright sessions do not record an HTTP Archive (`.har`). Request headers, response headers, HTTP status codes, cookies, timing metrics, and response bodies are discarded.
2. **Subpage Viewport Blindness**: Viewports other than desktop are captured ONLY on the homepage (`capture/crawler.py:162-167`). All subpages (`/work`, `/contact`, etc.) are captured strictly at desktop resolution.
3. **Subpage Interaction Blindness**: `BehaviorProbe` is executed exclusively on `root_url` (`capture/crawler.py:170-179`). Subpage interactive controls (modals, accordions, filters) are ignored.
4. **CORS Stylesheet Loss**: `capture/browser.py:205` catches cross-origin stylesheet errors and silently skips them (`catch (e) {}`), discarding critical external stylesheets.
5. **Dynamic API Responses**: Network response payloads (JSON REST/GraphQL endpoints) are not captured or mapped to component data.

### 3.3 Where `record_har_path` Plugs In [VERIFIED]
In `src/webextractor/capture/browser.py:45-51`, `self.browser.new_context()` currently passes only viewport and device scale factor. Playwright natively supports HAR recording at context initialization:
```python
# src/webextractor/capture/browser.py:45
self.context = await self.browser.new_context(
    viewport={"width": self.viewport_width, "height": self.viewport_height},
    device_scale_factor=1,
    record_har_path=str(self.har_output_path),
    record_har_content="embed",
    record_har_mode="full",
)
```
When `await self.context.close()` executes (`browser.py:560`), Playwright automatically writes the complete W3C-compliant HAR file.

---

## 4. Route & State Discovery

### 4.1 Route Discovery Mechanisms [VERIFIED]
- **Static Anchors**: `src/webextractor/analysis/routes.py:30-58` parses `soup.find_all("a")` from initial HTML. Fails on links mounted client-side after hydration.
- **Framer Script Regex**: `src/webextractor/capture/browser.py:251-274` downloads scripts containing `script_main` or `framer` and runs regex `/path:\s*[`"'](\/[^`"']*)['"`]/g`. Fails on all non-Framer SPA bundles.
- **Dynamic Menu Probe**: `src/webextractor/capture/browser.py:284-310` clicks the first visible trigger matching `.framer-zecFa, button[aria-label*='menu']` and extracts mounted `<a>` tags.
- **Crawler Loop**: `src/webextractor/capture/crawler.py:125-156` maintains a FIFO queue up to `max_routes=50` and `max_depth=3`.

### 4.2 Why Routes Are Missed [VERIFIED]
1. **Zero Sitemap / Robots Parsing**: WebExtractor never requests `/sitemap.xml`, `/sitemap_index.xml`, or `/robots.txt`.
2. **Framework-Specific Manifest Omission**: No parser exists for:
   - Next.js: `/_next/static/<buildId>/_buildManifest.js` and `_ssgManifest.js`.
   - Nuxt: `/_nuxt/manifest.json`.
   - Webflow: inline JSON page maps.
   - Remix / React Router: `window.__remixManifest` or `window.__reactRouterManifest`.
3. **Interaction-Locked Routes**:
   - Tabbed interfaces (`<button role="tab">`) that render view-specific content.
   - Pagination buttons (`<button class="next">`, "Load More") are never clicked in a loop.
   - Infinite scroll triggers are not scrolled to exhaustion.
   - Dropdown menus requiring hover or multi-step click sequences are skipped.

---

## 5. State & Behavioral Interaction Capture

### 5.1 Current Capabilities [VERIFIED]
- `src/webextractor/capture/behavior.py:19-94` (`BehaviorProbe.probe_page`):
  - Gathers up to 12 candidate elements matching buttons, links, `[role="button"]`, `details`.
  - Captures DOM snapshot before click (`behavior.py:36`).
  - Dispatches click event via `_safe_click` (`behavior.py:42`).
  - Waits `settle_time_ms=400` (`behavior.py:46`).
  - Captures DOM snapshot after click and diffs attributes/nodes (`behavior.py:49-52`).
  - Clicks again to detect toggleability (`behavior.py:56-60`).
  - Falls back to hover probe if click produces zero DOM change (`behavior.py:75-88`).
  - Detects continuous horizontal marquee motion by measuring `scrollLeft` progression over 600ms (`behavior.py:450-475`).

### 5.2 Missing Capabilities [VERIFIED]
1. **Forms**: Inputs (`<input>`, `<select>`, `<textarea>`) are never focused, typed into, or submitted. Validation states, error tooltips, and success messages are completely uncaptured.
2. **Modal Portals**: Modals rendered into `document.body` via React Portals or `<dialog>` elements are not tracked back to their triggering button. Backdrop scroll locks (`body { overflow: hidden }`) are not captured.
3. **Hover Menus**: CSS `:hover` dropdowns (`li:hover > ul`) that do not use JavaScript are not detected because `BehaviorProbe` only inspects DOM mutations, not CSS computed style changes on descendants.
4. **Drag & Slider Controls**: Carousels, range sliders, and draggable elements (`[draggable]`, Swiper, Slick) have no drag/swipe gesture emulation.
5. **State Reconciliation**: Captured interactions are emitted into `SiteIR.interactions` as loose trigger-action pairs (`model/interaction.py:10`), but are not compiled into state machine definitions (e.g. `isOpen`, `activeTab`, `currentStep`).

---

## 6. Intermediate Representation (IR) Schema

### 6.1 Current Schema Limitations [VERIFIED]
From `src/webextractor/model/site_ir.py:9-34`:
```python
@dataclass
class SiteIR:
  metadata: dict[str, Any]
  routes: list[str]  # Limitation 1: Flat string array
  design_system: dict[str, Any]
  responsive_rules: list[dict[str, Any]]
  pages: list[dict[str, Any]]  # Limitation 2: Loosely typed dicts
  reusable_components: list[dict[str, Any]]
  component_styles: dict[str, dict[str, Any]]
  data: dict[str, Any]
  components: dict[str, Any] | None
  assets: list[dict[str, Any]]  # Limitation 3: Flat global manifest
  asset_bindings: list[dict[str, Any]]
  typography: dict[str, Any]
  layout: dict[str, Any]
  raw_tokens: dict[str, Any] | None
  screenshot_paths: dict[str, str]
  animations: dict[str, Any]  # Limitation 4: Framer appear_animations bias
  interactions: list[dict[str, Any]]
  overlay: dict[str, Any] | None  # Limitation 5: Single ad-hoc overlay
```

1. **Routes**: Cannot represent route-level metadata (title, meta description, OpenGraph tags, canonical URLs, HTTP status codes, or parameterized segments like `/blog/[slug]`).
2. **Per-Route Asset Scoping**: Assets are globally pooled. There is no mapping of which assets are required for initial render of a given route versus deferred.
3. **Responsive Rules**: Represented as raw selector diff dictionaries detached from component nodes, requiring runtime query-selector matching rather than clean responsive CSS classes or Tailwind variants.
4. **Dual Animation Conflict**: Animations are split between `animations["appear_animations"]` (Framer-biased dictionary) and `animations["motion_triggers"]` (generic list), leading to duplicate execution in generators.
5. **State Representation**: No formal state graph. Dynamic UI states (open/closed, active tab index, expanded accordion item) cannot be expressed declaratively.

### 6.2 Proposed Universal IR Schema (SiteIR v2) [PROPOSED]
```typescript
interface SiteIRv2 {
  schemaVersion: "2.0.0";
  site: {
    origin: string;
    generator: string; // detected framework: Next, Webflow, Shopify, Framer, Generic
    title: string;
    lang: string;
    favicon?: string;
  };
  designTokens: {
    colors: Record<string, string>;
    typography: {
      fonts: Array<{ family: string; src: string; weight: number; style: string; localPath?: string }>;
      scale: Record<string, { fontSize: string; lineHeight: string; letterSpacing: string }>;
    };
    spacing: Record<string, string>;
    shadows: Record<string, string>;
    radii: Record<string, string>;
    transitions: Record<string, { duration: number; easing: string }>;
  };
  routes: Array<{
    path: string; // e.g. "/work/[slug]" or "/about"
    isDynamic: boolean;
    pattern?: string;
    params?: string[];
    statusCode: number;
    metadata: {
      title: string;
      description?: string;
      canonical?: string;
      openGraph?: Record<string, string>;
    };
    pageComponentId: string;
    assets: string[]; // Asset IDs scoped to this route
  }>;
  components: Record<string, {
    id: string;
    name: string;
    semanticTag: string;
    isShared: boolean; // used across multiple routes
    ast: DOMNodeAST;
    states: Record<string, { // e.g. "default", "hover", "open", "active"
      styleOverrides: Record<string, string>;
      domMutations?: Array<{ targetNodeId: string; action: "mount" | "unmount" | "attribute"; value: any }>;
    }>;
    responsiveRules: Record<string, Record<string, string>>; // breakpoint -> CSS property map
    animations: Array<{
      type: "reveal" | "marquee" | "parallax" | "spring" | "transition";
      trigger: "mount" | "scroll" | "hover" | "view";
      properties: Record<string, any>;
      timing: { duration: number; delay: number; easing: string };
    }>;
  }>;
  assets: Record<string, {
    id: string;
    originalUrl: string;
    localPath: string;
    publicUrl: string;
    mimeType: string;
    category: "image" | "font" | "video" | "audio" | "document" | "icon" | "script" | "style";
    contentHash: string; // SHA-256
    byteSize: number;
    variants?: Array<{ width: number; height?: number; localPath: string; url: string }>;
  }>;
  harPath?: string; // Reference to captured raw HAR
}
```

---

## 7. Asset Pipeline: Localization & Deduplication

### 7.1 Current Binding & Resolution Scope [VERIFIED]
- **Binding Scope**: Following Phase 2 improvements (`assets/binding.py:85-170`), `AssetBindingEngine.bind()` traverses DOM trees across all captured routes and overlays.
- **Resolution Hierarchy**: `generator/dom_emitter.py:770-858` resolves asset references through `asset_bindings` → `_asset_lookup` → `_clean_asset_lookup` → `_filename_lookup` → `_base_filename_lookup` → external URL.
- **Downloaded Protection**: `dom_emitter.py:840` ensures that if an asset is downloaded locally, its remote URL is never emitted.

### 7.2 Deficits & Failure Modes [VERIFIED]
1. **Remote Font Leaks**: External fonts defined in `@font-face` rules (`https://framerusercontent.com/assets/*.woff2` or Google Fonts) that are not requested during headless crawling remain pointing to remote CDNs (`generator/project.py:2881-2900`).
2. **No Perceptual / Hash Deduplication**: `assets/organizer.py:105-127` relies on URL query-string parsing (`@1080`) and filename hashing (`hash(asset.url)`). If two different URLs return identical binary files, both are downloaded and stored.
3. **CSS Nested Asset Blindness**: External stylesheets referenced via `<link rel="stylesheet">` are downloaded as static text, but `url(...)` declarations inside them (custom fonts, SVG masks, cursor icons) are not parsed, localized, or rewritten.
4. **MIME Type Authoritativeness Gap**: `assets/organizer.py:47` splits MIME type on `;`, but `AssetDiscovery.from_crawler` (`assets/discovery.py:41`) derives types from Playwright request `resource_type` before responses are inspected, leading to classification errors when CDNs serve generic `application/octet-stream`.

---

## 8. Code Generator: Reconstruction vs Synthesis

### 8.1 Points of Synthetic Fabrication [VERIFIED]
1. **Fallback Project Cards**: `src/webextractor/generator/project.py:2435-2475`: If `/work` is not matched in `pages`, it emits synthetic cards with hardcoded styles (`background: rgba(255,255,255,0.04)`).
2. **Dynamic Work Case Study**: `src/webextractor/generator/project.py:2505-2545`: `_write_work_dynamic_page` generates a hardcoded case-study template with generic typography and mock layout.
3. **Hardcoded Navigation Overlay**: `src/webextractor/generator/project.py:2009-2090`: Emits Glad-Service-specific text, coordinates, and social media links instead of rendering purely from `capture["overlay"]`.
4. **Hardcoded Cursor Runtime**: `src/webextractor/generator/project.py:1870-1960`: Embeds cursor expansion specifically tied to `[data-framer-cursor]` and `"VIEW"` badges.

### 8.2 Next.js Output Gaps [VERIFIED]
- **No `generateStaticParams`**: Emitted dynamic routes in `app/work/[slug]/page.tsx` lack `generateStaticParams()`. Running `next build` with `output: 'export'` fails immediately.
- **No Next.js Metadata API**: Layout and pages lack `export const metadata: Metadata = { ... }`. Page titles and OpenGraph tags are omitted or hardcoded into layout strings.
- **Bypasses `next/image`**: `dom_emitter.py:563` outputs standard HTML `<img>` tags. Next.js image optimization, automatic modern format conversion (AVIF/WebP), and layout shift prevention (`sizes`, blur placeholders) are completely absent.
- **No `next/font` Local Optimization**: Layout relies on standard `<link>` tags or CSS `@font-face` rules rather than `next/font/local` or `next/font/google`, causing visible layout shifts during font loading.
- **No `next.config.js` Setup**: The generated project does not configure image domains (`images.remotePatterns`), asset prefixes, or strict React compiler rules.

---

## 9. Verification & Repair Architecture

### 9.1 What Exists Today [VERIFIED]
- `src/webextractor/verification/visual_diff.py:329-602` (`VisualDiffScorer`):
  - **Asset Verification**: Checks if referenced asset paths physically exist in `public/` (`visual_diff.py:350-376`).
  - **Layout Verification**: Matches expected component names against `components/*.tsx` (`visual_diff.py:381-406`).
  - **Typography Verification**: Checks for `--font-display`, `--color-` in `tokens.css` (`visual_diff.py:411-437`).
  - **Responsive Verification**: Checks for `@media` queries in CSS (`visual_diff.py:442-460`).
  - **Animation Verification**: Verifies presence of `MotionRuntime.tsx` and timing curves (`visual_diff.py:465-504`).
  - **Visual Screenshot Comparison**: Compares full-page screenshots using perceptual pixel buffer diffing and dimension scoring (`visual_diff.py:527-569`).
  - **Component Diff Generator**: Extracts component bounding boxes and calculates region divergence (`visual_diff.py:53-280`).

### 9.2 Critical Verification Gaps [VERIFIED]
1. **Homepage-Only Visual Audit**: Visual screenshot comparison runs ONLY on `index.html` (`rip.py:231-235`). Subpage visual fidelity is completely unmeasured.
2. **Zero Automated Repair**: WebExtractor detects discrepancies and writes reports (`analysis/verification_report.json`), but has ZERO self-healing mechanisms. If a score fails, the pipeline exits without attempting remediation.
3. **No DOM/AST Diffing**: Verification compares flat pixels and string tokens. It does not compute tree edit distances or attribute diffs between source DOM and generated React DOM.
4. **No Route HTTP Audit**: Generated Next.js routes are never started on a test server (`next start`) to verify that all routes return HTTP 200 without hydration errors.

### 9.3 Proposed Numeric Verification Thresholds [PROPOSED]
For automated quality gating before a reconstruction is marked complete:
- **Visual Similarity (SSIM / Pixel)**:
  - Desktop Viewports (1440, 1920): `≥ 90.0%`
  - Tablet Viewport (768): `≥ 85.0%`
  - Mobile Viewport (375): `≥ 85.0%`
  - Component-Level Max Divergence: `≤ 8.0%`
- **Asset Integrity**:
  - Missing Local Asset Files: `0` (100% physically present)
  - Unresolved Image/Video References: `0`
  - Avoidable Remote Asset URLs: `0`
- **DOM Structural Similarity**:
  - Semantic Tag Alignment: `≥ 95.0%`
  - Text Content Preservation: `≥ 98.0%`
- **Route Integrity**:
  - Discovered vs Generated Route Ratio: `100.0%`
  - HTTP 404 / 500 Responses on Generated Routes: `0`
- **Console / Runtime Errors**:
  - React Hydration Mismatch Errors: `0`
  - Uncaught JavaScript Exceptions: `0`

---

## 10. CLI & UX Specifications

### 10.1 Current Commands [VERIFIED]
From `src/webextractor/cli/main.py:22-106`:
- `webextractor rip <target> [-o OUTPUT] [-t {next,html}] [--viewports VIEWPORTS] [--audit]`: Primary command.
- `webextractor extract <har_file> [-o OUTPUT] [-w WORKERS]`: Asset extraction from HAR file only.
- `webextractor inspect <har_file>`: Resource inspection from HAR file only.

### 10.2 Proposed Target CLI [PROPOSED]
```
webextractor clone <url> [options]
  Options:
    -o, --output <dir>          Target directory for reconstructed Next.js project
    --record-har <path>         Record full Playwright HTTP Archive to file
    --framework <engine>        Output format: 'next' (default) or 'html'
    --viewports <list>          Comma-separated viewports (default: 375,768,1024,1440,1920)
    --max-routes <n>            Maximum routes to discover and crawl (default: 50)
    --max-depth <n>             Maximum crawl depth (default: 3)
    --verify                    Execute multi-viewport, multi-route verification audit
    --repair                    Automatically repair detected visual/structural discrepancies
    --headless / --no-headless  Toggle browser UI during capture

webextractor extract <har|url> [options]
  Options:
    -o, --output <dir>          Target directory for downloaded and organized assets
    -w, --workers <n>           Concurrent download workers count

webextractor inspect <har|url> [options]
  Options:
    --json                      Emit machine-readable JSON analysis report
    --routes                    Inspect discovered route tree and SPA manifests
    --assets                    Inspect resource categories and remote domains

webextractor verify <project_dir> [options]
  Options:
    --threshold <score>         Minimum overall fidelity threshold to pass (default: 85.0)
    --viewports <list>          Viewports to audit
    --routes <list>             Specific routes to verify

webextractor repair <project_dir> [options]
  Options:
    --max-iterations <n>        Maximum repair cycles (default: 3)
```

---

## 11. Test Coverage & Non-Framer Fixture Needs

### 11.1 Test Suite Status [VERIFIED]
- **Command**: `pytest tests/ -q`
- **Result**: **158 passed in 5.44s**
- **Test Inventory**: 24 test files covering asset classification, layout heuristics, DOM parsing, timing functions, CLI arguments, and regression suites.

### 11.2 Coverage Gaps & Blind Spots [VERIFIED]
1. **Zero Non-Framer Testing**: 100% of existing tests run against Framer fixtures (`samples/har/porto-rehost-full.har`, Framer JSON scripts, or synthetic unit mocks). Zero test coverage exists for other major CMS/framework sites.
2. **No Live Pipeline Tests**: No automated end-to-end tests validating `webextractor clone` on real external network endpoints or local test servers.
3. **No Dynamic Interaction Tests**: Interactions are tested via mock objects (`test_phase6i_behavioral_interaction.py`), not against real rendered DOM events.

### 11.3 Required Non-Framer Test Fixture Set [PROPOSED]
To qualify WebExtractor as a universal engine, the test suite requires standardized fixtures representing diverse frontend architectures:
1. **Next.js App Router Site**: Fixture testing client-side page transitions, `_next/image`, and `_buildManifest.js` route discovery.
2. **Webflow Commercial Landing Page**: Fixture testing Webflow IX2 animations, dropdown interactions, and Webflow responsive container classes.
3. **Tailwind / Vite Static SPA**: Fixture testing client-side hash/history routing, standard utility classes, and SVG icon sprites.
4. **WordPress / WooCommerce E-commerce Store**: Fixture testing server-rendered HTML, paginated product grids, WooCommerce forms, and multi-level navigation menus.
5. **Shopify Storefront**: Fixture testing product variants, collection filters, and cart drawer interaction states.

---

## 12. Root Cause of Porto Breakage in `test-runs/porto`

### 12.1 Detailed Architectural Failure Path [VERIFIED]
The Porto test run (`samples/har/porto-rehost-full.har`) uncovered a fundamental defect in WebExtractor's animation pipeline:

1. **Unconditional Adapter Activation**:
   - `src/webextractor/analysis/motion_adapters/standard.py:25-27`: `StandardCssMotionAdapter.can_handle()` returns `True` unconditionally for every website.
   - `src/webextractor/analysis/motion_adapters/framer.py:17-24`: `FramerMotionAdapter.can_handle()` returns `True` whenever `"framer"` or `"data-framer-"` is in the HTML.
2. **Duplicate Trigger Generation**:
   - For Porto (a Framer site with CSS transitions), both adapters run simultaneously.
   - `FramerMotionAdapter` extracts appear animations from script tags and emits triggers targeting elements via `[data-framer-appear-id="..."]` (`analysis/motion_adapters/framer.py:107`).
   - `StandardCssMotionAdapter` extracts CSS transition declarations from `<style>` tags and emits triggers targeting the exact same elements via CSS classes or IDs (`analysis/motion_adapters/standard.py:120-145`).
3. **Un-reconciled Trigger Merging**:
   - `src/webextractor/analysis/animations.py:55`:
     ```python
     merged["motion_triggers"].extend(res.get("motion_triggers", []))
     ```
   - While `parallax_elements` and `keyframes` are deduplicated (`animations.py:65-68`), `motion_triggers` are appended with zero cross-adapter reconciliation or target identity matching.
4. **Duplicate Trigger Injection in SiteAnalyzer**:
   - `src/webextractor/analysis/analyzer.py:580`: `_extract_dom_transitions()` appends yet another trigger for every `framer_appear_id` directly into `animations["motion_triggers"]`.
5. **Conflicting Execution in Generated Runtime**:
   - In `src/webextractor/generator/project.py:1145-1267` (`MotionRuntime.tsx`):
     - Loop 1 iterates through `appearMap` and attaches Web Animation API (WAAPI) keyframes: `opacity: 0 -> 1`, `transform: translateY(20px) -> 0`.
     - Loop 2 iterates through `triggers` and attaches a second overlapping WAAPI animation or inline transition to the identical DOM element.
   - **Resulting Symptom**: Elements flicker, jump between conflicting translation offsets, fail to reach 100% opacity, and cause severe visual divergence in layout diffing.

---

## Deliverable A: Capability Gap Matrix

| Capability | Status | Evidence (file:line) | Effort | Risk |
|---|:---:|---|:---:|:---:|
| **HAR Recording during Live Crawl** | Missing | `capture/browser.py:45-51` (no `record_har_path`) | S | Low |
| **Universal Route Discovery (Sitemap/Robots)** | Missing | `analysis/routes.py:30` (HTML `<a>` tags only; zero sitemap code) | S | Low |
| **Non-Framer SPA Manifest Extraction** | Missing | `capture/browser.py:257-262` (Framer regex only) | M | Med |
| **Subpage Multi-Viewport Capture** | Missing | `capture/crawler.py:163-167` (Runs only on `captured_pages[0]`) | M | Low |
| **Subpage Behavioral Interaction Probe** | Missing | `capture/crawler.py:171-179` (Runs only on `root_url`) | M | Med |
| **Animation Trigger Reconciliation (Porto Fix)** | Missing | `analysis/animations.py:55` (unreconciled `.extend()`) | S | Low |
| **Decoupled Framework Motion Adapters** | Partial | `analysis/motion_adapters/` (Framer & Standard exist, Framer leaky) | M | Med |
| **Universal Navigation / Menu Interaction** | Partial | `capture/browser.py:285` (hardcoded `.framer-zecFa`) | M | Med |
| **Form & Input State Capture** | Missing | `capture/behavior.py:19` (click & hover only; no inputs) | L | High |
| **Modal / Dialog State Capture** | Missing | `capture/behavior.py:48-73` (no backdrop/portal tracking) | M | Med |
| **Per-Route Asset Scoping in IR** | Missing | `model/site_ir.py:25` (flat global asset array) | M | Low |
| **Perceptual Asset Deduplication** | Missing | `assets/organizer.py:105-127` (filename hash only; no SHA/dHash) | S | Low |
| **External Font Localization** | Partial | `generator/project.py:2881` (remote woff2 URLs remain) | M | Low |
| **Elimination of Synthetic Content** | Partial | `generator/project.py:2435, 2505` (fallback cards/case-study) | S | Low |
| **Next.js App Router Compliance** | Partial | `generator/project.py:2100` (missing `generateStaticParams`, `Metadata`) | M | Low |
| **Next.js Font & Image Optimization** | Missing | `generator/dom_emitter.py:563` (raw `<img>`, no `next/image` or `next/font`) | M | Med |
| **Multi-Route Visual Verification** | Missing | `cli/commands/rip.py:231` (tests `index.html` only) | M | Low |
| **Automated Verification-Repair Loop** | Missing | `verification/visual_diff.py:329` (reporting only; no repair) | L | High |
| **Unified CLI (`clone`, `verify`, `repair`)** | Missing | `cli/main.py:31` (`rip`, `extract`, `inspect` only) | S | Low |
| **Non-Framer Test Fixtures** | Missing | `tests/` (100% Framer or mock unit tests) | M | Low |

---

## Deliverable B: Target Architecture Diagram

```
                     ┌────────────────────────────────────────┐
                     │          CLI Entry Points              │
                     │  webextractor clone | extract | repair │
                     └───────────────────┬────────────────────┘
                                         │
 ┌───────────────────────────────────────▼────────────────────────────────────────┐
 │                    Universal Capture Engine (Playwright)                       │
 │                                                                                │
 │  ┌─────────────────────────┐  ┌───────────────────────┐  ┌──────────────────┐  │
 │  │ Network & HAR Recording │  │ Multi-Page Crawler    │  │ Multi-Viewport   │  │
 │  │ (playwright record_har) │  │ (HTML + DOM AST)      │  │ (375 to 1920)    │  │
 │  └─────────────────────────┘  └───────────────────────┘  └──────────────────┘  │
 │  ┌──────────────────────────────────────────────────────────────────────────┐  │
 │  │ Active Behavioral Probing Engine                                         │  │
 │  │ (clicks, toggles, accordions, tabs, modals, forms, scroll reveals)       │  │
 │  └──────────────────────────────────────────────────────────────────────────┘  │
 └───────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Raw DOM ASTs, Network HAR, Screenshots
 ┌───────────────────────────────────────▼────────────────────────────────────────┐
 │                     Analysis & Feature Extractor                               │
 │                                                                                │
 │  ┌─────────────────────────┐  ┌─────────────────────────────────────────────┐  │
 │  │ Framework Detector      │  │ Route Discovery Engine                      │  │
 │  │ (Next, Webflow, Shopify)│  │ (Sitemap.xml, SPA Manifests, DOM links)     │  │
 │  └─────────────────────────┘  └─────────────────────────────────────────────┘  │
 │  ┌──────────────────────────────────────────────────────────────────────────┐  │
 │  │ Pluggable Motion & Animation Adapters                                    │  │
 │  │   ┌────────────────────┐ ┌────────────────────┐ ┌─────────────────────┐  │  │
 │  │   │ Standard CSS / WAAPI│ │ GSAP / ScrollTrigger│ │ Framer Motion      │  │  │
 │  │   └────────────────────┘ └────────────────────┘ └─────────────────────┘  │  │
 │  │   └─ Motion Reconciliation & Conflict Arbiter (Prevents Porto Bug)       │  │
 │  └──────────────────────────────────────────────────────────────────────────┘  │
 └───────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Canonical Entities
 ┌───────────────────────────────────────▼────────────────────────────────────────┐
 │                  Canonical Intermediate Representation (SiteIR v2)             │
 │  - Typed Route Graph + Metadata          - Scoped Per-Route Asset Manifest     │
 │  - Component ASTs + Interaction States   - Reconciled Motion Specifications    │
 │  - Global Design Tokens (Colors/Fonts)   - Responsive Rulesets                 │
 └───────────────────┬────────────────────────────────────────────┬───────────────┘
                     │                                            │
 ┌───────────────────▼─────────────────────┐  ┌───────────────────▼───────────────┐
 │ Next.js / React Generator               │  │ Verification & Automated Repair   │
 │                                         │  │                                   │
 │ - App Router (`app/[route]/page.tsx`)   │  │ - Multi-Route Screenshot Diff     │
 │ - Clean JSX (`DomToJsxEmitter`)         │  │ - DOM AST & Computed Style Diff   │
 │ - Next.js Metadata API                  │  │ - Asset & Route Availability Gating│
 │ - Scoped CSS Tokens & Tailwind Config   │  │ - Closed-Loop Repair Dispatcher   │
 └─────────────────────────────────────────┘  └───────────────────────────────────┘
```

---

## Deliverable C: Phased Implementation Roadmap

### Phase 1: Porto Motion Conflict Fix & Adapter Reconciliation
- **Scope**: Eliminate duplicate animation triggers causing the Porto rendering breakdown. Implement strict cross-adapter motion reconciliation before IR compilation.
- **Files Touched**:
  - `src/webextractor/analysis/animations.py`
  - `src/webextractor/analysis/motion_adapters/standard.py`
  - `src/webextractor/analysis/motion_adapters/framer.py`
  - `src/webextractor/analysis/analyzer.py`
  - `src/webextractor/generator/project.py`
- **Dependencies**: None.
- **Acceptance Criteria**:
  - Running extraction on `samples/har/porto-rehost-full.har` produces zero duplicate animation triggers for identical DOM target nodes.
  - Generated `MotionRuntime.tsx` contains no duplicate WAAPI listeners on identical elements.
  - Component divergence on Porto benchmark drops below 5.0%.
- **Test Additions**: `tests/test_porto_motion_reconciliation.py` (asserts mutual exclusivity and target deduplication across adapters).

### Phase 2: Capture Engine Generalization & Live HAR Recording
- **Scope**: Unify capture on Playwright `record_har_path`, capture response headers and bodies, extend multi-viewport and behavioral probing to all crawled subpages.
- **Files Touched**:
  - `src/webextractor/capture/browser.py`
  - `src/webextractor/capture/crawler.py`
  - `src/webextractor/capture/multi_viewport.py`
  - `src/webextractor/capture/behavior.py`
- **Dependencies**: Phase 1.
- **Acceptance Criteria**:
  - Every live extraction produces a complete, valid W3C `.har` archive in `dest/capture/network.har`.
  - Subpages (`/about`, `/contact`) contain responsive screenshots for all 5 viewports in `dest/capture/screenshots/`.
  - Subpage interactions (e.g. contact form, FAQ accordion) are probed and recorded.
- **Test Additions**: `tests/test_live_har_recording.py`, `tests/test_subpage_multi_viewport_capture.py`.

### Phase 3: Universal Route & Dynamic Manifest Discovery
- **Scope**: Eliminate hardcoded Framer script matching. Add automated `sitemap.xml` ingestion and pluggable SPA router manifest parsers for Next.js, Nuxt, and Remix.
- **Files Touched**:
  - `src/webextractor/analysis/routes.py`
  - `src/webextractor/capture/browser.py`
  - `src/webextractor/capture/crawler.py`
  - `src/webextractor/capture/behavior.py`
- **Dependencies**: Phase 2.
- **Acceptance Criteria**:
  - Discovery automatically ingests `/sitemap.xml` and discovers unlinked routes.
  - Next.js build manifests (`_buildManifest.js`) are parsed to discover dynamic route patterns.
  - Dynamic hamburger/menu probe uses semantic ARIA and role queries instead of hardcoded `.framer-zecFa`.
- **Test Additions**: `tests/test_universal_router_discovery.py` (fixtures for Next.js build manifests and sitemap XML).

### Phase 4: Intermediate Representation Upgrade (SiteIR v2) & Decoupling
- **Scope**: Migrate `SiteIR` dataclass to v2 specification. Formalize route metadata, per-route asset scopes, declarative component states, and token clustering. Remove all Framer-specific fields.
- **Files Touched**:
  - `src/webextractor/model/site_ir.py`
  - `src/webextractor/model/route.py`
  - `src/webextractor/analysis/analyzer.py`
  - `src/webextractor/analysis/site.py`
  - `src/webextractor/generator/project.py`
  - `src/webextractor/generator/dom_emitter.py`
- **Dependencies**: Phase 1, Phase 3.
- **Acceptance Criteria**:
  - `SiteIR` serializes cleanly to `site_ir.json` matching the v2 schema with zero `framer` keys.
  - Route objects include page titles, descriptions, and scoped asset IDs.
  - Component models include state overrides for hover and toggle states.
- **Test Additions**: `tests/test_site_ir_v2_schema.py` (schema validation tests).

### Phase 5: Generator Modernization & Elimination of Synthetic Code
- **Scope**: Remove all synthetic fallback templates (`_write_work_dynamic_page`, mock portfolio cards, hardcoded overlay coordinates). Emit standard Next.js App Router conventions (`generateStaticParams`, `Metadata` API, `next/image` option).
- **Files Touched**:
  - `src/webextractor/generator/project.py`
  - `src/webextractor/generator/dom_emitter.py`
  - `src/webextractor/generator/static.py`
- **Dependencies**: Phase 4.
- **Acceptance Criteria**:
  - Zero hardcoded text, coordinates, or social links emitted in generated files.
  - Every dynamic route segment includes a valid `generateStaticParams()` export.
  - Generated project passes `next build` with zero TypeScript or build errors.
- **Test Additions**: `tests/test_generator_zero_synthesis.py`, `tests/test_nextjs_build_compliance.py`.

### Phase 6: Automated Verification & Closed-Loop Repair
- **Scope**: Extend visual diffing to all captured routes. Implement automated discrepancy classification and closed-loop repair dispatching targeted CSS/AST patches until thresholds are met.
- **Files Touched**:
  - `src/webextractor/verification/visual_diff.py`
  - `src/webextractor/verification/report.py`
  - `src/webextractor/cli/commands/rip.py`
  - New module: `src/webextractor/repair/engine.py`
- **Dependencies**: Phase 2, Phase 5.
- **Acceptance Criteria**:
  - Visual verification runs across all discovered routes and all 5 viewports.
  - Repair engine automatically detects and fixes missing CSS styles or unlocalized font URLs up to 3 iterations.
  - Verification fails if any route divergence exceeds the threshold.
- **Test Additions**: `tests/test_multiroute_verification.py`, `tests/test_repair_engine.py`.

### Phase 7: Non-Framer Fixture Suite & CLI Unification
- **Scope**: Add standardized test fixtures for Webflow, Next.js, and WordPress. Implement the unified CLI (`clone`, `verify`, `repair`).
- **Files Touched**:
  - `src/webextractor/cli/main.py`
  - `src/webextractor/cli/commands/rip.py`
  - `tests/fixtures/*`
  - `tests/test_universal_reconstruction.py`
- **Dependencies**: Phases 1–6.
- **Acceptance Criteria**:
  - `webextractor clone <url> --record-har --verify` functions as the single canonical entry point.
  - Full test suite passes across all non-Framer test fixtures with `≥ 85.0%` visual similarity.
- **Test Additions**: Integration tests for Webflow and Next.js sample archives.

---

## 13. Top 10 Technical Risks & Hard Constraints

1. **Bot Detection & Turnstile / Cloudflare Challenges**: Advanced anti-bot protection (Cloudflare Turnstile, Akamai, PerimeterX) blocks headless browser capture. *Hard Boundary: Sites requiring interactive proof-of-work or CAPTCHA cannot be scraped headlessly without authenticated sessions or residential proxy infrastructure.*
2. **Authenticated & Gated State Space**: Pages behind login forms, OAuth, or paywalls. *Hard Boundary: Observable presentation cannot be captured if access is denied.*
3. **WebGL / 3D Canvas Runtimes (Three.js, Spline, Babylon.js)**: 3D scene graphs and shaders cannot be reverse-engineered into editable React components from rendered `<canvas>` pixels. *Hard Boundary: Canvas elements can only be preserved as interactive client-side bundles or fallback video/poster loops.*
4. **Dynamic Server-Side State & Database Logic**: E-commerce checkouts, live inventory, search backends, user authentication, and payment gateways cannot be inferred from frontend observation. *Hard Boundary: Generated Next.js apps are frontends; server-side state machines must be mocked or connected to external headless APIs.*
5. **Personalized / Geolocation-Dependent UI**: Sites that dynamically adapt layout, language, or currency based on IP address or browser headers. *Risk: Captured snapshots reflect only the crawler's IP location and user-agent.*
6. **Obfuscated JavaScript Minification**: Heavily mangled production bundles (Terser/Rollup symbol mangling) make runtime reverse-engineering of custom interactive state trees fragile.
7. **Streaming & DRM Media**: Video/audio content protected by Widevine, FairPlay, or chunked HLS/DASH with expiring tokens cannot be permanently localized into `public/`.
8. **Complex Drag / Multi-Touch Physics**: Physics-based interactive widgets (custom drag carousels, spring canvas simulations) may lose fluid micro-behavior when converted to declarative CSS or standard WAAPI keyframes.
9. **Infinite Route Explosion**: E-commerce sites with millions of filter combinations (`?color=blue&size=m&sort=price`). Without strict crawl limits, the crawler can exhaust memory and disk storage.
10. **Hydration Mismatches in Server Components**: Reconstructed JSX rendered on the server (Next.js SSR) may mismatch client-side browser evaluation if dynamic browser APIs (`window.innerWidth`, `navigator.userAgent`) are evaluated during SSR.
