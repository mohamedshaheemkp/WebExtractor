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









We should establish a "STATIC FIDELITY GATE"

Before WebExtractor is allowed to work on animations:

Gate 1 — Assets
✓ correct images
✓ correct videos
✓ correct fonts
✓ correct SVGs
Gate 2 — Structure
✓ routes
✓ sections
✓ component hierarchy
✓ text
✓ links
Gate 3 — Geometry
✓ widths
✓ heights
✓ positions
✓ margins
✓ padding
✓ gaps
✓ stacking
✓ overflow
Gate 4 — Typography
✓ font family
✓ weight
✓ size
✓ line height
✓ letter spacing
✓ wrapping
Gate 5 — Responsive
✓ 375
✓ 768
✓ 1024
✓ 1440
✓ 1920

Only after all five are reasonably close:

STATIC = PASS

Then:

Gate 6 → interactions
Gate 7 → transitions
Gate 8 → scroll animations
Gate 9 → parallax
Gate 10 → sequencing/timing