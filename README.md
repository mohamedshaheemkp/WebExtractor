# WebExtractor

> **Deep Website Reverse Engineering, Code Generation & Asset Extraction Engine**

WebExtractor inspects live websites or captured HTTP Archive (`.har`) files, reverse-engineers their architecture, extracts and organizes all digital assets, and generates a modern, production-ready **Next.js (App Router) + TypeScript + Tailwind CSS** project replicating the site's layout, design system, responsive behavior, and components.

---

## Key Features

- **Dual Ingestion Pipelines**:
  - **Live URL Crawling**: Uses Playwright headless Chromium for multi-viewport DOM capture, computed style extraction, scroll/hover interaction recording, and route discovery.
  - **HAR Archive Ingestion**: Offline parsing of HTTP Archives recorded from any modern browser.
- **Deep Design System Extraction**:
  - Automatically identifies typography (font families, weights, scales, Google Fonts).
  - Extracts color palettes, CSS custom properties, spacing scales, and shadow tokens.
  - Detects underlying frontend frameworks (Framer, React, Next.js, Webflow, Squarespace, WordPress, etc.).
- **Semantic Component Reconstruction**:
  - Clusters DOM elements and repeats into clean, reusable React components (`Header`, `Hero`, `Section`, `Footer`, etc.).
  - Reconstructs Flexbox, CSS Grid, and responsive layout rules.
  - Preserves interactive states, navigation graphs, and motion transitions.
- **Canonical Asset Pipeline**:
  - Discovers, downloads, and categorizes images, vectors, videos, fonts, and stylesheets.
  - Rewrites asset references and organizes them cleanly into a standard Next.js `public/` folder hierarchy.
- **Production Code Generation**:
  - Emits modern Next.js App Router structure (`app/layout.tsx`, `app/page.tsx`, sub-routes).
  - TypeScript types and Tailwind CSS configuration with design system tokens (`styles/tokens.css`).
- **Integrity & Verification Audit**:
  - Verifies downloaded assets, component counts, and computes visual/structural similarity scores.

---

## The WebExtractor Formula (System Architecture)

```text
            ANY WEBSITE
                        │
                        ▼
              ┌──────────────────┐
              │ Browser Capture  │
              └────────┬─────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        DOM/CSS      Assets       Runtime
          │            │            │
          └────────────┼────────────┘
                       ▼
                BEHAVIOR ENGINE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Layout       States        Motion
          │            │            │
          └────────────┼────────────┘
                       ▼
                    SITE IR
                       │
                       ▼
                  GENERATORS
                       │
              ┌────────┴────────┐
              ▼                 ▼
           Static            Dynamic
              │                 │
              └────────┬────────┘
                       ▼
                  VERIFICATION
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
       Pixel fidelity       Behavioral fidelity
```

### Formula Breakdown

1. **Browser Capture**:
   - **DOM/CSS**: Multi-viewport DOM trees, computed styles, cascade rules, typography metrics, and bounding geometry.
   - **Assets**: Images, vector SVGs, custom web fonts, video media, and canvas payloads.
   - **Runtime**: Dynamic execution state, active DOM mutations, event listener bindings, and network interactions.
2. **Behavior Engine**:
   - **Layout**: Component hierarchy clustering, Flexbox/Grid flow, container queries, and responsive breakpoint constraints.
   - **States**: Hover, focus, active states, disclosure mechanics (drawers, modals, accordions, tabs), and route transitions.
   - **Motion**: CSS transitions, keyframes, scroll-driven triggers, parallax trajectories, and Framer Motion semantics.
3. **Site IR (Intermediate Representation)**:
   - The single source of truth and data contract decoupling extraction from code generation. Completely structured and schema-validated JSON.
4. **Generators**:
   - **Static**: Zero-dependency HTML, CSS design tokens, localized canonical assets, and responsive typography.
   - **Dynamic**: React / Next.js (App Router), interactive TypeScript components, state stores, and animation runtimes.
5. **Verification**:
   - **Pixel Fidelity**: Multi-viewport visual screenshot diffing against ground truth (pixel-perfect match thresholding).
   - **Behavioral Fidelity**: Automated testing of interactive state transitions, navigation, layout constraints, and motion playback.

---

## Prerequisites

- **Python**: Version `3.10` or higher
- **Node.js**: Version `18.0` or higher (required to run generated Next.js sites)
- **npm** or **pnpm** / **yarn**

---

## Installation

### 1. Clone or Open the Repository
```bash
cd WebExtractor
```

### 2. Create and Activate a Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt (cmd):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install WebExtractor Dependencies
```bash
pip install -e .
```
*(Alternatively: `pip install -r requirements.txt`)*

### 4. Install Playwright Browsers (Required for live URL crawling)
```bash
playwright install chromium
```

---

## CLI Usage & Commands

WebExtractor provides three primary commands: `rip`, `extract`, and `inspect`.

```text
webextractor [command] [target] [options]
```

### 1. `rip` &mdash; Complete Reverse Engineering & Next.js Generation

Captures or ingests a website, extracts all assets, runs design system analysis, and generates a runnable Next.js project.

#### From a Live URL:
```bash
webextractor rip https://example.com
```

#### From a HAR Archive:
```bash
webextractor rip samples/website.har
```

#### Options:
```bash
# Custom destination folder for the generated project
webextractor rip https://example.com -o ./output/my-site
```

#### Quick Shortcut:
Passing a URL directly automatically selects the `rip` pipeline:
```bash
webextractor https://example.com
```

---

### 2. `extract` &mdash; Asset Extraction & Archiving

Extracts and mirrors all raw assets (images, CSS, JS, fonts, media) from a `.har` file into an organized directory with detailed download reports.

```bash
webextractor extract samples/website.har
```

#### Options:
```bash
# Specify custom output folder
webextractor extract samples/website.har -o ./output

# Configure concurrent download worker threads
webextractor extract samples/website.har --workers 16
```

#### Quick Shortcut:
Passing a `.har` file path directly defaults to extraction:
```bash
webextractor samples/website.har
```

---

### 3. `inspect` &mdash; Architecture & Resource Inspection

Analyzes the contents of a HAR file and outputs a summary of the site's framework, unique domains, API endpoints, and resource breakdown table.

```bash
webextractor inspect samples/website.har
```

---

## Running the Generated Next.js Site

Once `webextractor rip` finishes, the project is ready to install and launch:

```bash
# 1. Navigate to the generated project directory
cd output/<site-name>

# 2. Install dependencies
npm install

# 3. Start local development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the reconstructed site.

---

## Project Structure

### Repository Architecture

```text
WebExtractor/
├── pyproject.toml               # Package build configuration & dependencies
├── requirements.txt             # Direct Python dependencies
├── src/
│   └── webextractor/
│       ├── __init__.py
│       ├── __main__.py          # Python -m webextractor entrypoint
│       ├── config.py            # Global settings, viewports, headers, timeouts
│       ├── constants.py         # Static mappings & asset classifications
│       │
│       ├── analysis/            # Interface & Design System Analysis
│       │   ├── analyzer.py          # Multi-pass analysis coordinator
│       │   ├── component_engine.py  # Component detection & clustering
│       │   ├── framework.py         # Source framework detection (Framer, Next, React...)
│       │   ├── layout_engine.py     # Flexbox, Grid, and responsive layout analysis
│       │   ├── typography_engine.py # Font scales, font-family extraction, webfonts
│       │   ├── design_system.py     # Palette, spacing, and design tokens
│       │   ├── routes.py            # Navigation and route hierarchy
│       │   ├── interactions.py      # Micro-interactions, hover states, menu triggers
│       │   └── motion_adapters/     # Framer Motion & CSS animation adapters
│       │
│       ├── assets/              # Canonical Asset Pipeline
│       │   ├── discovery.py         # Discovery from crawler snapshots & HARs
│       │   ├── downloader.py        # Asynchronous multi-worker asset downloader
│       │   ├── organizer.py         # Directory organization for public/ folder
│       │   ├── binding.py           # Asset binding & URL re-mapping
│       │   └── manifest.py          # Asset manifest data models
│       │
│       ├── capture/             # Browser Automation & Ingestion
│       │   ├── browser.py           # Playwright browser lifecycle manager
│       │   ├── crawler.py           # Crawling, multi-route discovery, snapshot runner
│       │   ├── dom.py               # DOM tree serialization & computed styles
│       │   ├── multi_viewport.py    # Desktop, tablet, and mobile capture
│       │   ├── network.py           # Request / response interception
│       │   ├── screenshot.py        # Viewport and element screenshot engine
│       │   └── states.py            # Interaction state capture (scroll, hover, modals)
│       │
│       ├── cli/                 # Command-Line Interface
│       │   ├── main.py              # CLI argument parser & command routing
│       │   └── commands/
│       │       ├── rip.py           # 'rip' command pipeline coordinator
│       │       ├── extract.py       # 'extract' asset downloader command
│       │       └── inspect.py       # 'inspect' HAR inspection command
│       │
│       ├── downloader/          # Asset Downloader & Reporting
│       │   ├── download.py          # Asynchronous download engine
│       │   ├── concurrency.py       # Worker queue management
│       │   └── reports.py           # Report generators (report.json, failed.txt, tree.txt)
│       │
│       ├── generator/           # React & Next.js Code Synthesis
│       │   ├── project.py           # Full Next.js App Router project generator
│       │   ├── components.py        # Component TSX generation
│       │   ├── dom_emitter.py       # DOM-to-JSX tree compiler
│       │   ├── nextjs.py            # Layout, page templates, and configurations
│       │   ├── styles.py            # Tailwind configuration & global stylesheets
│       │   └── tokens.py            # CSS design token variables
│       │
│       ├── har/                 # HAR (HTTP Archive) Ingestion
│       │   ├── parser.py            # Fast JSON streaming HAR parser
│       │   ├── entries.py           # Entry extraction (payloads, headers, status)
│       │   └── normalizer.py        # URL sanitization & mime-type classification
│       │
│       ├── model/               # Data Models & Intermediate Representation
│       │   ├── site_ir.py           # Canonical Site Intermediate Representation (SiteIR)
│       │   ├── site.py              # Site level abstractions
│       │   ├── component.py         # Component AST models
│       │   ├── asset.py             # Asset models & metadata
│       │   └── route.py             # Route definitions
│       │
│       ├── utils/               # Shared Utilities
│       │   ├── filesystem.py        # Safe file I/O operations
│       │   ├── sanitize.py          # Safe identifier and path sanitization
│       │   └── mime.py              # File extension & MIME resolution
│       │
│       └── verification/        # Integrity & Verification Auditing
│           ├── visual_diff.py       # Similarity and structural scoring
│           ├── screenshots.py       # Snapshot comparison capture
│           └── report.py            # Verification report generator
│
└── tests/                       # Test Suite (100+ unit & integration tests)
```

---

## Generated Output Architecture

### 1. When Running `webextractor rip`:
The generated Next.js project is placed in `output/<site-name>/`:

```text
output/<site-name>/
├── app/
│   ├── layout.tsx               # Root layout with fonts, metadata, and styles
│   ├── page.tsx                 # Main landing page assembling components
│   └── [sub-routes]/            # Discovered multi-page routes
│       └── page.tsx
│
├── components/                  # Extracted and structured React components
│   ├── Header.tsx
│   ├── Hero.tsx
│   ├── Features.tsx
│   └── Footer.tsx
│
├── public/                      # Downloaded and organized site assets
│   ├── images/
│   ├── fonts/
│   ├── videos/
│   └── icons/
│
├── styles/
│   ├── globals.css              # Global styles & Tailwind directives
│   └── tokens.css               # Extracted CSS custom properties & color tokens
│
├── analysis/
│   ├── site_ir.json             # Serialized Site Intermediate Representation
│   └── verification_report.json # Structural integrity audit & asset metrics
│
├── package.json                 # Next.js, React, Lucide, and Tailwind dependencies
├── tsconfig.json                # TypeScript configuration with path aliases
├── next.config.ts               # Next.js project settings
├── tailwind.config.ts           # Tailwind CSS configuration mapped to tokens
└── README.md                    # Generated project instructions
```

### 2. When Running `webextractor extract`:
The downloaded asset hierarchy is placed in `output/<har-name>/`:

```text
output/<har-name>/
├── <domain-name>/               # Assets sorted by original hosting domain
│   ├── css/
│   ├── js/
│   ├── images/
│   ├── fonts/
│   └── media/
│
├── report.json                  # Complete audit of all discovered assets & statuses
├── urls.txt                     # Plain text list of all extracted URLs
├── failed.txt                   # Any URLs that encountered download errors
└── tree.txt                     # Hierarchy overview of saved files
```

---

## How to Capture a HAR File (Browser Guide)

If you prefer offline extraction or are analyzing an authenticated / complex web app:

1. Open **Google Chrome**, **Microsoft Edge**, or **Brave**.
2. Navigate to the website you wish to capture.
3. Open Developer Tools: press **F12** (or `Ctrl + Shift + I` on Windows / `Cmd + Option + I` on macOS).
4. Click on the **Network** tab.
5. Check the **Preserve log** checkbox and ensure **Disable cache** is checked.
6. Refresh the page to capture all initial requests.
7. **Pro-tip:** Scroll through the entire page, trigger any dropdowns, modals, and tabs to capture lazy-loaded images, fonts, and dynamic resources.
8. Right-click anywhere in the Network request list and select **"Save all as HAR with content"** (or click the export HAR icon).
9. Save the file (e.g. `website.har`) and pass it to WebExtractor:
   ```bash
   webextractor rip website.har
   ```

---

## Running Tests

WebExtractor includes a test suite covering the parsing engine, component analyzer, layout engine, asset pipeline, and Next.js project generation.

To run the test suite:
```bash
# Windows PowerShell
.\.venv\Scripts\python.exe -m pytest

# Linux / macOS
pytest
```

---

## License

This project is licensed under the MIT License.
