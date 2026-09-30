WebExtractor — Engineering Steps & Fidelity Gates

Purpose

WebExtractor is an evidence-driven website reverse-engineering and reconstruction engine.

The engineering order follows the WebExtractor Formula:

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

The key rule is:

Never let the generator invent evidence.

If the source does not provide enough evidence for a behavior or structural interpretation, WebExtractor must preserve the uncertainty rather than fabricate a value.

Engineering Order

STEP 0 — Establish the Ground-Truth Capture

Before improving reconstruction, preserve a reproducible capture of the source website.

For each target site, record:

source URL

capture timestamp

routes discovered

viewport set

network/HAR evidence

DOM evidence

computed styles

assets

fonts

screenshots

interaction/behavioral evidence where available

For the current Porto/Framer regression target, the validated viewport set is:

375
768
1024
1440
1920

The static reference must remain available for later validation.

STEP 1 — Browser Capture Engine

The browser layer is responsible for collecting raw evidence, not interpreting it.

Current implementation is already centered around Playwright and existing capture infrastructure. The exact repository layout should follow the current codebase rather than creating duplicate capture systems.

Conceptually:

src/webextractor/capture/

├── browser.py
├── crawler.py
├── multi_viewport.py
└── ...

The capture engine should collect:

rendered DOM

raw element attributes

computed styles

CSS/style evidence

network/HAR data

assets and resource URLs

fonts

screenshots

viewport measurements

route/navigation state

animation attributes such as:

data-framer-appear-id

data-motion-id

data-aos

behavioral evidence where observable

Capture invariant

Capture must preserve evidence before analysis transforms it.

Do not make the browser layer responsible for deciding:

"This is a Hero component."
"This is a React component."
"This animation should be 800ms."

Those are analysis/reconstruction concerns.

STEP 2 — Evidence / Site Model

The previous plan proposed a new model/ package as the central representation.

The current architecture should not blindly duplicate the existing analysis/evidence structures.

The project already contains:

DOM analysis

asset models/bindings

interaction IR

behavioral evidence

design-token extraction

layout analysis

animation evidence

route/framework analysis

Therefore the rule is:

First audit the existing representations. Introduce a centralized Site Model only where it removes duplication and gives the pipeline a stable contract.

The eventual conceptual model should represent:

Site
 ├── Pages / Routes
 ├── Components
 ├── Assets
 ├── Design Tokens
 ├── Layout / Responsive Rules
 ├── Interactions
 ├── Animation Evidence
 └── Capture / Validation Metadata

The authoritative reconstruction contract is the versioned Reconstruction IR.

Do not create a second competing source of truth.

STEP 3 — Analysis

Analysis converts captured evidence into structured, evidence-backed conclusions.

Current analysis responsibilities include:

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
├── motion_adapters/
└── ...

Analysis should cover:

Structure

DOM hierarchy

sections

component boundaries

repeated structures

routes

links

Layout

display mode

flex/grid

widths/heights

margins/padding

gaps

alignment

positioning

stacking

transforms

overflow

container constraints

Typography

font family

font source

weight

size

line height

letter spacing

wrapping

Assets

authoritative MIME classification

images

SVGs

videos

fonts

responsive variants

asset bindings

Responsive behavior

Capture and compare:

375
768
1024
1440
1920

Then infer only changes supported by evidence:

visibility

dimensions

positions

typography

layout structure

image variants

navigation behavior

spacing

Behavior

Record evidence for:

hover

focus

click

navigation

scroll

reveal

sticky behavior

parallax

transitions

keyframes

timing/easing

The animation pipeline must retain canonical timing information such as:

timing_function
duration
delay
trigger
type

and must not substitute guessed defaults.

STEP 4 — Reconstruction IR

This step is more important than the previous simple "Site Model → Generator" design.

The analyzer should emit a versioned Reconstruction IR.

The generator should consume the IR.

[Capture + Inference]
         │
         ▼
Validated Reconstruction IR
         │
         ▼
[Static + Dynamic] Generator

There must not be a direct:

Analyzer / Capture → Generator

coupling.

The IR should contain evidence-backed representations for:

pages/routes

components

component relationships

variants

layout

breakpoint rules

design tokens

assets

asset variants/bindings

typography

interactions

animations

metadata

The current draft schema is versioned and must be audited against the actual analyzer and generator before implementation is finalized.

IR rule

If the evidence is insufficient:

UNKNOWN

is preferable to a fabricated value.

STEP 5 — Generator

The generator converts validated IR into editable output.

The current project already generates:

static HTML

React/Next.js projects

CSS

assets

responsive image bindings

animation styles

The conceptual generator responsibilities are:

Generator
├── React / Next.js
├── TypeScript
├── CSS / Tailwind where supported
├── Components
├── Routes
└── Assets

The implementation should reuse the existing generator architecture instead of creating parallel generators unless the current code proves that separation is necessary.

Generator invariant

The generator may transform evidence into code.

It must not invent unsupported behavior.

STATIC FIDELITY GATE

This is a hard architectural gate.

WebExtractor should not treat animation fidelity as successful while static fidelity is still materially wrong.

The gate is divided into five areas.

Gate 1 — Assets

Verify:

correct images

correct videos

correct fonts

correct SVGs

correct responsive image variants

no asset classification collisions

no accidental overwrites

Current validated asset behavior includes MIME-authoritative classification and resolution-aware variants.

Gate 2 — Structure

Verify:

routes

sections

component hierarchy

text

links

visibility

repeated structures

The generated DOM should correspond to the evidence captured from the source.

Gate 3 — Geometry

Verify:

widths

heights

positions

margins

padding

gaps

alignment

stacking

transforms

overflow

container constraints

Horizontal overflow must be measured, not hidden artificially.

For the current Porto regression:

375  → scrollWidth = 375
768  → scrollWidth = 768
1024 → scrollWidth = 1024
1440 → scrollWidth = 1440
1920 → scrollWidth = 1920

Gate 4 — Typography

Verify:

font family

font source

weight

font size

line height

letter spacing

text wrapping

text dimensions

Typography must be validated because even small font differences can create large downstream layout differences.

Gate 5 — Responsive Fidelity

Verify at:

375
768
1024
1440
1920

Compare:

layout

visibility

dimensions

spacing

typography

image variants

navigation

overflow

component relationships

STATIC = PASS

Only when Gates 1–5 meet the project's defined validation thresholds should the reconstruction be considered:

STATIC = PASS

"Reasonably close" should eventually be replaced by explicit measured thresholds.

The current Porto regression baseline is:

375px   81.2%
768px   85.1%
1024px  84.1%
1440px  96.3%
1920px  88.8%

Average visual fidelity: 87.1%
Overall fidelity:         94.2%

These are regression measurements, not permanent universal pass thresholds.

STEP 6 — Interaction Fidelity

After static fidelity passes, validate interactive behavior.

Examples:

navigation

menus

buttons

links

hover states

focus states

click behavior

modal/open-close behavior

sticky/fixed behavior

Validation should use browser interaction tests rather than screenshot-only comparison.

STEP 7 — Transition Fidelity

Validate state-to-state visual transitions.

Examples:

hover
focus
active
open
close
enter
exit

Verify:

property changes

duration

delay

timing function

transition target

initial/final states

Do not assume a default easing or duration when evidence exists.

STEP 8 — Scroll Animation Fidelity

Validate scroll-triggered behavior:

viewport reveal

fade

translate

scale

stagger

sticky transitions

scroll-linked effects

Use behavioral evidence and controlled browser capture.

A screenshot of the final state alone is not sufficient to prove a scroll animation.

STEP 9 — Parallax / Scroll-Linked Fidelity

Validate:

element movement relative to scroll

scroll progress mapping

direction

range

sticky relationships

nested scrolling where applicable

Parallax should be reconstructed only when the source provides sufficient evidence.

STEP 10 — Sequencing & Timing Fidelity

This is the highest-level motion validation layer.

Validate:

animation order

delays

stagger intervals

overlapping animations

durations

easing curves

trigger relationships

multi-element sequencing

The objective is not merely:

"the animation exists"

but:

"the reconstructed behavior follows the observed timing model"

STEP 11 — Visual / Behavioral Verification

Verification is a continuous subsystem, not only the final step.

Conceptually:

Original
   │
   ├── screenshot
   ├── DOM evidence
   ├── computed styles
   └── behavior evidence
             │
             ▼
       Generated Site
             │
   ├── screenshot
   ├── DOM evidence
   ├── computed styles
   └── behavior tests
             │
             ▼
       Verification
             │
             ▼
      Diff / Report

Verification should include:

screenshot comparison

pixel/visual diff

DOM comparison

geometry comparison

responsive comparison

asset validation

interaction testing

animation testing

Validation states remain authoritative:

NOT_RUN
PASS
WARN
FAIL
BLOCKED

A PASS must come from empirical validation.

Component counts, asset counts, successful builds, or generated-file counts must never independently turn a result into PASS.

STEP 12 — Repair Loop

When validation identifies a mismatch:

Evidence
   ↓
Mismatch
   ↓
Root-cause analysis
   ↓
Targeted correction
   ↓
Regenerate
   ↓
Screenshot / behavior validation
   ↓
Compare again

The system should prefer correcting the smallest responsible layer.

For example:

wrong asset
→ asset binding

wrong spacing
→ layout evidence / generation

wrong font
→ typography / asset binding

wrong animation timing
→ behavioral evidence / motion analysis

wrong generated structure
→ reconstruction IR / component analysis

Do not solve every mismatch by adding arbitrary CSS overrides.

STEP 13 — Component Deduplication

After the core reconstruction pipeline is validated, improve component reuse.

Use evidence such as:

structural signatures

DOM signatures

visual/perceptual hashes

style similarity

repeated variants

Do not merge components solely because their rendered appearance is similar.

Legitimate variants may share appearance while having different behavior or structure.

Stable component IDs are required for deterministic regeneration.

STEP 14 — Deterministic Generation & Synchronization

Once the reconstruction pipeline is stable:

Source change
    ↓
New capture
    ↓
Evidence diff
    ↓
IR diff
    ↓
Changed components
    ↓
Regenerate
    ↓
Visual / behavioral validation
    ↓
PR / human review

Requirements:

stable IDs

stable ordering

deterministic IR

deterministic generated output

pinned numeric precision

generated/manual ownership boundaries

no accidental modification of human-owned files

Auto-merge should not be used as the default synchronization behavior.

Current Engineering Status

The current Porto regression demonstrates that the pipeline already has substantial end-to-end evidence:

Static HTML export       PASS
Next.js production build PASS
Automated tests          140 / 140 PASS

Horizontal overflow:
375   → 0px
768   → 0px
1024  → 0px
1440  → 0px
1920  → 0px

Average visual fidelity  87.1%
Overall fidelity         94.2%

Viewport results:

375px   81.2%
768px   85.1%
1024px  84.1%
1440px  96.3%
1920px  88.8%

The 1440px result also records a -1.8% regression from the previous baseline. This should remain visible in regression reports rather than being hidden.

Engineering Priority

The project should now prioritize:

1. Preserve reproducible static reference
2. Formalize STATIC FIDELITY GATE
3. Continue improving weak static/responsive regions
4. Validate interaction behavior
5. Validate transitions
6. Validate scroll animations
7. Validate parallax
8. Validate sequencing/timing
9. Formalize Reconstruction IR
10. Component deduplication
11. Deterministic synchronization

Do not jump directly from a successful build to advanced animation reconstruction.

A successful build proves that the generated project compiles.

It does not prove that the reconstruction is faithful.

The fidelity gates and browser-based validation are the authority.