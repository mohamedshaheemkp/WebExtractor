                    WebExtractor
                         │
              URL or HAR file
                         │
                         ▼
              ┌──────────────────┐
              │  DEEP CAPTURE     │
              │                  │
              │ DOM              │
              │ Accessibility    │
              │ CSS              │
              │ Network          │
              │ Assets           │
              │ Routes           │
              │ States           │
              │ Screenshots      │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  REVERSE ENGINE  │
              │                  │
              │ Components       │
              │ Layout           │
              │ Design tokens    │
              │ Typography       │
              │ Responsive       │
              │ Interactions     │
              │ APIs             │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  CODE GENERATOR  │
              │                  │
              │ React            │
              │ Next.js          │
              │ TypeScript       │
              │ Tailwind         │
              │ Components       │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │    VERIFY        │
              │                  │
              │ Screenshot diff  │
              │ Layout comparison│
              │ Missing assets   │
              └────────┬─────────┘
                       ▼
                 COMPLETE PROJECT







                 What the final command should look like
URL
webextractor rip https://example.com

Then:

WebExtractor
────────────────────────────────────────────

[1/6] Launching browser
      ✓ Chromium started

[2/6] Crawling website
      ✓ 8 routes discovered
      ✓ 14 interaction states

[3/6] Analyzing interface
      ✓ 42 components
      ✓ 18 design tokens
      ✓ 3 font families
      ✓ 67 assets

[4/6] Building site model
      ✓ Component tree
      ✓ Route graph
      ✓ Responsive layouts
      ✓ Interaction graph

[5/6] Generating React
      ✓ TypeScript
      ✓ Next.js App Router
      ✓ Tailwind CSS

[6/6] Verifying
      ✓ 94.8% visual similarity

Project generated:
./example-com/

Then:

cd example-com
npm install
npm run dev
And HAR should work too
webextractor rip website.har

The difference is:

URL mode
URL
 ↓
Playwright browser
 ↓
crawl + capture
 ↓
analysis
 ↓
generation
HAR mode
HAR
 ↓
HAR parser
 ↓
resources + captured responses
 ↓
analysis
 ↓
generation

HAR mode won't have information that wasn't captured, while URL mode can actively explore the site.





//////////////////////////////////////////////////////////



What I want WebExtractor to do with this URL

You should ultimately be able to run:

webextractor rip https://glad-service-673278-17a284d97.framer.app/

and get:

webextractor/
└── output/
    └── glad-service/
        ├── app/
        │   ├── page.tsx
        │   ├── layout.tsx
        │   └── projects/
        │
        ├── components/
        │   ├── Intro.tsx
        │   ├── Projects.tsx
        │   ├── About.tsx
        │   ├── Capabilities.tsx
        │   ├── Voice.tsx
        │   ├── Journey.tsx
        │   ├── Toolkit.tsx
        │   └── Footer.tsx
        │
        ├── public/
        │   ├── images/
        │   ├── fonts/
        │   └── videos/
        │
        ├── styles/
        │   └── globals.css
        │
        ├── analysis/
        │   ├── site.json
        │   ├── components.json
        │   ├── tokens.json
        │   ├── routes.json
        │   └── interactions.json
        │
        ├── package.json
        ├── next.config.ts
        ├── tailwind.config.ts
        └── README.md

And the generated site should look and behave like your Framer site, rather than just displaying the extracted text.