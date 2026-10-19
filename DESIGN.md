---
name: TariffTrail
description: A metro route map fused with a station departure board, drawn in white line on enamel-blue signage, where every Decider fork is an interchange and the chosen tariff route lights signal yellow.
colors:
  signal-yellow: "#ffd21a"
  signal-yellow-hover: "#ffdd4d"
  signal-ink: "#191400"
  vermilion: "#ff7a5f"
  enamel: "#102f86"
  deep-enamel: "#0b2260"
  deepest-enamel: "#081a4a"
  station-white: "#f6f8ff"
  station-white-dim: "rgb(246 248 255 / 0.78)"
  station-white-faint: "rgb(246 248 255 / 0.2)"
  station-white-hair: "rgb(246 248 255 / 0.14)"
  flap-upper: "#12306f"
  flap-seam: "#040d2a"
  flap-lower: "#0f2864"
typography:
  display:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "clamp(30px, 3.6vw, 52px)"
    fontWeight: 800
    lineHeight: 1.02
    letterSpacing: "-0.025em"
  wordmark:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.005em"
  body:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
  body-lead:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "16.5px"
    fontWeight: 400
    lineHeight: 1.5
  field:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.45
  note:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
  route-label:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.2
  button:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1
  action:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1
  sign:
    fontFamily: "Overpass, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.1em"
  flap-digit:
    fontFamily: "'Overpass Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace"
    fontSize: "clamp(30px, 4.2cqi, 48px)"
    fontWeight: 700
    lineHeight: 1
    fontFeature: '"tnum"'
  metric:
    fontFamily: "'Overpass Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  readout:
    fontFamily: "'Overpass Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace"
    fontSize: "13px"
    fontWeight: 600
    letterSpacing: "0.01em"
rounded:
  control: "6px"
  tile: "5px"
  circle: "50%"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  gutter: "22px"
  board: "30px"
components:
  rail:
    backgroundColor: "{colors.deep-enamel}"
    textColor: "{colors.station-white}"
    typography: "{typography.body}"
    padding: "20px 22px 16px"
    width: "372px"
  button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signal-ink}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "14px 16px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.signal-yellow-hover}"
  button-primary-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.station-white-dim}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.station-white}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "11px 15px"
  button-secondary-hover:
    backgroundColor: "rgb(246 248 255 / 0.07)"
  button-sample:
    backgroundColor: "transparent"
    textColor: "{colors.station-white}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "7px 11px 7px 38px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.station-white-dim}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  button-quiet-pressed:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signal-ink}"
  field:
    backgroundColor: "{colors.deepest-enamel}"
    textColor: "{colors.station-white}"
    typography: "{typography.field}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  status-pill:
    backgroundColor: "transparent"
    textColor: "{colors.station-white-dim}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 12px 6px 10px"
  status-pill-live:
    textColor: "{colors.station-white}"
  sign-fast-track:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signal-ink}"
    typography: "{typography.sign}"
    rounded: "{rounded.control}"
    padding: "11px 16px"
  sign-heading-agreed:
    backgroundColor: "transparent"
    textColor: "{colors.signal-yellow}"
    typography: "{typography.sign}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  sign-broker-review:
    backgroundColor: "transparent"
    textColor: "{colors.vermilion}"
    typography: "{typography.sign}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  sign-idle:
    backgroundColor: "transparent"
    textColor: "{colors.station-white-dim}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  digit-tile:
    backgroundColor: "{colors.flap-upper}"
    textColor: "{colors.station-white}"
    typography: "{typography.flap-digit}"
    rounded: "{rounded.tile}"
    width: "0.78em"
    height: "1.22em"
  digit-tile-rolling:
    textColor: "{colors.signal-yellow}"
  route-plaque:
    backgroundColor: "{colors.station-white}"
    textColor: "{colors.enamel}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    width: "240px"
    height: "66px"
  map-key:
    backgroundColor: "{colors.deep-enamel}"
    textColor: "{colors.station-white}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  board:
    backgroundColor: "{colors.deepest-enamel}"
    textColor: "{colors.station-white}"
    padding: "22px 26px 16px"
---

# Design System: TariffTrail

## Overview

**Creative North Star: "The Enamel Station"**

TariffTrail is drawn as the signage of a metro station. A navy enamel field carries a single white route line; every Decider call is an interchange ring on that line, every option is a branch whose stub is as long as it is likely, and the foot of the screen is a departure board that rolls out the destination code. The whole interface is the answer to one question: where did this product end up on the tariff tree, and how did it get there. It reads as civic wayfinding, not software chrome: plain, evidence-first, no hype.

The palette is three navy grounds, one structural white, and exactly two signals. Yellow means the system's chosen route and the one thing to press. Vermilion means "none of these" and every place where sources disagree and a broker must look. Nothing else is allowed to carry color, so a glance at the screen already says which parts are decided and which are doubtful. The surface is deliberately flat: no outer shadows, depth is made by stepping between navy grounds and by inset keylines on signs. The confirmed rejection is the default SaaS arrangement of a form card beside an accordion of probability bars.

**Key Characteristics:**
- White line on navy: one structural ink, stepped down through a short ladder of opacities, on three tonal grounds.
- Two signals only: signal yellow for the lit route and the primary action, vermilion for none-of-these, disagreement and broker review.
- Signage type: Overpass for sentences and signs, Overpass Mono for every code, percentage, latency and count.
- 6px corners on rectangular controls and signs, true circles for rings, lamps and marks, split-flap tiles for digits.
- Flat and keylined: no offset or blurred shadows; framed signs use a gap-ring keyline.
- Motion draws the route and rolls the digits, then gets out of the way; everything stops under reduced-motion.

## Colors

A deep ultramarine enamel palette with white as the only line color and two warm signals that appear only when the system has made, or failed to make, a decision.

### Primary
- **Signal Yellow** (#ffd21a): The chosen route and everything that is "lit": the route sweep after a result, lit interchange fills, the primary action button, the live-status lamp, the TariffTrail bar on the bench, the fast-track sign, text selection, and the focus outline. Its hover is a lighter **Signal Yellow Hover** (#ffdd4d), used on the primary button only.
- **Signal Ink** (#191400): The near-black warm ink that sits on every yellow fill. Text on yellow is always this, never white.

### Secondary
- **Vermilion** (#ff7a5f): A light, warm coral-vermilion for the "none of these" dotted branch and its cross cap, the broker-review sign, a source row that disagrees, a "different" gold-standard readout, and error states. On the enamel map it reads at 4.6:1, on the darker grounds above 5.8:1.

### Neutral
- **Enamel** (#102f86): The map ground, the stage bar, the interchange ring fill, and the halo behind map labels. The brightest ground on screen.
- **Deep Enamel** (#0b2260): The left rail, the page background, and the map key panel (at 92 percent opacity).
- **Deepest Enamel** (#081a4a): Instrument surfaces: the destination board, text fields and select menus.
- **Station White** (#f6f8ff): All structural ink: route lines, ring strokes, headings, body text, the plaque fill. Never pure white.
- **Station White Dim** (78 percent): Secondary text, notes, option labels not on the route. 7.4:1 on enamel.
- **Station White Faint** (20 percent): Dashed "waiting" frames and scrollbar thumbs. The shipped build also uses it as the resting edge of outline buttons, fields and the status pill; at 1.8:1 on its ground that edge is below the 3:1 floor for control boundaries, so it is a carried defect, not a pattern for new controls (see Do's and Don'ts).
- **Station White Hair** (14 percent): Dividers, panel edges and the perforated strip on top of the board.
- **Flap Upper / Flap Seam / Flap Lower** (#12306f / #040d2a / #0f2864): The three stops of the split-flap tile: lit upper half, the dark seam, slightly deeper lower half.

### Named Rules
**The Two Signals Rule.** Yellow and vermilion are the only hues allowed to mean something. There is no green for success, no blue for links, no amber for warning. A third signal would dilute the first two.

**The Earned Yellow Rule.** On the map, the chosen branch stays white until the result resolves the path; only then does yellow sweep along it, fork by fork. Yellow is a conclusion, not a highlight.

**The White Line Rule.** Every structural element is Station White at one rung of its opacity ladder. Abandoned branches go white at 60 percent, then fade to 30 percent once the result lands. They never take an accent color.

## Typography

**Display Font:** Overpass (with Segoe UI, system-ui, sans-serif)
**Body Font:** Overpass (same stack)
**Label/Mono Font:** Overpass Mono (with ui-monospace, Cascadia Mono, Consolas, monospace)

**Character:** Highway-gothic voice: Overpass is an open-source take on the US highway sign face, so it reads like a sign at every weight. Overpass Mono sets everything a broker could copy or audit, so codes and numbers look like they belong to a different, more exact register than the sentences around them.

### Hierarchy
- **Display** (800, clamp(30px, 3.6vw, 52px), 1.02, -0.025em): The empty-state headline "Your route appears here." and nothing else.
- **Wordmark** (800, 30px, 1, -0.02em): "TariffTrail" in the rail, beside the roundel.
- **Headline** (700, 15px, 1.2): Rail section heads ("Describe the product", "How it scores").
- **Body** (400, 15px, 1.45): Page default. Lead paragraphs in the empty state step up to 16.5px / 1.5, held to about 48 characters.
- **Field** (400, 14.5px, 1.45): Text in the product textarea and the replay select.
- **Note** (400, 13px, 1.45, Station White Dim): Helper copy at 13px; bench subtext and the footer step down to 12px.
- **Label** (600, 13px): Status-pill text, sample chips, quiet buttons (12.5px) and the board's "Destination" label (in Station White Dim).
- **Route label** (400, 15px, 1.2): Option names beside map branches; 600 and full white for the option taken, 600 vermilion for none-of-these, 600 yellow for the lit route. Clamped to two lines.
- **Button** (700, 14px, 1): Default buttons. The primary action steps up to 15px.
- **Sign** (800, 14px, 1, 0.1em, uppercase): The review-tier sign only.
- **Flap digit** (Mono 700, clamp(30px, 4.2cqi, 48px), 1, tabular figures): The 10-digit destination code, one tile per digit.
- **Metric** (Mono 700, 18px, 1.1): Values in the board's metrics strip, with the 13px label after the value.
- **Readout** (Mono 600, 13px, 0.01em): The ticker ("18 Decider calls · 61.2 s"), the gold-standard line, source-row values. Route codes and percentages on the map are Mono at 14px (700 for percentages, 500 for codes); ring numbers 700 at 12px.

### Named Rules
**The Two Registers Rule.** Sentences are Overpass; anything numeric or code-like is Overpass Mono. Never set a code in the sans or a sentence in the mono.

**The Sign-Case Rule.** Uppercase with wide tracking belongs to the tier sign alone. Every other label is sentence case.

## Layout

A fixed two-pane instrument: a 372px control rail on the left and a fluid stage on the right, filling 100dvh (minimum 640px). The rail is a single scrolling column with an 18px gap between sections and 22px side padding: wordmark and roundel, status pill, product field with sample chips and the primary action, the replay row (select plus button), the four-bar bench, and a hairline-topped footer. The stage is three stacked rows: a stage bar (ticker, Fit route toggle, and, in replay, a one-line recorded-run notice), the map taking all remaining height, and the destination board docked full-width at the foot (minimum 15.5rem).

The map is a pannable canvas on a 28px dot grid (Station White at 12 percent). Geometry is fixed: 56px per option row, 470px between forks, a 13px interchange ring, 6px route stroke (7px lit), and a 240 by 66px product plaque at the left edge with the route leaving it. The map key floats bottom-left over the grid. The board is a three-column grid (destination tiles, tier sign and note, sources) with the metrics strip and the path/reason row spanning beneath.

Spacing is hand-set rather than a strict scale. The recurring steps are 6, 8, 12, 18, 22 and 30px; panels pad 20 to 26px, controls pad 10 to 14px.

Responsive behavior: when the stage container is 1080px or narrower, the board drops to two columns and the sources become an auto-fit row. At 800px of viewport height or less, the breadcrumb chain hides, reasons clamp to two lines and the board tightens. At 920px or narrower the app becomes a single column with the rail dissolved into the page flow (brand, status, controls, then the stage, then the bench), the map at 62dvh with a 380px minimum, and the board as one column. At 520px the replay row stacks.

## Elevation & Depth

Flat by construction. There are no drop shadows, no blurs and no gloss. Depth comes from tonal grounds: the map is the brightest navy (Enamel), the rail and page sit one step darker (Deep Enamel), and instruments that carry data (the board, fields) sit darkest (Deepest Enamel), separated from neighbors by 14 percent hairlines. Signs get their weight from inset keylines, a ring of the ground color cut between two lines, like enameled plates.

Map labels are lifted off the lines they cross by a 5px Enamel text halo, not a box. The only translucency is the map key panel at 92 percent Deep Enamel.

### Shadow Vocabulary
- **Plaque keyline** (`box-shadow: inset 0 0 0 3px #f6f8ff, inset 0 0 0 4.5px #102f86`): The white product plaque's inner frame.
- **Fast-track keyline** (`box-shadow: inset 0 0 0 2px #ffd21a, inset 0 0 0 3.5px #191400`): A gap-ring of ink inside the yellow sign.
- **Review keyline** (`box-shadow: inset 0 0 0 2px #081a4a, inset 0 0 0 3px #ff7a5f`, over a 2px vermilion border): The doubled outline of the broker-review sign.
- **Tile bevel** (`box-shadow: inset 0 0 0 1px rgb(246 248 255 / 0.1)`): A hairline edge on each split-flap tile.
- **Focus halo** (`box-shadow: 0 0 0 3px rgb(255 210 26 / 0.2)`): Added to a focused field beside its yellow border.
- **Live pulse** (`box-shadow` animating from `0 0 0 0` to `0 0 0 9px` at 55 percent to 0 percent yellow, 2.4s): The live-status lamp only.

### Named Rules
**The Keyline Rule.** Signs are framed with an inset gap-ring, never an outer shadow. A new framed element copies one of the keylines above.

**The Brightest-Field Rule.** The map is the lightest ground on screen; anything that reads out data sits on a darker one. Do not lighten a panel to make it stand out.

**The Knockout Rule.** Text over a line is cut out of the line with an Enamel halo; it is never put in a filled chip.

## Shapes

Two forms only: 6px-radius rectangles and perfect circles. Every rectangular control, field, sign, plaque, status pill and the map key uses the 6px corner; split-flap digit tiles use a slightly tighter 5px. Interchange rings, status lamps, source marks and the sample-chip badge are circles drawn with strokes 3 to 4px thick. Lines are round-capped with round joins and bend only at 45 degrees, in the manner of an octilinear transit diagram: route stubs end in a short vertical bar, "none of these" ends in a cross.

Borders are 1px hairlines for containers and controls, 2px for emphasized signs. Dashes carry a meaning: a dashed border or ring means not yet, unavailable or pending (the idle sign, a disabled primary action, a pending interchange); a dotted line means none-of-these.

## Components

### Buttons
- **Shape:** 6px corners, 1px border, 700-weight Overpass at 14px.
- **Primary:** Full-width Signal Yellow with Signal Ink text, 15px, padding 14px 16px. One per screen: "Classify live". Hover lightens to #ffdd4d. When disabled (Decider offline) it drops to a transparent fill, Station White Dim text and a dashed 20 percent border; while a run is in flight it holds yellow at 70 percent opacity with a progress cursor. In offline mode the Replay button takes the primary look instead.
- **Secondary:** Transparent fill, Station White text, 20 percent border, padding 11px 15px. Hover brightens the border to full white and tints the fill at 7 percent. Active presses down 1px and scales to 98.5 percent.
- **Quiet toggle:** Smaller (12.5px, 600, padding 6px 10px) in Station White Dim; when pressed it fills yellow with ink text. Used for "Fit route / Actual size".
- **Sample chip:** A line-badge. A 15px white-stroked circle sits on a short yellow bar, like a station on a line, set in the left 38px of a 13px, 600-weight button.

### Fields
- **Style:** Deepest Enamel fill, Station White text at 14.5px, 1px 20 percent border, 6px corners, padding 10px 12px. The select swaps its native arrow for a white chevron at the right.
- **Hover / Focus:** Hover lifts the border to 40 percent white. Focus switches the border to Signal Yellow with a 3px translucent yellow halo. Placeholder text is 62 percent white (6.7:1 on the field).

### Status pill
- **Style:** Inline pill with a 10px circular lamp: hollow white ring when offline, solid yellow with a slow pulse when the Decider is live (border and text brighten, border goes to 60 percent yellow). Text is 13px, 600.

### Tier signs
The review tier is shown as an enamel sign, uppercase and tracked, that stamps in with a slight overshoot and a -1.5 degree settle.
- **Fast-track review:** Signal Yellow fill, Signal Ink text, ink keyline. The one sign that earns yellow.
- **Heading agreed:** Transparent with a doubled Signal Yellow outline and Signal Yellow text. Hollow, so it reads as partial agreement; only fast-track gets the filled yellow sign.
- **Broker review:** Transparent with a doubled Vermilion outline and Vermilion text.
- **Idle:** "Awaiting a run": dashed 20 percent outline, sentence case, no uppercase. Error: vermilion outline, sentence case.
- Beside each sign sits one 14px sentence of plain explanation in Station White Dim, held to about 40 characters wide.

### Destination board (signature)
A departure-board readout of the 10-digit HTS code as individual split-flap tiles: each digit sits in a 0.78em by 1.22em tile with a lit upper half, a dark seam across the middle and a slightly deeper lower half. Dots between groups are 9px Station White circles, not characters. At rest the tiles show dashes at 40 percent white; on a result each tile rolls through six random digits (55ms steps, 80ms stagger left to right) in yellow, then lands white, and the whole row drops 5px into place. The top edge of the board is a perforated strip of 14px-pitch dots. Under the digits a mono line gives "CBP's ruling" and "match" (yellow) or "different" (vermilion).

### Route map (signature)
- **Interchange:** a 13px circle with a 4px Station White stroke, Enamel fill, and a mono fork number; lit interchanges fill yellow with ink numerals. A pending interchange has a dashed ring that turns slowly. Latency sits below in 12px mono.
- **Branches:** 6px white route lines for taken options, 4px at 60 percent for options not taken, a 4px vermilion dotted line ending in a cross for none-of-these. Stub length equals probability. Percentages sit in bold mono before the code and the option label.
- **Product plaque:** a white 240 by 66px sign with Enamel text and a double keyline, holding the first lines of the product description.
- **Map key:** a small Deep Enamel panel, bottom-left, with a short line sample beside each label.
- **Empty ghost:** a faint 55 percent white schematic of the tree with four counts (22 sections, 98 chapters, 11,516 decisions, 18,946 codes) shown as station labels.

### Source rows and metrics
Each source (Decider path, Past rulings, Final pick) is a row with an 18px circular mark: yellow-filled with an ink tick when it agrees with the final code, a hollow vermilion ring with a bar when it differs, and its code in 13.5px mono at the right, vermilion if different. The metrics strip is a flat definition row split by 14 percent hairlines: mono 18px values followed by 13px labels.

### Bench bars
Accuracy drawn as route lengths: a 6px rounded line whose width is the score out of 40, ending in a short tick like a route stub. TariffTrail's bar and numbers are yellow; the others are white at 55 percent. The bar grows in over 900ms.

### Breadcrumb chain
The tree path as a wrapping row of "code + title" pairs in 13px Station White Dim, codes in 12.5px mono white, separated by small CSS-drawn chevrons. The final item is full white.

## Do's and Don'ts

### Do:
- **Do** keep all structural ink Station White (#f6f8ff), stepped only through the opacities the build already uses (100, 78, 60, 40, 20, 14 percent), on Enamel (#102f86), Deep Enamel (#0b2260) or Deepest Enamel (#081a4a).
- **Do** reserve Signal Yellow (#ffd21a) for the resolved route, the one primary action, the live lamp, selection and focus, with Signal Ink (#191400) on every yellow fill.
- **Do** reserve Vermilion (#ff7a5f) for none-of-these, disagreement, broker review, mismatch and errors.
- **Do** set every code, percentage, latency and count in Overpass Mono, and every sentence in Overpass.
- **Do** use 6px corners on rectangular controls and signs, and true circles (50 percent) for rings, lamps and marks.
- **Do** frame signs with an inset gap-ring keyline and cut map text out of lines with a 5px Enamel halo.
- **Do** show "not yet" with a dashed outline, a dash placeholder or a dashed ring.
- **Do** ease draws, pops, rises, stamps and presses with cubic-bezier(0.16, 1, 0.3, 1), and switch all animation and transition off under prefers-reduced-motion.
- **Do** give any new resting control boundary at least the 40 percent white edge the build uses on hover, since the 20 percent faint edge is only 1.8:1 on its ground.

### Don't:
- **Don't** add a third signal color: no green for success, no blue for links, no amber for caution.
- **Don't** give the review tier the look of approval. Fast-track is a yellow sign that still says a licensed broker confirms; never a green check, badge or "cleared" state.
- **Don't** present the path probability as a confidence meter, gauge or score on the board. The board shows the tier and whether sources agree.
- **Don't** use offset or blurred drop shadows. Inset keylines, the focus halo and the live-lamp pulse are the only box-shadows.
- **Don't** color abandoned branches. Options not taken stay white and fade; they never turn yellow or vermilion.
- **Don't** box map labels in filled chips or cards.
- **Don't** use uppercase with tracking outside the tier sign.
- **Don't** use pure #fff or #000 for text or lines, or white text on a yellow fill.
- **Don't** add decorative gradients or gloss. The only gradients are hard-stop patterns: the split-flap tile seam, the dot grid, the board perforation and the none-of-these dotted key.
- **Don't** replace the dot grid, the 45-degree bends or the round caps with curves or smooth bezier routes.
