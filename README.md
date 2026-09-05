# WebExtractor

WebExtractor is a Python tool that downloads the files and resources used by a website.

It can extract resources from a HAR (HTTP Archive) file and download them locally.

## What can it download?

WebExtractor can find and download:

- HTML
- CSS
- JavaScript
- Images
- Videos
- Fonts
- Documents
- API resources
- Other files requested by the website

It also creates reports showing what was downloaded and what failed.

---

## How it works

WebExtractor works in 3 simple steps:

1. Open a website in your browser.
2. Record the website's network activity as a `.har` file.
3. Give the `.har` file to WebExtractor.

The tool then downloads the resources into a local folder.

```text
Website
   ↓
Browser
   ↓
HAR file
   ↓
WebExtractor
   ↓
Downloaded website resources
```

---

## Installation

### 1. Open the project
```bash
cd WebExtractor
```

### 2. Create a virtual environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install WebExtractor
```bash
pip install -e .
```

---

## Extract a Website

### Step 1 &mdash; Create a HAR file

1. Open the website you want to extract in Chrome or Edge (e.g. `https://example.com`).
2. Open Developer Tools by pressing **F12** (or `Ctrl + Shift + I`).
3. Go to the **Network** tab.
4. Enable **Preserve log**.
5. Reload the website.
6. Let the website completely load.

> **Tip:** If the website has scrolling animations, videos, lazy-loaded images, project sections, menus, or interactive content, scroll through the entire website and interact with important sections. This helps capture all the resources used by the website.

7. Right-click anywhere in the network table and choose **Save all as HAR with content** (or click the export HAR icon) and save it as:
   `website.har`

---

### Step 2 &mdash; Run WebExtractor

Put the HAR file somewhere convenient.

For example:
```
WebExtractor/
├── samples/
│   └── website.har
```

Then run:

#### 1. Extract and Download Assets
```bash
webextractor extract samples/website.har
# (or simply: webextractor samples/website.har)
```

**Options:**
```bash
# Custom output directory
webextractor extract samples/website.har --output ./output

# Change download workers
webextractor extract samples/website.har --workers 16
```

#### 2. Inspect Website Architecture
Analyze framework, domains, resource counts, and API endpoints from a HAR file:
```bash
webextractor inspect samples/website.har
```

#### 3. Reconstruct a Starter Project
Generate a starter Next.js application based on the HAR analysis:
```bash
webextractor reconstruct samples/website.har
# (or with custom directory: webextractor reconstruct samples/website.har -o ./my-site)
```
After generating:
```bash
cd reconstructed-site/website
npm install
npm run dev
```

---

## Output

After extraction, the tool creates a folder inside `output/` named after your `.har` file (e.g., `output/website/` for `website.har`):

```text
output/
│
└── website/                        # Folder named after the .har file
    ├── example.com/                # Mirrored assets by domain
    │   ├── css/
    │   ├── js/
    │   ├── images/
    │   ├── fonts/
    │   └── ...
    │
    ├── report.json
    ├── urls.txt
    ├── failed.txt
    └── tree.txt
```

### Output Files:
- **`report.json`**: Detailed summary of all extracted assets, statuses, and file sizes.
- **`urls.txt`**: List of all unique asset URLs found.
- **`failed.txt`**: List of URLs that could not be downloaded.
- **`tree.txt`**: Hierarchy map of the downloaded files.
