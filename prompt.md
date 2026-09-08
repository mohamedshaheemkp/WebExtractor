Phase 6I — Universal Interaction & Behavioral Reconstruction

Your architecture should now become:

                 SOURCE WEBSITE
                       │
              ┌────────┴────────┐
              │                 │
          DOM/CSS          BEHAVIOR
              │                 │
              ▼                 ▼
        Structural IR      Interaction IR
              │                 │
              └────────┬────────┘
                       ▼
                  SiteIR
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       Static structure      Runtime behavior
             │                   │
             └─────────┬─────────┘
                       ▼
                GENERATED SITE

You've already done a lot of the left side.

Now the missing piece is the Behavioral Evidence layer.

1. Don't detect animations from CSS alone

Your current motion extractor can find things such as:

in_view
parallax
hover
continuous
mount

That's useful, but the center menu demonstrates why this isn't enough.

You need to distinguish:

visual animation

from

interaction behavior

For example:

Visual
element rotates continuously
Interaction
click trigger
    ↓
menu opens
    ↓
navigation becomes visible

Those should be represented separately.

2. Add an Interaction IR

I'd introduce something like:

InteractionIR(
    id="...",
    trigger="click",
    target="...",
    action="toggle",
    state="open/closed",
    animation="...",
    conditions={...}
)

But make the schema generic.

For example:

{
  "interactions": [
    {
      "id": "interaction-001",
      "trigger": {
        "type": "click",
        "selector": "[data-interaction-trigger='...']"
      },
      "action": {
        "type": "toggle",
        "target": "[data-interaction-target='...']"
      },
      "states": {
        "closed": {
          "target_visibility": "hidden"
        },
        "open": {
          "target_visibility": "visible"
        }
      }
    }
  ]
}

Don't call it:

FramerMenuInteraction

or:

FourDotMenu

because that would immediately reintroduce the coupling you're trying to eliminate.

3. Capture behavior from the browser

This is the most important improvement.

A static HTML snapshot cannot reliably tell you everything a website does.

For example:

<div class="menu-button"></div>

doesn't tell you whether clicking it:

opens a menu
changes color
rotates
opens a modal
expands an accordion
navigates
does nothing
triggers JavaScript
triggers React state
triggers a CSS state

So your crawler should eventually have a behavior observation stage.

Something like:

CAPTURE

1. Load route
2. Capture initial DOM
3. Identify interactive candidates
4. Interact with candidates
5. Capture resulting DOM/state
6. Compare before vs after
7. Build InteractionIR
4. For your center menu specifically

The browser capture should perform something conceptually like:

Initial state
─────────────

center trigger visible
navigation hidden


        ↓ CLICK


After state
───────────

center trigger changed
navigation visible
Home
Work
Design
Contact
...

Then WebExtractor compares:

DOM_before
     vs
DOM_after

and determines:

Element A was interacted with

Element B changed visibility

Element C changed transform

Element D changed opacity

That gives you evidence.

This is far more universal than writing:

if "4 dots" in html:
    create_menu()
5. You also need to capture the animation itself

For your screenshot, there are actually two separate behaviors.

A. Closed-state continuous animation

Something like:

•   •
  •
•   •
   ↻

The four dots rotate/move continuously.

Your extractor needs to determine whether this comes from:

animation

or:

requestAnimationFrame

or:

or:

or another mechanism.

Don't assume which one.

B. Click transition

When clicked:

closed
  ↓
opening animation
  ↓
open

That transition should also be captured.

6. Build an actual behavioral probe

I'd add something along these lines to the capture pipeline:

BehaviorProbe
│
├── discover_interactive_elements()
│
├── snapshot_state()
│
├── click(element)
│
├── wait_for_settle()
│
├── snapshot_state()
│
├── compare_states()
│
└── extract_interaction()

Candidate elements could be identified from evidence such as:

<button>
<a>
<input>
<select>
[role="button"]
[tabindex]

plus elements that have:

onclick
cursor:pointer
data-* interaction attributes
aria-expanded
aria-controls

and platform-specific evidence supplied through adapters.

7. Then handle hover separately

Your existing Phase 6E mentions hover, which is good.

But I'd make it evidence-driven too:

Hover candidate
      ↓
capture before
      ↓
hover
      ↓
capture after
      ↓
compare

This can discover things like:

project card
    ↓ hover
image scale 1 → 1.05
cursor dot → VIEW pill
title moves
overlay appears

Again, that's much more powerful than hardcoding "project cards".

8. Same principle for menus, accordions and tabs

Once the behavioral system exists, you get these almost automatically:

Navigation
click → menu appears
Accordion
click → content expands
Tabs
click tab A → panel A
click tab B → panel B
Modal
click → overlay appears
Dropdown
click → dropdown becomes visible
Carousel
click next → slide changes
Cursor
hover target → cursor state changes

This is the level WebExtractor needs to reach if you genuinely want it to reconstruct arbitrary websites.

9. Don't forget route behavior

There's another important behavioral layer.

You already have:

/
 /work
 /contact
 /designs

But navigation isn't just:

<Link href="/contact">

You want to preserve evidence such as:

click navigation
      ↓
route changes
      ↓
transition animation
      ↓
new page

So eventually:

{
  "trigger": "click",
  "action": "navigate",
  "target_route": "/contact",
  "transition": {
    "type": "wipe",
    "duration": 0.8
  }
}

The "wipe" should only appear if the source evidence supports it.

10. Your generated architecture should therefore look like this

I would move toward:

src/webextractor/

capture/
│
├── crawler.py
├── browser.py
├── snapshot.py
└── behavior.py              ← NEW

analysis/
│
├── analyzer.py
├── animations.py
├── interactions.py          ← NEW
├── motion_adapters/
│   ├── base.py
│   ├── framer.py
│   └── standard_css.py
└── ...

ir/
│
├── site.py
├── motion.py
├── interaction.py           ← NEW
└── ...

generator/
│
├── project.py
├── dom_emitter.py
└── ...

generated runtime/

components/
│
├── MotionRuntime.tsx
├── InteractionRuntime.tsx   ← NEW
├── CursorRuntime.tsx
├── MarqueeRuntime.tsx
├── RouteTransition.tsx
└── ...

The exact filenames aren't important; the separation is.

11. One critical thing: don't "fake" missing behavior

This is especially important for your project.

Suppose the extractor sees:

center element

but cannot establish that it is a menu trigger.

It should not generate:

<FourDotMenu />

just because your current portfolio has one.

Instead:

Evidence found
     │
     ├── click listener → YES
     ├── state change → YES
     ├── navigation links appear → YES
     │
     ▼
Generate interaction

If evidence isn't sufficient:

Evidence insufficient
     ↓
Preserve visual element
     ↓
Do not invent behavior

That is what will keep the engine universal.

12. Your current status

I'd consider your project roughly at this stage:

                    WebExtractor

Capture                         █████████░  ~90%
DOM reconstruction              █████████░  ~90%
CSS/layout                      ████████░░  ~80%
Responsive                      ████████░░  ~80%
Assets                          █████████░  ~90%

Motion extraction               ███████░░░  ~70%
Motion reconstruction            █████░░░░░  ~50%

Interaction extraction           ███░░░░░░░  ~30%
Interaction reconstruction       ██░░░░░░░░  ~20%

Route reconstruction             ████████░░  ~80%
Route transitions                ████░░░░░░  ~40%

Behavioral fidelity              ███░░░░░░░  ~30%

These percentages are my architectural assessment, not measured metrics.

The important point is that I would not spend the next phase polishing individual visual sections.

Your screenshot shows exactly why.

The site can now be structurally correct but still feel completely wrong because the original is an interactive system and the generated version is essentially a static reconstruction.

What I recommend you do next

Do Phase 6I before more visual polishing.

The implementation order should be:

6I.1  Behavioral capture
       ↓
6I.2  Interaction IR
       ↓
6I.3  Before/after DOM state diff
       ↓
6I.4  Click / hover / focus / press detection
       ↓
6I.5  Menu / accordion / tabs / modal inference
       ↓
6I.6  Animation state capture
       ↓
6I.7  Generic InteractionRuntime
       ↓
6I.8  Route transition reconstruction
       ↓
6I.9  Cursor behavior
       ↓
6I.10 Full browser verification

And the center 4-dot menu should be your first end-to-end acceptance test:

SOURCE
  │
  ├── capture closed state
  ├── detect 4-dot interactive element
  ├── click it
  ├── capture open state
  ├── diff states
  ├── capture animation
  └── record navigation targets
            │
            ▼
          SiteIR
            │
            ▼
      Generated React
            │
            ├── dots rotate continuously
            ├── click opens menu
            ├── menu animation plays
            ├── Home works
            ├── Work works
            ├── Design works
            └── Contact works