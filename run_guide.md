# Run Guide

## 1. Setup

```bash
cd WebExtractor

# Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
# .\.venv\Scripts\activate.bat (CMD) | source .venv/bin/activate (macOS/Linux)

# Install dependencies & browser
pip install -e .
playwright install chromium
```

---

## 2. Run WebExtractor

### Full Site Generation (Next.js)
```bash
# Live URL
webextractor rip https://example.com

# Offline HAR
webextractor rip samples/website.har

# Custom output folder & viewports
webextractor rip https://example.com -o ./output/my-site --viewports 375,768,1024,1440,1920

# Shortcut
webextractor https://example.com
```

### Standalone Static HTML/CSS/JS Export
```bash
# Generate pure zero-dependency static site (no Node/npm needed)
webextractor rip https://example.com -o ./output/my-static-site -t html
```

### Extract Assets Only
```bash
webextractor extract samples/website.har -o ./output/assets --workers 16
```

### Inspect HAR
```bash
webextractor inspect samples/website.har
```

---

## 3. Run Generated Site

### Next.js App Router (Default)
```bash
cd output/<site-name>
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000).

```bash
# Production
npm run build
npm run start
```

### Static HTML/CSS/JS (`-t html`)
```bash
cd output/<site-name>
# Open index.html directly, or run local HTTP server:
python -m http.server 3000
```
Open [http://localhost:3000](http://localhost:3000).

---

## 4. Tests

```bash
pytest
```

---

## 5. Troubleshooting

- **Missing browser**: `playwright install chromium`
- **PowerShell script error**: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
- **Command not found**: Use `python -m webextractor <command>` or run `pip install -e .` in activated `.venv`.
