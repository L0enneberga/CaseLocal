---
version: 1
slug: "design-caselocal-html"
primary_target: "design/caselocal.html"
related_targets: []
---

## Scope
CaseLocal research screen (question → pipeline → verified answer → sources), redesigned as a static, interactive HTML artifact for portfolio and README use. Mode: Operate. Pinned by the user: "clean minimalistic". The UI stays in German.

## Audience and job
Reviewers and recruiters need to understand within seconds that every statement is verified against its source. The modelled user is a German lawyer who asks one question and checks the answer down to the Randnummer.

## Direction contract
THESIS: The answer is set like the Bundesgesetzblatt, an official record: sober text with a ruled column of Fundstellen beside it. This refuses the category default of a chat bubble with sources in a sidebar.
OWN-WORLD: A cool paper-white ground and blue-black ink. The one accent is Stempelviolett, the violet of an Eingangsstempel, used for interaction, selection and Fundstelle references. Hairline rules, a serif for the reading text, a sans for the UI, and tabular numerals for Az., Rn. and dates. Flat surfaces: no shadows and no gradients. Status is encoded by shape fill (solid, half, hollow) as well as colour.
STORY: The question is visible, the pipeline shows that it worked, and the answer shows which statement is backed by which decision. Hovering a statement dims everything else and lights up its sources.
FIRST VIEWPORT: Top bar with the wordmark and a "Lokal · offline" status. A thin left rail with settings and filters. In the main area, the question field at full width, then the pipeline ledger in one line, then the answer at about 65ch with a Beleg column aligned to each statement. The Fundstellen list sits to the right, with the Zitatprüfung tally at its top.
FORM: Bundesgesetzblatt (gazette) grammar, candidate 7 of my grounded list, seed 352e7964.
Raises: variable-font-specimen: hierarchy by scale and weight on a strict rhythm, not boxes. streaming-wall: a focused statement dims the rest. labanotation: fill shape encodes verification level. emigre-bitmap: provenance is an honest state (Datenbank, Code or Modell tag). ticket-wallet: excluded decisions stay visible and are marked aussortiert, never removed. zoo-map: flat, unmodulated surfaces.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
