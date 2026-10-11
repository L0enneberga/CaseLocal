---
name: CaseLocal
description: Local legal research where every statement is set like an official record, with its Fundstellen ruled beside it.
colors:
  paper: "#F7F8FA"
  rail: "#EEEFF4"
  sheet: "#FFFFFF"
  ink: "#161A2B"
  ink-2: "#464B5F"
  ink-3: "#62677D"
  rule: "#DADCE4"
  rule-2: "#C4C7D2"
  violet: "#5636B0"
  violet-ink: "#FFFFFF"
  violet-wash: "#ECE8F8"
  violet-line: "#C9BEEC"
  ok: "#1C7448"
  part: "#9A5B00"
  no: "#B42318"
typography:
  wordmark:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  question:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.45
  title:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.3
  reading:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  quote:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.6
  body:
    fontFamily: "Source Sans 3, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"kern\", \"liga\""
  control:
    fontFamily: "Source Sans 3, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.35
  label:
    fontFamily: "Source Sans 3, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
  meta:
    fontFamily: "Source Sans 3, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
  figures:
    fontFamily: "Source Sans 3, Segoe UI, system-ui, -apple-system, sans-serif"
    fontWeight: 600
    fontFeature: "\"tnum\", \"lnum\""
rounded:
  tag: "3px"
  row: "4px"
  control: "6px"
  field: "8px"
  pill: "9px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
  s-7: "48px"
components:
  button-primary:
    backgroundColor: "{colors.violet}"
    textColor: "{colors.violet-ink}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  input-question:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.question}"
    rounded: "{rounded.field}"
    padding: "8px 8px 8px 16px"
  input-year:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "5px 8px"
  chip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.tag}"
    padding: "3px 10px"
  chip-selected:
    backgroundColor: "{colors.violet}"
    textColor: "{colors.violet-ink}"
    rounded: "{rounded.tag}"
    padding: "3px 10px"
  switch-track:
    backgroundColor: "{colors.rule-2}"
    rounded: "{rounded.pill}"
    width: "30px"
    height: "18px"
  switch-track-on:
    backgroundColor: "{colors.violet}"
    rounded: "{rounded.pill}"
    width: "30px"
    height: "18px"
  fundstelle-ref:
    textColor: "{colors.violet}"
    typography: "{typography.label}"
    rounded: "{rounded.tag}"
    padding: "0 2px"
  fundstelle-ref-hover:
    backgroundColor: "{colors.violet-wash}"
    textColor: "{colors.violet}"
  claim-row:
    textColor: "{colors.ink}"
    typography: "{typography.reading}"
    padding: "12px 0 12px 30px"
  claim-row-lit:
    backgroundColor: "{colors.violet-wash}"
  source-entry:
    textColor: "{colors.ink}"
    rounded: "{rounded.row}"
    padding: "12px 8px 12px 0"
  source-entry-lit:
    backgroundColor: "{colors.violet-wash}"
  source-number-lit:
    backgroundColor: "{colors.violet}"
    textColor: "{colors.violet-ink}"
    rounded: "{rounded.row}"
    height: "22px"
  quote-panel:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.quote}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  out-tag:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.tag}"
    padding: "0 5px"
---

# Design System: CaseLocal

## Overview

**Creative North Star: "The Official Record"**

CaseLocal sets a research answer the way the Bundesgesetzblatt sets law: sober serif text on cool paper, divided by hairline rules, with a ruled column of Fundstellen beside every statement. Nothing floats, nothing glows. Hierarchy comes from scale, weight and the weight of the rule beneath a block, not from boxes or cards. The single accent is Stempelviolett, the violet of an Eingangsstempel, and it only ever marks what the reader can act on, what is selected, and where a Fundstelle points.

The system is dense but calm. It is built for long, careful reading on a large monitor: a reading column capped at about 66ch, a thin settings rail, and a sticky sources column. Verification is the visual subject. Every statement carries a status mark whose fill shape (solid, half, hollow, dashed hollow) says how well it is backed, every answer section names its provenance (Datenbank, Code or Modell), and decisions that were excluded stay on the page, struck through and tagged aussortiert.

Interaction is quiet and explanatory: focusing a statement dims the rest of the answer and lights its sources; focusing a source lights every statement that cites it. The world ships in a light and a dark theme with identical roles.

**Key Characteristics:**
- Cool paper-white ground, blue-black ink, one violet accent.
- Serif for what is read, sans for the instrument around it.
- Tabular lining figures for every Az., Rn., date, duration and count.
- Flat surfaces: depth from paper tone and rules, never shadows or gradients.
- Status encoded by fill shape, colour and a written label together.
- Provenance and exclusion are always visible, never smoothed away.

## Colors

A cool, near-neutral paper-and-ink palette with one stamp-violet accent and three verification colours that only ever speak about evidence.

### Primary
- **Stempelviolett** (violet): the only accent. Primary button, selected chips, switches in the on position, the range thumb, Fundstelle references ([n]), the lit source number, links, the focus ring, the caret, the running-stage pulse, and the "Local" half of the wordmark.
- **Stempel Ink** (violet-ink): text and glyphs set on a solid violet fill.
- **Stempel Wash** (violet-wash): the lit state behind a focused statement (mixed at 60%) or source, the hover behind refs and tally marks, and text selection.
- **Stempel Line** (violet-line): the violet hairline: the Beleg column border of a lit statement and the left rule of a quoted original passage.

### Status
- **Gestützt Green** (ok): supported statements, completed pipeline stages, the "Lokal" live dot.
- **Teilweise Amber** (part): partially supported statements.
- **Nicht-gestützt Red** (no): unsupported statements.
- **Hinweis** uses ink-3: unverified notes are deliberately colourless.

### Neutral
- **Cool Paper** (paper): page ground and the sticky top bar.
- **Rail Grey** (rail): the settings rail, one tonal step below paper.
- **Sheet White** (sheet): surfaces that hold input or original text: the question field, year inputs, chips, quoted Wortlaut panels, the switch knob.
- **Blue-Black Ink** (ink): primary text and the structural rules (ledger, tally, the double rule under Antwort).
- **Ink Secondary** (ink-2): labels, meta prose, Beleg column text.
- **Ink Tertiary** (ink-3): metadata, durations, legends, struck-through excluded entries, Hinweis.
- **Hairline** (rule): row separators and region borders.
- **Hairline Strong** (rule-2): control strokes (chips, inputs, field border at rest), the off switch track, scrollbars.

### Dark theme
The dark theme keeps every role and swaps values (via `prefers-color-scheme` or `data-theme="dark"`): paper #11131A, rail #171A23, sheet #151821, ink #E6E7ED, ink-2 #B4B7C5, ink-3 #8F93A6, rule #272B37, rule-2 #363B4A, violet #A996F2, violet-ink #14111F, violet-wash #241D42, violet-line #4B3C86, ok #52C48E, part #E2A541, no #F26B5B. In dark, the violet lightens and its ink turns near-black; the sheet sits slightly above paper rather than white.

### Named Rules
**The Stempel Rule.** Violet marks interaction, selection and Fundstelle references, nothing else. It never encodes verification status and never decorates.

**The Evidence Colours Rule.** Green, amber and red appear only on verification marks, their written status, and stage completion. They are never used for buttons, alerts or decoration.

## Typography

**Display Font:** Source Serif 4 (with Georgia, Times New Roman)
**Body Font:** Source Serif 4 for reading text; Source Sans 3 (with Segoe UI, system-ui) for UI
**Label/Mono Font:** Source Sans 3 with tabular lining figures; no monospace

**Character:** A text serif with optical sizing carries everything a lawyer reads; a plain humanist sans carries the instrument panel around it. The pairing reads like a gazette with a well-made apparatus.

### Hierarchy
- **Wordmark** (600, 21px, 1, -0.015em): the CaseLocal mark only.
- **Headline** (600, 26px, 1.2, -0.01em): the Antwort heading; one per screen.
- **Question** (400, 19px, 1.45): the user's question in its field, set as text, not as a form value.
- **Title** (600, 18px, 1.3, balanced): numbered answer section headings.
- **Reading** (400, 17px, 1.6, max 66ch, pretty wrap): each statement. 16.5px below 640px.
- **Quote** (400, 15.5px, 1.6, max 66ch): Wortlaut panels; the original-passage quote is italic at 16px/1.55 in ink-2.
- **Body** (400, 15px, 1.5): UI base size.
- **Control** (400, 14px): switches, fields, source case lines.
- **Label** (600, 13px): rail and column headings, field labels, stage names, [n] refs, section numbers.
- **Meta** (400, 12.5px): durations, legends, citation counts, credits, footers.

### Named Rules
**The Two Voices Rule.** Serif for what is read (question, statements, headings, quoted law); sans for what operates (controls, labels, metadata). An Aktenzeichen inside a serif statement switches to the sans at 600 so it reads as a reference, not prose.

**The Tabular Figures Rule.** Every Az., Rn., date, duration and count is set with tabular lining figures (`font-variant-numeric: tabular-nums lining-nums`). Numbers are records and must align.

**The Weight Not Caps Rule.** Labels gain authority from weight 600 and ink colour, not from uppercase.

## Layout

An app shell: a 56px sticky top bar, a 252px settings rail, and a work area capped at 1240px. The work area stacks the question, the pipeline ledger in one ruled line (four stages plus total), then the result grid: the answer in a flexible column and a 316px sticky sources column, 48px apart.

Each statement is a three-part row: a 30px status gutter holding the mark, the statement text (max 66ch), and a 148px Beleg column separated by a hairline, holding refs, Randnummern and the written status. The 30px gutter is reused as the indent for every row-level element in the answer (change lines, quoted passages, provenance on wrap) and as the number column of the sources list.

Spacing follows the s-1 to s-7 scale (4, 8, 12, 16, 24, 32, 48). Rows breathe at s-3 vertically; sections open with s-6; the rail and work areas pad at s-5 and s-6.

Responsive: at 1180px the sources column drops beneath the answer as an auto-fill grid (min 260px) and the Zitatprüfung tally moves under the Antwort header. At 880px the rail collapses behind an "Einstellungen" button and the ledger becomes a 2x2 grid. At 640px the Beleg column folds under its statement as a wrapped row and the search button goes full width.

### Named Rules
**The Beleg Column Rule.** No statement stands alone: every claim row carries its Fundstellen in an aligned, ruled column beside it (or directly beneath it on narrow screens).

## Elevation & Depth

Flat. There are no shadows and no gradients anywhere. Depth is tonal and linear: the rail sits one step below paper, sheet-white marks surfaces that hold input or original text, and rules do the structural work. Rule weight is the hierarchy: a 1px hairline (rule) separates rows, a 1px ink rule bounds the ledger and the tally, and a 3px double ink rule closes the Antwort header like the head of a gazette page. State is shown with violet wash, opacity (the focus dim) or, while the pipeline replays, a 0.35 opacity with a 1.5px blur on the result.

### Named Rules
**The Flat Paper Rule.** Surfaces never lift. If something needs separation, give it a rule or a tone step, not a shadow.

**The Rule Weight Rule.** Hairline for rows, ink line for structure, double ink line for the one heading that opens the record.

## Shapes

Small, functional corners on a rectilinear page. Tags, chips and refs use 3px; source rows and source numbers 4px; buttons, inputs and quote panels 6px; the question field 8px. Only the switch track (9px on 18px height) and dots are fully round. The page itself is built from straight full-width rules, not containers: answer rows and source rows are open, bounded only top and bottom.

Status marks are 12px circles (15px in the tally): solid for gestützt, half-filled for teilweise, hollow for nicht gestützt, dashed hollow for Hinweis. Icons are 16px line drawings at 1.5 stroke with round caps, drawn in currentColor.

## Components

### Buttons
Quiet and decisive; one solid button per screen.
- **Shape:** gently rounded (6px).
- **Primary (Recherchieren):** violet fill, violet-ink text, label weight at 14.5px, 9px 16px padding, leading search icon.
- **Hover / Focus:** brightness 1.08 over 0.15s; 2px violet focus outline offset 2px. Disabled shows 0.6 opacity with a progress cursor.
- **Secondary (Einstellungen, mobile):** transparent with a rule-2 stroke, 6px radius, 13px text and icon.

### Chips
- **Style:** sheet fill, rule-2 stroke, ink-2 text, 3px corners, 13px.
- **State:** pressed fills violet with violet-ink text; used as multi-select filters (Gerichtsbarkeit).

### Switches
- **Style:** full-width row button: label in control size with an optional ink-3 subline, track at the right (30 by 18px), white knob.
- **State:** off is rule-2, on is violet; the knob slides 12px on the house ease. Dependent switches disable to ink-3 with the track at 0.45 opacity.

### Inputs / Fields
- **Question field:** sheet fill, rule-2 stroke, 8px corners; the textarea inside is serif question type and grows with content; the submit button sits inside the field at the bottom right.
- **Focus:** the field stroke turns violet (focus-within), no glow.
- **Year inputs:** sheet fill, rule-2 stroke, 6px corners, tabular figures, separated by an en dash.
- **Range:** native slider tinted with violet, value shown as a 600-weight output beside the label.

### Navigation
- **Top bar:** paper ground, hairline bottom, wordmark left (serif, "Local" in violet) with a 13px ink-3 descriptor; right side holds the "Lokal · offline" status with a green dot, a rule-2 separator, and model/data facts in tabular figures. Facts collapse first on narrow screens.
- **Rail:** rail tone, hairline right border, groups titled in label type, credit line pinned to the bottom above a hairline.

### Pipeline Ledger (signature)
A single ruled line between two ink rules: four stages divided by hairlines, each with a 13.5px name, a check icon in green when done, a result line in ink-2 and a duration in ink-3 tabular figures; the total sits right-aligned in 15px 600. Pending stages fall to ink-3 with results hidden; the running stage shows a pulsing violet dot.

### Claim Row (signature)
The unit of the answer. Status mark in the 30px gutter, reading-serif statement, Beleg column with violet [n] refs, Randnummern in tabular figures, and the written status in its evidence colour (with the reason when not fully supported). Optional Wortlaut disclosure below: a chevron summary in ink-2 that rotates 90 degrees and opens a sheet panel with the quoted law and an ink-3 Stand footer.
- **Focus (Spotlight):** hovering or focusing a row lights it with violet wash at 60%, turns its Beleg rule violet-line, and dims every other row to the dim opacity (0.32 light, 0.28 dark).

### Fundstellen List (signature)
Numbered entries: violet tabular number in a 30px column, court in 14px 600 with its level in ink-3, case line, ink-3 meta (citations, Rn.), and an ink-2 reason line. Lit entries take violet wash and a solid violet number; when a statement is focused, unrelated entries drop to 0.45. Excluded entries stay in place: case line struck through in ink-3, a 3px-cornered ink-3 outline tag reading "aussortiert", and the reason.

### Zitatprüfung Tally
Heading with a count, then one status mark per checked statement (each a button that spotlights and scrolls to its statement), then counts in tabular figures. Bounded below by an ink rule.

### Provenance Tag
An inline 12px ink-3 label with a 13px line icon (database, code or pen) naming where a section came from: Datenbank, per Code ergänzt, or Modell. Sits at the right of every section heading.

## Do's and Don'ts

### Do:
- **Do** keep violet for interaction, selection and Fundstelle references only (The Stempel Rule).
- **Do** encode every verification state three ways: fill shape, evidence colour and written label.
- **Do** set reading text in Source Serif 4 at 17px/1.6, capped near 66ch, and UI in Source Sans 3.
- **Do** set every Az., Rn., date, duration and count in tabular lining figures.
- **Do** give every statement its ruled Beleg column and every section its provenance tag.
- **Do** keep excluded decisions visible: struck through in ink-3 with the "aussortiert" tag and a reason.
- **Do** separate with rules and tone steps; use the double ink rule only to open the answer.
- **Do** honour reduced motion: transitions and the pulse switch off entirely.

### Don't:
- **Don't** add shadows or gradients to any surface (The Flat Paper Rule).
- **Don't** show verification status by colour alone, and don't use green, amber or red outside evidence.
- **Don't** render the answer as chat bubbles or move sources into a detached sidebar list without per-statement alignment.
- **Don't** remove or hide sources that were excluded or uncited.
- **Don't** use uppercase labels or eyebrow kickers to create hierarchy; use weight and ink.
- **Don't** set Aktenzeichen in the reading serif inside a statement; switch to the sans at 600.

## Variant: Lapis (`design/caselocal-lapis.html`)

A distilled sibling of the main design. It uses the same grammar, the same status shapes and the same type pair. Only the differences are listed here.

- **Accent:** lapis ultramarine `#1A3AF0` (chosen by the user), with `#1430C4` on hover, `#E8ECFE` as the wash and `#6B87FF` in dark mode. It appears only on refs, focus, the primary button, active toggles and chips, the Befund dot and the logo mark. It is never used for areas or text blocks.
- **Ground:** warm paper `#F7F6F2` in light mode. Dark mode uses warm ink-black `#121211`, so the ultramarine keeps its hue contrast.
- **Three places:** the question, with all settings folded into a one-line summary. The Befund, which is the Kurzantwort on a white sheet beside the Zitatprüfung panel. The Akte, which holds the sections beside the Fundstellen. Pipeline steps, search terms, uncited and excluded decisions, and data limits are folded behind named entry points or moved to the footer. The short limits stay in the header and in the Zitatprüfung panel.
- **Claims:** refs sit inline at the end of each sentence and there is no Beleg column. A status note appears only for teilweise, nicht gestützt or Hinweis. Hovering a claim shows its exact Randnummer on the lit Fundstelle.
- **Adaptation:** the question field is left-aligned with the answer column rather than centred.

### Lapis in der Streamlit-App

`app.py` übernimmt die Variante Lapis. Farben, Radien und Schriften stehen in `.streamlit/config.toml`, und zwar getrennt für `[theme.light]` und `[theme.dark]`. Alles, was das Theme nicht abdeckt, steht in `static/caselocal.css`. Die CSS-Regeln greifen über `st-key-*`-Klassen und Theme-Farben mit `light-dark()`. Die Schriften liegen lokal in `static/fonts`.

Grenzen von Streamlit:
- `st.html` entfernt SVG. Raute, Haken und Stift sind deshalb mit CSS-Masken gezeichnet, die Prüfmarken mit `border` und `background`.
- Das Hervorheben von Aussage und Quelle beim Darüberfahren gibt es in der App nicht.
- Unter 640 px stapelt Streamlit die Spalten. Damit die Zitatprüfung auch dann direkt unter der Kurzantwort steht, wird sie ein zweites Mal gerendert (`bilanz_schmal`) und per CSS umgeschaltet.
