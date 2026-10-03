PHASE 1b — Close evidence gaps and fix regressions in Phase 1. Scope: same files as Phase 1 plus tests. No new features.

1. REPRODUCE (no code changes): run the full pipeline on samples/har/porto-rehost-full.har into a fresh dir. Using Playwright against the generated NEXT app (pnpm build + start, not the static HTML):
   a) with MotionRuntime ENABLED at the pre-Phase-1 commit (git stash or checkout): per-element visibility (opacity>0, size>0) at 1440 and 375, plus console errors;
   b) same with MotionRuntime REMOVED.
   Report a table of counts of invisible elements for (a) and (b). If (a) has no invisible elements, state that the symptom is NOT reproduced and stop.

2. FIX regressions:
   - MotionRuntime: remove the unconditional 3000ms force-visible timer. If a safety net is needed, apply it only to elements whose reveal did not fire AND that are currently intersecting the viewport. Restore original non-`once` reset behavior. Below-fold elements must stay hidden until scrolled into view.
   - Confirm the triggers.forEach loop also respects boundElements; show the code.
   - Dedup at the IR level: an element carrying both data-framer-appear-id and data-motion-id must resolve to ONE motion key. Define and document precedence.
   - Replace substring matching in _targets_overlap and in the standard adapter's claimed_targets with exact matching on normalized selectors or ids.
   - Standard adapter can_handle: gate on real evidence (an @keyframes rule, or transition/animation declarations on elements that are not purely hover/focus utility rules). Drop the timestamp regex or justify it with a test.
   - Adapter attribution: add a `name` attribute on each adapter class; stop deriving it from the class-name string; remove the "or 'framer'" default.
   - Revert the `dur_val > 0` and the invented 0.6 default unless a test proves they are needed; if kept, document why.

3. TESTS: replace string-grep tests with a Playwright behavioral test on a small fixture page: elements below the fold stay hidden until scrolled, then end visible; no element is animated twice; reduced to one binding per node. Keep all existing tests.

4. RE-RUN the full pipeline on Porto and report the real before/after per-viewport scores and invisible-element counts from the pipeline outputs, not hand-regenerated files.

OUTPUT: reproduction table, diffs, git diff --stat, test counts, before/after scores. STOP after Phase 1b.