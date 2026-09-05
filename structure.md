src/webextractor/
│
├── cli/
│   ├── commands/
│   │   ├── extract.py
│   │   ├── inspect.py
│   │   └── rip.py
│   │
│   └── main.py
│
├── capture/
│   ├── browser.py
│   ├── crawler.py
│   ├── dom.py
│   ├── network.py
│   ├── screenshot.py
│   └── states.py
│
├── har/
│   ├── parser.py
│   ├── entries.py
│   └── normalizer.py
│
├── analysis/
│   ├── components.py
│   ├── framework.py
│   ├── layout.py
│   ├── typography.py
│   ├── tokens.py
│   ├── assets.py
│   ├── routes.py
│   ├── interactions.py
│   └── accessibility.py
│
├── model/
│   ├── site.py
│   ├── page.py
│   ├── component.py
│   ├── asset.py
│   ├── token.py
│   ├── interaction.py
│   └── route.py
│
├── generator/
│   ├── react.py
│   ├── nextjs.py
│   ├── components.py
│   ├── styles.py
│   ├── assets.py
│   └── project.py
│
├── verification/
│   ├── screenshots.py
│   ├── visual_diff.py
│   └── report.py
│
└── downloader/
    ├── download.py
    ├── concurrency.py
    └── reports.py