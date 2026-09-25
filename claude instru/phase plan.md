# WebExtractor — Phase Plan

Read this doc + `IR_SCHEMA.md` + `PATCH_FORMAT.md` at the start of any
session (Claude or ChatGPT) instead of re-explaining project context
verbally. Update this file as phases complete or scope changes — it's
the standing source of truth, not a one-time plan.

## Role split

- **Claude**: architecture decisions, schema design, root-cause diagnosis
  on real bugs, review pass on batched ChatGPT patches.
- **ChatGPT**: patch-writing against an already-written spec (this doc +
  IR_SCHEMA.md + PATCH_FORMAT.md), routine/mechanical code, test
  boilerplate. Does not originate architecture — flags spec gaps instead
  of improvising around them.
- **Antigravity**: applies patches, runs test suite, reports pass/fail
  counts.

Batch ChatGPT-produced patches (3-5 at a time) before bringing them to
Claude for review — don't review one patch per message.

## Phase 0 — Flat-export mode
**Owner: Claude (patches), Antigravity (apply)**

Reuse existing `browser.py` / `crawler.py` capture. Add:
- Asset URL rewrite → local relative paths
- Framer-runtime stripping (analytics, watermark/license checks,
  edit-mode hooks, `framer.cloud` remote deps)
- Package as flat static bundle

**Exit criteria**: flat export of Porto renders correctly standalone,
no React involved. This becomes the ground-truth artifact for Phase 1.

**Status**: not started.

## Phase 1 — Validation loop (screenshot diff)
**Owner: Claude**

Pixel-diff harness (pixelmatch or odiff) comparing current React-generated
output against the Phase 0 flat export, per-component region diffing,
not full-page only. Threshold-gated flagging.

**Exit criteria**: harness runs against Porto, produces a diff report
identifying which components/regions diverge.

**Status**: not started. Blocks Phase 2.

## Phase 2 — Fix Porto rendering bug
**Owner: Claude**

Use Phase 1's diff report as evidence — trace root cause file:line before
patching, per existing diagnosis-loop practice. Suspected area (unconfirmed
until diff report exists): the `analyzer.py` reveal-animation merge into
`appear_animations` may be producing duplicate/conflicting entries.

**Exit criteria**: diff report shows near-zero divergence on Porto.

**Status**: blocked on Phase 1.

## Phase 3 — IR construction + component dedup
**Owner: Claude (schema validation + patches), ChatGPT (mechanical
codegen once schema is confirmed against real code)**

First: validate `IR_SCHEMA.md` against actual current `analyzer.py` /
`generator/project.py` output shapes — the schema doc is currently
speculative, not confirmed. Revise schema doc first, then patch analyzer
to emit IR and generator to consume it, replacing any direct
analyzer→generator coupling.

Component dedup: structural signature (tag+class path) + perceptual hash
of subtree screenshot, merge above similarity threshold (threshold value
TBD — needs its own design pass, not yet specified).

**Exit criteria**: analyzer and generator both operate through versioned
IR, verified via Phase 1's diff harness staying clean after the refactor.

**Status**: blocked on Phase 2.

## Phase 4 — Responsive inference + design tokens
**Owner: Claude**

Diff computed styles across the 4 captured breakpoints (375/768/1024/1440
per IR_SCHEMA.md `breakpoints`), infer which properties actually change,
emit media queries only for those. Cluster near-identical values into
`designTokens`.

**Exit criteria**: diff harness stays clean across all 4 breakpoints,
not just desktop.

**Status**: blocked on Phase 3.

## Phase 5 — Sync pipeline (continuous Framer → code)
**Owner: Claude**

Per-component hashing for change detection, deterministic regen (stable
IDs, sorted output, pinned float precision), generated/override split so
manual edits survive regen, poll→diff→PR flow (not auto-merge), config
layer (`webextractor.config.yaml`) for multi-project reuse.

**Exit criteria**: a design change in Framer produces a PR with a
component-scoped diff and attached screenshot-diff review artifact,
without touching manually-edited files.

**Status**: blocked on Phase 4.

## Explicitly out of scope (do not attempt)

- CMS schema reconstruction for arbitrary third-party sites.
- Server-side logic replication (forms, auth, payment flows).
- LLM-vision-based regeneration as a fidelity strategy (evaluated and
  rejected — see AIDesigner comparison; approximation-based, not
  verifiable against computed values).