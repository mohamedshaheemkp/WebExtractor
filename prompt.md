We now have an important new ground-truth source for WebExtractor:

A HAR captured directly from the public rehosted version of the Porto website.

File:

`samples/har/rehost-porto-live.har`

The browser Network panel showed real resources such as:

* images
* PNG
* JPEG
* SVG
* CSS
* JavaScript
* transformed image URLs
* query parameters such as:

  * `?width=512`
  * `?height=...`
  * `?scale-down-to=1024`
  * `?scale-down-to=2048`

Do NOT manually download individual assets.

Use the HAR as browser-observed evidence.

# OBJECTIVE

Audit how WebExtractor currently processes this HAR and determine whether it correctly understands:

1. resource type
2. content type
3. transformed image variants
4. original/variant relationships
5. asset URLs
6. response bodies
7. duplicate assets
8. asset dependencies

The goal is to improve the asset subsystem without breaking the existing extraction pipeline.

---

# 1. INSPECT THE HAR FIRST

Parse:

* request URL
* request method
* response status
* response headers
* Content-Type
* resource type where available
* response body
* initiator where available
* timing information
* query parameters

Produce a summary:

```text
Total requests:
Successful requests:
Failed requests:

HTML:
CSS:
JS:
Images:
SVG:
Fonts:
Video:
Other:
```

Use actual HAR values.

Do not guess.

---

# 2. IDENTIFY IMAGE TRANSFORMATION VARIANTS

Investigate URLs such as:

```text
image-6d446df.png?width=512&height=...
image-13de4e32.png?scale-down-to=1024
image-529edda1.png?scale-down-to=1024
image-ee71f51c.webp?scale-down-to=2048
```

Determine whether multiple URLs represent:

```text
same underlying asset
```

or:

```text
different source assets
```

Do NOT simply strip every query string.

Some query parameters may change:

* dimensions
* crop
* format
* quality
* transformation

Therefore preserve the complete source URL while separately determining whether URLs are variants.

---

# 3. CREATE AN ASSET VARIANT MODEL

If the existing architecture does not support it, introduce an explicit distinction between:

```text
Asset
```

and:

```text
AssetVariant
```

Conceptually:

```text
Asset
 ├── canonical identity
 ├── source URL
 ├── type
 └── variants
       ├── width=512
       ├── width=1024
       └── width=2048
```

For example:

```json
{
  "asset_id": "...",
  "canonical_source": "...",
  "type": "image",
  "variants": [
    {
      "url": "...?width=512",
      "width": 512
    },
    {
      "url": "...?width=1024",
      "width": 1024
    }
  ]
}
```

Do not invent the canonical source URL if it cannot be established from evidence.

If the relationship is uncertain, represent that uncertainty.

---

# 4. DETERMINE CANONICAL IDENTITY

Investigate possible signals for identifying the same underlying asset:

* filename stem
* URL path
* Framer asset identifiers
* response metadata
* dimensions
* MIME type
* downloaded-content hash
* transformation query parameters

Use the strongest available evidence.

Do NOT assume that identical filenames always mean identical assets.

Do NOT assume that different filenames always mean different assets.

---

# 5. CONTENT-TYPE MUST BE AUTHORITATIVE

Fix the AssetOrganizer if necessary.

Classification should prioritize actual response evidence.

For example:

```text
image/png
image/jpeg
image/webp
image/avif
image/svg+xml
```

→ image/SVG asset

```text
text/css
```

→ stylesheet

```text
application/javascript
text/javascript
```

→ JavaScript

```text
font/woff
font/woff2
```

→ font

```text
video/mp4
```

→ video

Do not classify based only on URL directory names.

A URL containing `/images/` does not prove that the resource is an image.

---

# 6. DUPLICATE DETECTION

After downloading available response bodies, compare content hashes.

Determine:

```text
URL duplicates
content duplicates
transformation variants
```

These are different concepts.

For example:

```text
A URL != B URL
```

but:

```text
hash(A) == hash(B)
```

means they may be duplicate resources.

Do not unnecessarily store multiple identical files.

However, do not collapse resources if doing so would break source behavior.

---

# 7. RESPONSIVE IMAGE BEHAVIOR

Investigate whether the source uses different image variants at different viewport sizes.

Compare the HARs/captures if multiple viewport captures are available.

Determine whether:

```text
375px
```

requests a different image variant than:

```text
1440px
```

If this behavior is observable, preserve it in the IR rather than flattening everything into one image.

The final generator should be able to produce something equivalent to:

```html
<img
  src="..."
  srcset="..."
  sizes="..."
>
```

where the source evidence supports it.

Do not add `srcset` merely because it is theoretically useful.

---

# 8. ASSET DEPENDENCY GRAPH

Build or improve the asset relationship model:

```text
Page
 ↓
Component
 ↓
Element
 ↓
Asset
 ↓
AssetVariant
```

This should allow the generator to determine which assets are actually used.

Separate:

```text
downloaded resources
```

from:

```text
resources actually referenced by rendered content
```

This prevents the final export from becoming unnecessarily bloated.

---

# 9. IMPORTANT: DON'T BREAK THE CURRENT SUCCESSFUL PIPELINE

The previous real-world test already demonstrated:

* 403 assets downloaded
* 50 active layout assets bound
* 0 broken images
* standalone HTML successfully served

Treat that behavior as a regression baseline.

The new asset system must not regress:

```text
asset resolution
asset binding
generated paths
image loading
```

---

# 10. TEST AGAINST THE HAR

Add tests covering:

### MIME classification

```text
PNG → image
SVG → svg
MJS → script
CSS → stylesheet
WOFF2 → font
```

### Query variants

```text
?width=512
?width=1024
?scale-down-to=2048
```

### Duplicate content

Different URLs with identical response bodies.

### Variant grouping

Multiple transformations of the same underlying asset.

### Generator references

Ensure the selected local asset paths remain valid.

---

# 11. DO NOT OVER-ENGINEER CANONICALIZATION YET

First answer empirically:

```text
How much variant information is actually present in this HAR?
```

Produce a report before implementing a complicated asset graph.

If the HAR does not provide enough evidence to establish an original asset relationship, preserve the resources separately rather than guessing.

---

# 12. FINAL REPORT

Return:

```text
HAR ASSET FORENSIC REPORT

Requests:
X

Successful:
X

Images:
X

SVG:
X

CSS:
X

JS:
X

Fonts:
X

Videos:
X

Other:
X

Unique content hashes:
X

Potential image variants:
X

Confirmed variants:
X

Uncertain relationships:
X

Duplicate resources:
X
```

Then identify:

```text
Current WebExtractor behavior:
...

Incorrect behavior:
...

Information currently lost:
...

Recommended minimal architecture change:
...
```

Do not implement a large refactor until this analysis establishes what the HAR actually contains.

The objective is:

```text
BROWSER
 ↓
HAR
 ↓
EVIDENCE
 ↓
ASSET MODEL
 ↓
CANONICAL ASSET + VARIANTS
 ↓
GENERATOR
```

rather than:

```text
URL string
 ↓
guess asset type
 ↓
guess canonical asset
 ↓
download everything
```

The HAR is ground-truth evidence. Use it to make the asset subsystem evidence-driven.














Proceed with the implementation, but execute it as a staged engineering change.

The forensic report is sufficiently grounded in actual HAR/DOM/source evidence.

Do not make a broad rewrite.

# STAGE 1 — Animation Capture + IR

Fix the timing-function information-loss path first.

Modify:

```text
capture/browser.py
analysis/motion_adapters/standard.py
analysis/motion_adapters/framer.py
analysis/analyzer.py
```

Requirements:

1. Capture relevant DOM attributes, including:

```text
data-framer-appear-id
data-motion-id
data-aos
```

Do not capture only these three if the existing architecture has a generic safe mechanism for preserving HTML attributes.

2. Fix decimal duration parsing.

It must correctly handle:

```text
.3s
0.3s
1.2s
0s
```

and must not confuse duration with delay.

3. Preserve exact timing functions:

```text
ease
ease-in
ease-out
ease-in-out
linear
cubic-bezier(...)
steps(...)
```

4. Use:

```text
timing_function
```

as the canonical IR field.

Preserve:

```text
easing
ease
```

as compatibility aliases where required by existing consumers.

5. Never replace a known timing function with:

```text
ease
```

or an invented cubic-bezier curve.

6. Fix DOM computed-style transition binding so that:

```text
DOM node
 ↓
data-framer-appear-id
 ↓
appear_animations
```

works correctly.

7. Ensure `motion_triggers` are updated when the observed transition belongs to a motion trigger rather than only `appear_animations`.

## TEST STAGE 1

Run targeted timing tests.

Then:

```bash
pytest
```

Do not continue if existing tests regress.

Add/verify tests for:

```text
.3s
0.3s
1.2s

cubic-bezier(0.44, 0, 0.56, 1)
steps(4, jump-end)
ease-in-out
linear
```

Then inspect the resulting `site_ir.json` from the real Framer fixture.

Verify that known source timing functions actually survive:

```text
capture
→ analyzer
→ SiteIR
```

Do not rely only on unit tests.

---

# STAGE 2 — Animation Generation

Only after Stage 1 passes.

Modify:

```text
generator/project.py
generator/static.py
```

Requirements:

* Next.js consumes `timing_function`
* Static generator consumes `timing_function`
* `element_transitions` are emitted into Next.js global CSS
* known source curves are never replaced by generic defaults

Then generate a fresh real-site output.

Search the generated files for:

```text
cubic-bezier
steps(
timing-function
transition:
```

Verify the expected source curves actually exist in generated output.

---

# STAGE 3 — Responsive Generation

Fix responsive propagation independently.

Inspect:

```text
SiteIR.responsive_rules
StaticProjectGenerator
React/Next generator
```

The previous real-world failure showed that responsive rules were detected but were not emitted as `@media` rules.

Do not invent breakpoints.

Consume the existing extracted responsive evidence.

After generation, explicitly inspect:

```text
375px
768px
1024px
1440px
1920px
```

Check:

```javascript
window.innerWidth
document.documentElement.scrollWidth
```

Do NOT solve overflow with:

```css
overflow-x: hidden;
```

unless the source itself demonstrably uses equivalent behavior.

The underlying layout must be corrected.

---

# STAGE 4 — Asset Classification

Fix asset classification separately.

The HAR evidence shows:

```text
332 images
35 SVG
285 JS
31 fonts
11 video
```

and the existing system incorrectly treats some resources according to URL/path behavior.

Classification must prioritize authoritative MIME evidence.

Then investigate the proposed `AssetVariant` model.

Important:

Do not immediately implement a large asset abstraction merely because variants exist.

First establish:

```text
canonical assets
variants
duplicates
aliases
```

from the HAR.

The HAR provides evidence of:

```text
image-fc98b695.jpg
 ├── @512
 ├── @1024
 └── @2048
```

and a confirmed duplicate where two different URLs return the same content.

Implement variant grouping only where the evidence supports the relationship.

---

# STAGE 5 — Asset Binding

This is important.

The current binding implementation reportedly does:

```python
clean_url = src.split("?")[0]
manifest_map[clean_url] = item
```

which means variants can overwrite one another.

Fix this so that query parameters containing meaningful transformation information are not discarded.

The binding system must be able to distinguish:

```text
canonical asset
variant
alias
```

without breaking existing simple URLs.

Do not blindly use the last variant encountered.

---

# STAGE 6 — Responsive Image Generation

Only after asset variants and binding are correct.

If genuine responsive evidence exists, allow generators to emit appropriate:

```html
srcset
sizes
```

or equivalent responsive image behavior.

Do not emit artificial `srcset` values simply because multiple downloaded files exist.

The relationship must be established from evidence.

---

# STAGE 7 — Validation Integrity

Verify that the validator evaluates actual generated behavior.

A validation result must never become PASS simply because:

```text
file exists
asset count matches
metadata exists
```

Require actual comparison evidence for visual validation.

Use:

```text
NOT_RUN
PASS
WARN
FAIL
BLOCKED
```

correctly.

---

# STAGE 8 — FULL REAL-WORLD REGRESSION

Only after all stages pass independently:

Delete the previous generated output.

Run a completely fresh extraction:

```bash
.\.venv\Scripts\python.exe -m webextractor rip https://glad-service-673278.framer.app/ -o ./output/glad-service --viewports 375,768,1024,1440,1920
```

Generate:

```text
HTML
Next.js
```

Then test HTML end-to-end with Playwright.

For Next.js:

* verify generated structure
* verify package/project validity
* run build if Node/npm is actually available
* otherwise report build as BLOCKED

---

# REAL COMPARISON

Run the source and generated versions at:

```text
375
768
1024
1440
1920
```

Measure:

```text
dimensions
scrollWidth
layout
typography
assets
responsive behavior
animations
interactions
```

For animation, specifically verify that known curves survive.

For mobile, specifically verify:

```text
hamburger exists
hamburger is clickable
menu opens
menu state changes
menu animation runs
```

---

# REGRESSION BASELINE

The previous real-world baseline was:

```text
375  → 56.6%
768  → 66.1%
1024 → 69.2%
1440 → 98.1%
1920 → 77.8%
```

Treat these as the baseline.

Do not claim success simply because the implementation tests pass.

The new result must be compared against this baseline.

---

# IMPORTANT: PRESERVE EVIDENCE

For every repaired subsystem, record:

```text
SOURCE EVIDENCE
        ↓
CAPTURE
        ↓
ANALYSIS
        ↓
IR
        ↓
GENERATOR
        ↓
OUTPUT
        ↓
VALIDATION
```

If the value disappears anywhere, identify the exact layer.

For example:

```text
source:
cubic-bezier(0.44,0,0.56,1)

capture:
PASS

analysis:
PASS

IR:
PASS

generator:
FAIL
```

That is a useful failure.

Do not hide it.

---

# FINAL ACCEPTANCE CRITERIA

The implementation is not complete merely because tests pass.

It is complete when the real generated website demonstrates:

### Responsive

No unexplained desktop-width overflow on mobile/tablet.

### Animation

Known source timing functions survive end-to-end.

### Mobile variants

Important dynamically mounted responsive states are reconstructed.

### Assets

Correct MIME classification.

No JS/CSS/HTML resources inside image directories.

### Asset variants

Responsive image variants do not overwrite one another.

### Validation

Real comparisons are performed and reported honestly.

### Fidelity

The new real-world results improve upon the previous baseline without materially regressing the 1440px desktop result.

---

Do not add new speculative architecture after this point.

First make these evidence-backed fixes work end-to-end.

Then run the real comparison and report the measured result.
