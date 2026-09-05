I would build it in this order
STEP 1 — Browser Capture Engine

Add:

src/webextractor/browser/
├── browser.py
├── crawler.py
├── dom.py
├── styles.py
├── network.py
├── screenshots.py
└── states.py

Using Playwright.

This gives us the raw evidence.

STEP 2 — Site Model

Add:

src/webextractor/model/
├── site.py
├── page.py
├── component.py
├── asset.py
├── route.py
├── token.py
├── interaction.py
└── state.py

This becomes the central representation of the website.

STEP 3 — Analyzer
src/webextractor/analyzer/
├── components.py
├── framework.py
├── layout.py
├── tokens.py
├── routes.py
├── responsive.py
├── interactions.py
└── accessibility.py
STEP 4 — Generator
src/webextractor/generator/
├── react.py
├── nextjs.py
├── typescript.py
├── tailwind.py
├── components.py
└── assets.py
STEP 5 — Verification
src/webextractor/verify/
├── screenshot.py
├── visual_diff.py
├── dom_diff.py
└── report.py