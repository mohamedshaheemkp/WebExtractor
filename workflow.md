WebExtractor — Engineering Workflow

Status: Active
Purpose: Standing engineering workflow for WebExtractor. This document defines how the project is developed, validated, debugged, and extended. It should be read together with:

docs/IR_SCHEMA.md — data contract between analysis and generation

docs/PHASE_PLAN.md — current phase, dependencies, and exit criteria

docs/PATCH_FORMAT.md — patch/handoff contract for implementation

These documents are the project source of truth. Do not reconstruct architecture from conversation history when the repository documents already define it.

1. Project identity

WebExtractor is not merely a website downloader and not an LLM-driven visual website generator.

It is an evidence-driven website reverse-engineering and reconstruction system.

The long-term goal is:

Capture a website accurately, preserve a stable ground-truth representation, derive a versioned intermediate representation, reconstruct the observable behavior and visual system into maintainable React/Next.js code, validate the result against captured evidence, and eventually keep the reconstruction synchronized with source changes.

The system must prioritize:

Evidence → deterministic analysis → reconstruction → validation

over:

Guess → generate → visually hope it is correct

2. Two output paths

WebExtractor has two fundamentally different outputs built on the same capture layer.

A. Flat export — fidelity-first ground truth

The flat exporter preserves the rendered website as faithfully as practical:

Source website
    ↓
Browser capture
    ↓
Rendered HTML/CSS/JS/assets
    ↓
Asset URL rewrite
    ↓
Minimal, explicitly-defined runtime stripping
    ↓
Static package

Its purpose is not to produce elegant source code.

Its purpose is to establish a stable, local reference representation with minimal semantic loss.

This is the foundation for visual validation.

Flat export must not:

reconstruct React components

infer a design system

simplify CSS

invent responsive rules

reinterpret animations

replace unknown behavior with guesses

Only deliberate capture/package transformations should occur.

Ground-truth rule

The flat export is the local reference artifact used to validate the editable reconstruction.

Captured source
      ↓
Flat export
      ↓
GROUND TRUTH
      ↓
React/Next.js reconstruction
      ↓
Screenshot/component validation

B. Editable reconstruction — maintainable source

The reconstruction path is intentionally harder:

Raw capture
    ↓
IR construction
    ↓
Analysis
    ↓
Validated IR
    ↓
Code generation
    ↓
React / Next.js

Its purpose is to produce:

reusable components

design tokens

responsive rules

real assets

typography systems

interactions

animation adapters

maintainable source code

The reconstruction path may lose fidelity if analysis or generation is wrong. Therefore it must always be validated against the flat-export ground truth.

3. Core Architecture — The WebExtractor Formula

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

The central architectural rule is:

Browser capture preserves empirical evidence (DOM/CSS, Assets, Runtime) without guessing. The Behavior Engine infers structure, stateful interactions, and motion semantics (Layout, States, Motion) into a unified Site Intermediate Representation (IR). Generators branch into Static and Dynamic pipelines that reconstruct the website. Verification tests both pixel fidelity and behavioral fidelity against the source.

Analysis and generation must not directly exchange ad-hoc internal objects or raw capture data.

4. Evidence and capture layer

The capture layer is the foundation shared by both output paths.

Existing infrastructure includes:

Playwright browser capture

DOM capture

computed-style capture

HAR/network evidence

asset discovery/download

viewport capture

scroll/reveal evidence

interaction evidence

framework detection

existing behavioral evidence and Interaction IR

The capture layer should collect evidence rather than prematurely decide how the final application should be implemented.

Capture targets

Where practical, capture:

DOM
computed styles
authored CSS / stylesheet references
network requests
assets
fonts
screenshots
viewport dimensions
responsive observations
scroll states
hover states
focus states
interaction states
animation evidence
navigation/routes
accessibility/semantic attributes

Viewports

The baseline reconstruction/validation set is:

375
768
1024
1440

Additional viewports may be used when the source requires them.

The exact viewport dimensions and capture metadata must be recorded in the capture/IR artifacts rather than assumed later.

5. Flat-export requirements

Phase 0 establishes the ground truth.

The initial implementation should reuse the existing browser.py / crawler.py capture infrastructure.

Required work:

Capture rendered output.

Rewrite captured asset URLs to local relative paths.

Download/bind assets where permitted and appropriate.

Apply explicit Framer-specific stripping rules where required.

Package the result as a standalone static bundle.

Produce a manifest describing the capture.

Example:

test-runs/
└── porto/
    └── flat/
        ├── index.html
        ├── assets/
        ├── css/
        ├── js/
        └── manifest.json

The flat export must be independently renderable without the React reconstruction.

Important evidence rule

The exact implementation details of third-party exporters such as NoCodeXport are not assumed to be known. Their observed behavior can inform our architecture, but WebExtractor's implementation must be based on our own tested capture evidence.

6. Validation is a hard dependency

The screenshot-diff system is not an optional polish feature.

It is the mechanism that makes reconstruction correctness measurable.

Minimum validation loop

Flat-export reference
        ↓
same viewport
        ↓
screenshot

Generated React/Next.js
        ↓
same viewport
        ↓
screenshot

        ↓
      DIFF

Initial validation should provide:

overall difference

difference image/heatmap

difference bounding regions

viewport-specific results

pass/fail threshold

enough information to identify the likely affected region

Component-level attribution should be added as component identity becomes reliable.

Do not make the first validation implementation unnecessarily dependent on the future component-dedup system.

7. Debugging workflow

Never patch from visual intuition alone when evidence can be collected.

Use:

Observed failure
    ↓
Capture evidence
    ↓
Identify mismatch
    ↓
Trace file → function → line
    ↓
Confirm root cause
    ↓
Write minimal patch
    ↓
Run tests
    ↓
Run visual validation
    ↓
Compare result

A hypothesis must remain explicitly marked as a hypothesis until confirmed by the code or captured evidence.

Do not convert repeated discussion into "fact" without verification.

8. Current Porto animation issue

A concrete root-cause candidate has been traced in the current codebase.

Reported evidence:

src/webextractor/analysis/animations.py:43-55

adapters are run and their motion_triggers are merged

motion_triggers uses .extend() without cross-adapter reconciliation

src/webextractor/analysis/motion_adapters/standard.py:23-24

StandardCssMotionAdapter.can_handle() returns True universally

src/webextractor/analysis/motion_adapters/framer.py:17-22

FramerMotionAdapter.can_handle() activates when "framer" appears in the HTML

src/webextractor/analysis/analyzer.py:549-577

_extract_dom_transitions() already contains matching-trigger checks

src/webextractor/generator/project.py:38

src/webextractor/generator/project.py:1083

generated behavior consumes the merged motion_triggers

The reported failure path is:

Framer page
    ↓
Standard adapter + Framer adapter
    ↓
both may emit triggers for the same target
    ↓
motion_triggers.extend(...)
    ↓
duplicate/conflicting triggers
    ↓
generator applies multiple triggers
    ↓
Porto animation mismatch

Important

The existence of an un-deduplicated merge is evidence of a real defect risk, but the exact deduplication identity must be established from the actual trigger structure.

Do not blindly:

remove one adapter

keep one adapter universally

convert the list to a set

deduplicate only by target

assume every same-target trigger is a duplicate

Legitimate triggers can coexist.

Phase 2 must establish the correct reconciliation semantics before patching.

This fix belongs before IR construction so corrupted motion evidence is not baked into the IR.

9. Intermediate Representation

The IR is the formal contract between analysis and generation.

Current schema location:

docs/IR_SCHEMA.md

Current schema status is DRAFT until audited against the real analyzer and generator.

The initial conceptual shape is:

Site
├── pages
├── components
├── designTokens
└── assets

Components may contain:

stable identity

DOM signature

visual hash

variants

style/token references

breakpoint rules

animations

child relationships

The IR must be versioned.

Analyzer and generator must reject unsupported schema versions rather than silently producing incompatible output.

IR audit requirement

Before implementing Phase 3:

IR_SCHEMA.md
       │
       ├── current analyzer output
       │
       └── current generator input
                ↓
          GAP ANALYSIS
                ↓
          revise schema
                ↓
          only then patch

Every proposed IR field should be classified during the audit as something such as:

EXISTS
PARTIALLY EXISTS
DERIVABLE
MISSING
CONFLICTS
UNKNOWN

Do not assume the draft schema matches existing code.

10. Component reconstruction

The target is not a DOM dump.

A repeated structure should eventually become something like:

ProjectCard
├── image
├── title
├── category
└── metadata

with content represented as data/props rather than duplicated components.

Component identity should be deterministic and stable.

Avoid incrementing identities such as:

Component1
Component2
Component3

because unrelated upstream changes can shift every later identifier.

Use a deliberate stable identity strategy defined by the IR contract.

Visual deduplication can combine:

structural signature
+
style signature
+
subtree visual/perceptual similarity

Do not build the visual-dedup system before correctness can be measured.

11. Responsive reconstruction

Responsive behavior is an inference problem.

Do not simply capture desktop pixel values and create arbitrary media queries.

Capture multiple viewports and compare:

DOM structure
computed styles
positions
dimensions
visibility
typography
images
navigation
grid/flex behavior

Then infer rules only when the evidence supports them.

Example:

1440 → 4 columns
1024 → 3 columns
768  → 2 columns
375  → 1 column

The generated result should express the underlying responsive rule rather than four independent pixel snapshots where possible.

This phase comes after single-breakpoint correctness and validation.

12. Design tokens

Tokens should be derived from observed evidence.

Candidate token categories include:

colors
typography
spacing
easings

Near-identical values can eventually be clustered into canonical tokens.

However, token clustering thresholds are not currently fixed.

Do not invent a threshold without a dedicated design decision and validation.

Tokens must not become a mechanism for hiding inaccurate extraction.

13. Animation and interaction model

Animation reconstruction must preserve evidence such as:

target
trigger
type
from/to state
property
duration
delay
timing function
iteration/direction where applicable
adapter

Where the exact value cannot be established:

UNKNOWN

is preferable to inventing a plausible value.

Examples of triggers include:

load
viewport/scroll
hover
focus
active
click

Existing motion adapters should be used rather than reproducing builder-specific runtime internals unnecessarily.

The goal is to reproduce observable behavior, not the original builder's private implementation.

14. Asset strategy

Assets are evidence, not placeholders.

Capture and preserve relevant:

images

SVGs

videos

WebP/AVIF

fonts

favicons

logos

background images

responsive image variants

Where the source provides srcset/sizes, preserve the responsive relationship rather than merely downloading the largest file.

For the editable Next.js output, assets can eventually map to appropriate Next.js primitives where that improves the result without changing observable behavior.

Asset licensing/ownership rules must always be respected.

15. Code generation

Code generation must be:

deterministic

template/AST based where appropriate

human-readable

stable under regeneration

driven by IR

independent of raw capture details

Avoid direct string concatenation as the long-term architecture.

Generated output should have stable:

component names

import ordering

object/property ordering

CSS ordering

serialization

numeric precision

file ordering

Identical input evidence should produce identical output.

This is required before reliable incremental synchronization can exist.

16. Manual edits and generated ownership

Regeneration must not destroy human work.

Initial strategy:

generated/
    WebExtractor-owned output

src/
    human-owned wrappers/overrides

Regeneration may replace generated code but must not overwrite human-owned files.

Do not implement AST-aware merging until the generated/override split has demonstrably become a bottleneck.

17. Multi-route architecture

Eventually WebExtractor should support:

/
 /about
 /projects
 /contact

and identify shared structures across routes:

Header
Footer
Navigation
ProjectCard
Button

Shared components should be generated once where the evidence supports reuse.

Multi-page orchestration should come after the single-page pipeline is reliable.

18. Synchronization architecture

Continuous synchronization is a later phase, not the starting point.

Target:

poll
  ↓
capture
  ↓
component-level hashes
  ↓
compare with previous IR snapshot
  ↓
changed components only
  ↓
deterministic regeneration
  ↓
visual validation
  ↓
GitHub PR
  ↓
human review

Do not auto-merge generated changes into main.

The validation artifact should accompany the PR.

A future per-project configuration can define:

source_url: ...
output_repo: ...
framework: nextjs
poll_interval: 6h
override_dir: src/

The core engine remains project-agnostic.

19. Orchestration and scaling

A future full-site architecture may become:

URL
 ↓
Orchestrator
 ↓
Crawl jobs
 ↓
Browser workers
 ↓
Raw capture store
 ↓
IR
 ↓
Analysis workers
 ↓
Validation
 ↓
Codegen
 ↓
Packaged repository

For large multi-page sites, browser contexts/workers and object storage can be introduced.

Do not build queues, Temporal/BullMQ, or a crawl farm before the single-page pipeline is reliable.

Scaling a broken reconstruction pipeline only parallelizes the failure.

20. Phase gates

Current project order:

Phase 0 — Flat export
        ↓
Phase 1 — Screenshot validation
        ↓
Phase 2 — Fix Porto
        ↓
Phase 3 — IR construction + component dedup
        ↓
Phase 4 — Responsive inference + design tokens
        ↓
Phase 5 — Continuous synchronization

Phase 0

Goal:

Produce a stable, standalone flat representation of Porto.

Exit:

Porto flat export renders correctly without React reconstruction.

Phase 1

Goal:

Compare the editable reconstruction against the flat ground truth.

Exit:

Validation produces objective mismatch information.

Phase 2

Goal:

Fix Porto using measured evidence.

Exit:

Porto reaches the defined visual/behavioral tolerance.

Phase 3

Goal:

Establish and enforce the versioned IR contract and reusable components.

Exit:

Analyzer and generator communicate through versioned IR and validation remains clean.

Phase 4

Goal:

Infer responsive constraints and canonical design tokens.

Exit:

Validation remains clean across the supported viewports.

Phase 5

Goal:

Safely synchronize source changes into human-owned projects.

Exit:

Source changes produce deterministic, validated, component-scoped PRs without overwriting manual work.

21. Development role split

Because multiple AI/code tools are used, architecture must have one written source of truth.

Claude

Use for:

architecture decisions

initial/major schema design

root-cause diagnosis on real code

decisions requiring full project history

review of batches of implementation patches

architecture drift detection

ChatGPT

Use for:

implementation against existing written specifications

routine/mechanical patches

tests and boilerplate

straightforward capture/asset logic

bounded technical research/review

ChatGPT must not silently redesign the architecture.

If a task conflicts with the written contract:

flag the conflict instead of improvising.

Antigravity

Use for:

applying patches

running commands

running tests/builds

executing the repository

reporting actual results

22. Context handoff

Every session should begin from the repository contracts rather than verbal reconstruction of project history.

Relevant documents:

docs/IR_SCHEMA.md
docs/PHASE_PLAN.md
docs/PATCH_FORMAT.md

For ChatGPT implementation sessions, provide the relevant document sections and the actual files needed for the requested patch.

Do not ask a model to trace code it has not been shown.

Do not fabricate file contents, APIs, line numbers, or test results.

Batch routine ChatGPT patches for architecture review rather than sending every tiny patch for separate review.

23. Patch discipline

Before writing a patch:

Identify the exact files involved.

Read the relevant current code.

Identify the applicable phase and specification.

Confirm the requested behavior fits the existing contract.

State blockers rather than guessing.

After writing a patch:

Keep the change minimal.

Preserve existing behavior outside the requested scope.

Provide exact verification commands.

Do not claim tests passed unless they actually ran.

Validate behavior against the relevant phase exit criteria.

24. Testing philosophy

Tests should exist at multiple levels:

Unit
  ↓
Analyzer / IR / generator logic

Integration
  ↓
Capture → analysis → generation

Browser
  ↓
Rendered behavior

Visual
  ↓
Original/flat reference vs generated output

Regression
  ↓
Previously validated sites

A build passing is not sufficient evidence of visual fidelity.

A screenshot looking close is not sufficient evidence of behavioral correctness.

Use the appropriate evidence for each claim.

25. Accuracy rules

WebExtractor must never invent evidence.

If the system cannot determine something reliably:

UNKNOWN

or an explicit diagnostic state is preferable to a fabricated value.

Examples:

Unknown animation duration
Unknown responsive rule
Unknown CMS structure
Unknown interaction behavior

The generator must not silently convert uncertainty into arbitrary CSS/JS.

This principle applies equally to development of WebExtractor itself: never claim a fix was verified until it was actually tested.

26. Explicit non-goals

Do not turn WebExtractor into:

an arbitrary CMS schema reconstruction engine

a backend/auth/payment replication system

an LLM-vision-based approximation generator

a blind auto-merging synchronization bot

a collection of project-specific hardcoded hacks

For CMS-backed content, distinguish static-copy extraction from real backend/CMS reconstruction.

For server-side behavior, flag what cannot be reconstructed from rendered evidence.

27. Current immediate objective

The immediate objective is not to add more reconstruction intelligence.

It is:

1. Establish Phase 0 flat export.
2. Produce a stable Porto ground-truth artifact.
3. Build Phase 1 screenshot validation.
4. Use measured evidence to complete Phase 2 Porto repair.
5. Then validate the IR against the real analyzer/generator.

Do not skip the phase gates.

Do not add responsive inference, sophisticated component deduplication, orchestration, or synchronization while the underlying single-page capture/reconstruction pipeline is not objectively validated.

28. End-state

The intended mature system is:

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
           │                       │
           └───────────┬───────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
          PASS                    FAIL
           │                       │
        PACKAGE            DIAGNOSE / REPAIR
                                   │
                                   └────→ VERIFICATION
```

Later:
source change → component hash → incremental regeneration → validation → PR

The defining principle remains:

Website → Browser Capture (DOM/CSS, Assets, Runtime) → Behavior Engine (Layout, States, Motion) → Site IR → Generators (Static, Dynamic) → Verification (Pixel & Behavioral Fidelity)

The system should become progressively more intelligent without becoming less deterministic.






CURRENT
  │
  ▼
1. Preserve Porto regression baseline
  │
  ▼
2. Static Fidelity Gate
  │
  ├── Assets
  ├── Structure
  ├── Geometry
  ├── Typography
  └── Responsive
  │
  ▼
3. Improve visual diff diagnostics
  │
  ▼
4. Validate / formalize Reconstruction IR
  │
  ▼
5. Component reconstruction + deduplication
  │
  ▼
6. Platform adapters
  │
  ├── Generic web
  ├── Framer
  ├── WordPress
  └── Other platforms as evidence requires
  │
  ▼
7. Interaction fidelity
  │
  ▼
8. Transition fidelity
  │
  ▼
9. Scroll / parallax fidelity
  │
  ▼
10. Sequencing / timing
  │
  ▼
11. Deterministic regeneration
  │
  ▼
12. Repair loop
  │
  ▼
13. Continuous synchronization