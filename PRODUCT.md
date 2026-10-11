# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary, for now:** recruiters, hiring managers and technical reviewers looking at CaseLocal as a portfolio piece for job applications (confirmed: "just for my portfolio and job applications for now"). They mostly meet the app through the README screenshots, the GitHub repo, or a live demo run by the author. They judge two things in seconds: whether the output can be trusted, and how carefully it was engineered.
- **Modelled user (inferred from the repo, not confirmed):** German lawyers, trainees and law students who ask a legal question in plain language and need an answer they can verify down to the Randnummer, without client data leaving their machine.

## Product Purpose

CaseLocal is local AI research across the 10,000 most significant German court decisions, selected via the Open Legal Data citation graph. A plain-language question returns an answer structured the way lawyers work (Kurzantwort, Normen, Rechtsprechung, abweichende Entscheidungen, offene Punkte). Each claim is checked against the cited decision and marked gestützt, teilweise or nicht gestützt.

Success for the current phase: a reviewer sees in the first screenshot that this is a serious, trustworthy research tool, and that its honesty about uncertainty is the point.

## Positioning

The model only handles what needs language understanding. Code handles what code does more reliably: court, date and case number come from the database; statutory text is looked up and never generated; invented paragraphs are flagged; changes in case law are surfaced, and the original passage is shown instead of a verdict. Everything runs locally: no text leaves the machine and there are no API costs. Quality is measured on 13 gold questions rather than claimed.

## Operating Context

- Runs on the user's desktop: `start.bat` launches Ollama plus Streamlit at http://localhost:8501. Tested on Windows 11 with an RTX 4080 Super and 32 GB RAM.
- One research run takes about 30 s and goes through search, Einzelprüfung, answer and Zitatprüfung. Waiting through these stages is part of the experience.
- Answers are long and read carefully on a large monitor. Statutory text, case cards and reviews are expanded on demand.

## Capabilities and Constraints

- Stack: Python and Streamlit (`app.py`). Ollama with Gemma 4 12B and bge-m3, ChromaDB, SQLite FTS5.
- Settings: number of hits, AI keywords, AI answer, Gründliche Analyse, Zitatprüfung, check for Rechtsprechungsänderungen. Filters: Gerichtsbarkeit and year range.
- Output elements: search terms, Einzelprüfung per decision, a five-part structured answer with [n] citations and check marks, expandable Wortlaut with Stand and link, a block on Rechtsprechungsänderungen, references to EU law, the Zitatprüfung tally, and hit cards (Instanz, Zitierhäufigkeit, Tenor, most-cited norms, Fundstelle with Randnummern).
- Limits that must stay visible: statutory text in its current version only; federal law only, covering the most-cited statutes; 10,000 of about 424,000 decisions; the Rechtsprechungsänderung check is a heuristic; not legal advice.
- UI language: German. Legal terminology (Aktenzeichen, Randnummer, Tenor, Leitsatz, Instanz) stays exact.

## Brand Commitments

- Name: CaseLocal. Voice: sober, precise, honest about limits ("gemessen statt behauptet"). Never claims more than the evidence supports.
- Attribution to Open Legal Data (Ostendorff, Blume & Ostendorff, JCDL 2020, ODbL 1.0) and the "Keine Rechtsberatung" notice must remain in the UI.

## Evidence on Hand

- README screenshots: `docs/screenshot1.png` to `docs/screenshot4.png` (current default dark Streamlit look).
- Measurements in the README: falsches Datum/Az. 0 (previously 6); 88 % of statements supported (99/113); 10/13 leading decisions in the top 5; about 28 s per question.
- No users, testimonials or deployments exist. Do not fabricate any.

## Product Principles

1. **Verifiability is the product.** Every claim leads to its source, and every uncertainty is shown, not smoothed over.
2. **Code over model where code is reliable.** The UI should make it clear which parts are looked up and which are generated.
3. **Honest limits.** Show what is in the data and what is not, the version of the law displayed, and that this is a heuristic.
4. **Respect the reader.** Long legal text gets reading-grade typography and calm structure; nothing competes with the answer.
