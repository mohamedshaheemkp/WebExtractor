# WebExtractor — Engineering Steps

## Architecture Pipeline — The WebExtractor Formula

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

---

## STEP 1 — Browser Capture

Use Playwright to collect source evidence.

Current capture responsibilities:

- DOM
- computed styles
- network / HAR
- assets
- fonts
- screenshots
- viewport measurements
- route/navigation state
- observable animation attributes
- behavioral evidence

Existing capture code:

```text
src/webextractor/capture/
├── browser.py
├── crawler.py
├── multi_viewport.py
└── ...
```

Capture preserves evidence. It does not infer components or invent behavior.

---

## STEP 2 — Evidence Model

Keep the captured evidence as the source for analysis.

The project already has representations for:

- DOM
- assets and bindings
- layout
- design tokens
- interactions
- behavioral evidence
- animations
- routes
- framework detection

Do not create duplicate models unless the existing structures are first audited.

---

## STEP 3 — Analysis

Convert evidence into structured findings.

```text
src/webextractor/analysis/
├── components.py
├── framework.py
├── layout.py
├── design_system.py
├── dom.py
├── assets.py
├── interactions.py
├── accessibility.py
├── animations.py
└── motion_adapters/
```

Analysis covers:

- component structure
- layout
- typography
- assets
- routes
- responsive behavior
- interactions
- animations
- accessibility
- design tokens

Only evidence-supported conclusions are emitted.

---

## STEP 4 — Reconstruction IR

Analysis produces a versioned Reconstruction IR.

```text
[Capture + Inference]
         ↓
         IR
         ↓
[Static + Dynamic]
         ↓
Reconstructed Website
```

The generator consumes the IR instead of depending directly on analyzer internals.

The IR represents:

- pages / routes
- components
- component relationships
- variants
- layout
- breakpoint rules
- design tokens
- assets and variants
- typography
- interactions
- animations

The schema must be validated against the current analyzer and generator before it is treated as final.

---

## STEP 5 — Generation

Generate editable output from the validated IR.

Current outputs include:

- Static HTML
- React / Next.js
- CSS
- assets
- responsive image bindings
- animation styles

The generator must not invent unsupported evidence.

---

# STATIC FIDELITY GATE

Animations are not considered until static fidelity passes.

## Gate 1 — Assets

Verify:

- images
- videos
- fonts
- SVGs
- responsive variants
- asset bindings
- no variant collisions

## Gate 2 — Structure

Verify:

- routes
- sections
- component hierarchy
- text
- links
- visibility

## Gate 3 — Geometry

Verify:

- widths
- heights
- positions
- margins
- padding
- gaps
- alignment
- stacking
- transforms
- overflow

## Gate 4 — Typography

Verify:

- font family
- weight
- size
- line height
- letter spacing
- text wrapping

## Gate 5 — Responsive

Verify:

```text
375
768
1024
1440
1920
```

Compare:

- layout
- visibility
- dimensions
- spacing
- typography
- image variants
- navigation
- overflow

When Gates 1–5 meet the defined validation thresholds:

```text
STATIC = PASS
```

---

## STEP 6 — Interaction Fidelity

After static fidelity passes, validate:

- navigation
- menus
- links
- buttons
- hover
- focus
- click behavior
- open / close states
- sticky / fixed behavior

---

## STEP 7 — Transition Fidelity

Validate:

- transition properties
- duration
- delay
- timing function
- initial state
- final state

---

## STEP 8 — Scroll Animation Fidelity

Validate:

- viewport reveals
- fades
- transforms
- scale
- stagger
- sticky transitions
- scroll-linked effects

---

## STEP 9 — Parallax Fidelity

Validate:

- scroll-linked movement
- direction
- range
- sticky relationships

Only reconstruct when supported by evidence.

---

## STEP 10 — Sequencing & Timing

Validate:

- animation order
- delays
- stagger
- overlapping animations
- durations
- easing
- trigger relationships

---

## Verification

Verification is empirical.

```text
Original
   ↓
Capture
   ↓
Generated
   ↓
Capture
   ↓
Compare
   ↓
Report
```

Use:

- screenshot / pixel diff
- geometry comparison
- DOM comparison
- responsive comparison
- asset validation
- interaction tests
- animation tests

Validation states:

```text
NOT_RUN
PASS
WARN
FAIL
BLOCKED
```

A PASS must come from validation evidence.

---

## Repair Loop

```text
Evidence
   ↓
Mismatch
   ↓
Root Cause
   ↓
Fix
   ↓
Regenerate
   ↓
Verify
```

Fix the responsible layer instead of adding arbitrary overrides.

---

## Current Porto Regression Baseline

Target:

```text
https://glad-service-673278.framer.app/
```

Viewports:

```text
375
768
1024
1440
1920
```

Visual results:

```text
375   → 81.2%
768   → 85.1%
1024  → 84.1%
1440  → 96.3%
1920  → 88.8%
```

Average visual fidelity:

```text
87.1%
```

Overall fidelity:

```text
94.2%
```

Horizontal overflow:

```text
375   → 0px
768   → 0px
1024  → 0px
1440  → 0px
1920  → 0px
```

Automated tests:

```text
140 / 140 PASS
```

Next.js production build:

```text
PASS
```

Static HTML verification:

```text
PASS
```
