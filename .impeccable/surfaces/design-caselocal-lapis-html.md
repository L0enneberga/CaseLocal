---
version: 1
slug: "design-caselocal-lapis-html"
primary_target: "design/caselocal-lapis.html"
related_targets: ["design/caselocal.html"]
---

## Scope
Second variant of the CaseLocal research screen. It builds on design/caselocal.html, which stays untouched. Mode: Operate. Pinned by the user: a lapis lazuli blue, luminous but not garish, as the accent for small parts of the UI only. The first view must be much calmer, with the key information grouped in a few fixed places. The UI stays in German.

## Audience and job
The same as variant 1: reviewers see within seconds that each statement is checked against its source. The difference here is that the first glance shows only the answer and its check results, and everything else is one click away.

## Direction contract
THESIS: The same official-record grammar, distilled. Three places hold everything: the question (with a one-line settings summary), the Befund (Kurzantwort next to the Prüfbilanz), and the Akte (the full answer next to its Fundstellen). Everything else, such as the pipeline stages, search terms, settings, excluded decisions and data limits, is folded behind a named entry point.
OWN-WORLD: A warm paper-white ground and blue-black ink. The single accent is lapis lazuli ultramarine (#1A3AF0 light, chosen by the user; #6B87FF dark). It appears only on references, focus, the primary action, active toggles and the Befund marker. Ultramarine against warm ivory is the classic lapis pairing. Surfaces stay flat, rules are hairlines, Source Serif 4 is the reading face and Source Sans 3 the UI face, and figures are tabular.
STORY: Ask, see that the run worked (one status line), read the Kurzantwort and its Prüfbilanz, then go deeper. Hovering a statement still lights up its sources.
FIRST VIEWPORT: A slim header. A centred question field with a "Einstellungen · 8 Treffer · Arbeit · alle Prüfungen" summary under it. One status line for the run. Then the Befund: the Kurzantwort on a white sheet on the left and the Prüfbilanz on the right.
FORM: variant 1's gazette grammar, seed 352e7964, minus the rail, the ledger grid, the Beleg column and the section numbers. Refs move inline at the end of each sentence, and a status note appears only when a statement is not fully supported.
FINISH: finish review, verdict, then DESIGN-lapis notes appended to DESIGN.md as a variant section.
