# WebExtractor — Intermediate Representation (IR) Schema

**Status: DRAFT.** This schema has not yet been validated against the actual
`analyzer.py` / `generator/project.py` internals — it reflects the design
discussed in planning sessions, not confirmed code structure. First task
against this doc: check where current analyzer output and generator input
already resemble/diverge from this shape, then revise this file before
writing patches against it. Do not treat any field below as already
implemented.

## Purpose

The IR is the contract between the analysis layer and the generation layer.
Analysis writes IR, generation reads IR — no direct passing of raw capture
data between them. This is what makes Porto's rendering bug diagnosable:
if generated output is wrong, check IR first (is the IR itself wrong?)
before assuming the generator is at fault, or vice versa.

Stored as versioned JSON per site, checked into the repo under
`test-runs/<site>/ir.json` (or a DB if this grows past flat-file scale —
not needed yet).

## Architectural Context — The WebExtractor Formula

The Site IR sits at the exact center of the WebExtractor pipeline, bridging the evidence collected by Browser Capture and interpreted by the Behavior Engine to the Static and Dynamic Generators:

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

## Top-level shape

```json
{
  "schemaVersion": "0.1.0",
  "site": {
    "sourceUrl": "string",
    "capturedAt": "ISO8601 timestamp",
    "breakpoints": [375, 768, 1024, 1440]
  },
  "pages": [ Page ],
  "components": [ Component ],
  "designTokens": DesignTokens,
  "assets": [ Asset ]
}
```

## Page

```json
{
  "route": "/about",
  "componentRefs": ["component-id-1", "component-id-2"],
  "meta": { "title": "string", "description": "string" }
}
```

## Component

```json
{
  "id": "stable-hash-of-domPath+classSignature",
  "domSignature": "tag+class path used for structural matching",
  "visualHash": "perceptual hash of subtree screenshot, for dedup",
  "variants": [
    { "variantId": "string", "props": {}, "domSignature": "..." }
  ],
  "styleTokens": {
    "// per-breakpoint style refs, pointing into designTokens where possible": ""
  },
  "breakpointRules": {
    "375": { "properties changed at this breakpoint vs base": {} },
    "768": {}
  },
  "animations": [
    {
      "trigger": "scroll | hover | focus | load",
      "type": "css-transition | css-keyframes | js-driven",
      "adapter": "which motion_adapter handles this — e.g. 'standard'",
      "timingFunction": "cubic-bezier(...)",
      "durationMs": 300
    }
  ],
  "children": ["child-component-id", "..."]
}
```

Open question (resolve before Phase 3 patches): how does this map onto
what `analyzer.py`'s current `appear_animations` merge step actually
produces? That merge is the suspected source of the Porto bug — confirm
its current output shape against this `animations` array before assuming
they already match.

## DesignTokens

```json
{
  "colors": { "token-name": "#hex" },
  "typography": {
    "token-name": { "fontFamily": "", "fontWeight": 0, "fontSize": "", "lineHeight": "", "letterSpacing": "" }
  },
  "spacing": { "token-name": "value" },
  "easings": { "token-name": "cubic-bezier(...)" }
}
```

Tokens are derived by clustering near-identical values across components
(discussed threshold-based approach) — clustering method/threshold not
yet specified, needs its own design pass before Phase 4.

## Asset

```json
{
  "id": "string",
  "originalUrl": "string",
  "type": "image | video | font",
  "localPath": "string, post-rewrite",
  "srcsetVariants": [{ "width": 0, "url": "" }]
}
```

## Versioning rule

Any change to this schema bumps `schemaVersion`. Generator and analyzer
should both assert on the version they were written against — mismatch
should fail loudly, not silently produce wrong output. This is a cheap
guard against exactly the kind of drift the two-tool (Claude/ChatGPT)
workflow risks introducing.

## Non-goals (explicitly out of scope for this schema)

- CMS content schema inference — flagged as "static-copy only" per prior
  discussion, not modeled here.
- Server-side logic / form handlers — not extractable from rendered
  output, not represented in IR.