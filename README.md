# CaseLocal - lokale KI-Recherche in deutscher Rechtsprechung

[![Tests](https://github.com/L0enneberga/CaseLocal/actions/workflows/tests.yml/badge.svg)](https://github.com/L0enneberga/CaseLocal/actions/workflows/tests.yml)

Recherche in den 10.000 bedeutendsten deutschen Gerichtsentscheidungen – mit hybrider Suche, gegliederter KI-Antwort und einer Zitatprüfung, die nicht belegte Aussagen sichtbar macht. **Alles läuft lokal**: Kein Text verlässt den Rechner, und es entstehen keine API-Kosten.

> **Datengrundlage:** CaseLocal nutzt den Urteilsdatensatz von [Open Legal Data](https://openlegaldata.io) (Ostendorff, Blume & Ostendorff, 2020). Das Sammeln, Aufbereiten und offene Bereitstellen von über 400.000 Gerichtsentscheidungen ist ihre Arbeit, nicht meine. Herzlichen Dank dafür! Details und Zitat: [Datengrundlage und Dank](#datengrundlage-und-dank).

**Gegliederte Antwort:** Kurzantwort, einschlägige Normen und Rechtsprechung mit Randnummern. Jede belegte Aussage ist gegen das zitierte Urteil geprüft (✓).

![Gegliederte KI-Antwort mit geprüften Belegen](docs/screenshot1.png)

**Zitatprüfung:** Teilweise gestützte Aussagen werden orange, nicht gestützte rot markiert. Die Treffer zeigen Instanz, Zitierhäufigkeit und Jahr.

![Zitatprüfung markiert nicht belegte Aussagen](docs/screenshot2.png)

**Fundstelle im Urteil:** der passende Abschnitt der Gründe mit Randnummern und verlinkten Normen.

![Fundstelle mit Randnummern und verlinkten Normen](docs/screenshot3.png)

## Was das Projekt kann

Der Schwerpunkt liegt auf **nachprüfbaren Antworten**: Das Sprachmodell soll nicht nur zusammenfassen, sondern zeigen, worauf sich jede Aussage stützt, und kenntlich machen, wo das nicht gelingt.

- **Die bedeutendsten 10.000 Urteile statt einer Zufallsstichprobe**: Über den Zitationsgraphen von Open Legal Data (rund 7,4 Millionen Zitierungen) bekommt jedes der 424.000 Urteile einen Bedeutungs-Score: Zitierungen, gewichtet nach der Instanz des zitierenden Gerichts, geteilt durch das Alter, mal einem Faktor für die eigene Instanz. Kontingente sorgen dafür, dass auch neue Grundsatzentscheidungen, Instanzgerichte und jede Gerichtsbarkeit vertreten sind (siehe [Auswahl](#auswahl-der-urteile)).
- **Gewichten und kennzeichnen statt aussortieren**: Bedeutung und Aktualität fließen in die Rangfolge ein, die Relevanz zur Frage bleibt entscheidend. Jeder Treffer zeigt Instanz, „zitiert von N Entscheidungen“ und Jahr.
- **Hinweis auf Rechtsprechungsänderungen**: Zitiert ein neueres Urteil gleicher oder höherer Instanz einen Treffer mit Formulierungen wie „hält nicht mehr fest“ oder „in Abkehr von“, prüft das Modell, ob dort wirklich eine Änderung der Rechtsprechung erörtert wird. Dann erscheint am Treffer ein Prüfhinweis mit der Originalstelle. Ob der Treffer die alte oder die neue Linie vertritt, entscheidet bewusst der Mensch: Im Test an 40 echten Fällen lag das Sprachmodell dabei etwa jedes zweite Mal falsch.
- **Zitatprüfung gegen Halluzinationen**: Ein zweiter Durchgang prüft jeden Satz der Antwort gegen das Urteil, das er zitiert. Gestützte Aussagen erhalten ein Häkchen, teilweise oder nicht gestützte werden farbig markiert und begründet.
- **Zweistufige Analyse**: Das Modell prüft zuerst jedes gefundene Urteil einzeln (beantwortet es die Frage? was wurde im konkreten Fall entschieden? welche Randnummer?) und sortiert unpassende aus. Erst aus diesen Einzelprüfungen entsteht die Antwort.
- **Gegliederte Antwort nach juristischer Arbeitsweise**: Kurzantwort, einschlägige Normen, Rechtsprechung mit Randnummern, abweichende Entscheidungen und was die Urteile *nicht* beantworten. Einzelfall und Rechtssatz werden getrennt, höhere Instanzen und neuere Entscheidungen zuerst.
- **Suche entlang der Urteilsgliederung**: Urteile werden an Tenor, Tatbestand und Gründen zerlegt, Randnummern bleiben erhalten. Die Gründe zählen bei der Suche mehr als der Parteivortrag im Tatbestand. Zu jedem Treffer bekommt das Modell Leitsatz, Tenor und den Kontext rund um die Fundstelle.
- **Hybride Suche**: kombiniert klassische Volltextsuche (SQLite FTS5, BM25) mit semantischer Suche über Embeddings (ChromaDB), zusammengeführt per *Reciprocal Rank Fusion*.
- **KI-Schlagworte**: ein lokales Sprachmodell übersetzt Fragen in juristische Suchbegriffe und verschlagwortet Urteile automatisch.
- **Antworten mit Fundstellen (RAG)**: das Modell antwortet nur auf Grundlage der gefundenen Urteile und zitiert sie mit Nummer und Aktenzeichen.
- **Filter**: Suche auf Gerichtsbarkeiten und einen Zeitraum eingrenzen.
- **Normen verlinken**: Zitate wie „§ 573 Abs. 2 BGB“ oder „Art. 3 GG“ werden erkannt und auf gesetze-im-internet.de verlinkt.

## Architektur

```
Open Legal Data ──► daten_laden.py ──► SQLite (Metadaten + FTS5-Index)
                                          │
                    index_bauen.py ───────┴──► ChromaDB (Embeddings via bge-m3)
                    schlagworte.py ──► LLM vergibt Schlagworte + Kurzfassung

Frage ──► LLM: Suchbegriffe ──► hybride Suche ──► LLM: Einzelprüfung je Urteil
                                                          │
          Streamlit ◄── Zitatprüfung je Satz ◄── LLM: gegliederte Antwort mit [Fundstellen]
```

| Datei | Aufgabe |
| --- | --- |
| `config.py` | Alle Einstellungen (Modelle, Pfade, Datenmenge) |
| `auswahl.py` | Wählt die bedeutendsten Urteile über den Zitationsgraphen aus |
| `daten_laden.py` | Lädt die Urteile von Hugging Face in SQLite |
| `gliederung.py` | Erkennt Tenor, Tatbestand, Gründe und Randnummern |
| `index_bauen.py` | Teilt Urteile entlang der Gliederung in Abschnitte, berechnet Embeddings |
| `schlagworte.py` | Optional: KI-Verschlagwortung |
| `suche.py` | Schlagwort-, semantische und hybride Suche, Filter |
| `normen.py` | Erkennt Normzitate und verlinkt sie |
| `llm.py` | Prompts und Aufrufe an das Sprachmodell (Einzelprüfung, Antwort, Zitatprüfung) |
| `belege.py` | Zerlegt die Antwort in Sätze und markiert, welche Aussagen belegt sind |
| `abweichung.py` | Sucht neuere Urteile, die von einem Treffer abweichen könnten |
| `app.py` | Weboberfläche (Streamlit) |
| `tests/` | Automatische Tests (pytest), laufen bei jedem Push auf GitHub |

## Technik

Python · [Ollama](https://ollama.com) · Gemma 4 12B · bge-m3 · ChromaDB · SQLite FTS5 · Streamlit

Getestet auf: Windows 11, RTX 4080 Super (16 GB VRAM), 32 GB RAM.

## Schnellstart unter Windows

Voraussetzungen: [Python](https://www.python.org/downloads/) 3.11+ und [Ollama](https://ollama.com/download) sind installiert, und auf der [Datensatzseite](https://huggingface.co/datasets/openlegaldata/court-decisions-germany) sind die Zugangsbedingungen akzeptiert (kostenloser Hugging-Face-Account).

1. **`setup.bat`** doppelklicken – einmalig. Legt die virtuelle Umgebung an, installiert die Bibliotheken, lädt die Modelle aus `config.py` und die Urteile und baut den Suchindex. Fehlt etwas, erklärt das Skript, was zu tun ist; danach einfach erneut starten, Erledigtes wird übersprungen.
2. **`start.bat`** doppelklicken – bei jeder Nutzung. Prüft, ob alles bereit ist, startet Ollama bei Bedarf und öffnet die App im Browser.

## Installation von Hand

Voraussetzungen: Python 3.11+, [Ollama](https://ollama.com/download), ein Hugging-Face-Account mit akzeptierten Bedingungen für den [Datensatz](https://huggingface.co/datasets/openlegaldata/court-decisions-germany).

```bash
git clone https://github.com/L0enneberga/CaseLocal.git
cd CaseLocal
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

ollama pull bge-m3
ollama pull gemma4:12b
hf auth login                    # Hugging-Face-Token eingeben
```

## Benutzung

```bash
python daten_laden.py            # 1. die 10.000 bedeutendsten Urteile auswählen und laden (ca. 3 GB)
python index_bauen.py            # 2. Suchindex bauen (ca. 2-3 Stunden, kann unterbrochen werden)
python schlagworte.py --anzahl 100   # 3. optional: KI-Schlagworte
streamlit run app.py             # 4. App starten -> http://localhost:8501
```

## Auswahl der Urteile

Statt einer Zufallsstichprobe lädt CaseLocal gezielt die bedeutendsten Urteile aus dem Vollbestand. Dafür werden zuerst nur der Zitationsgraph und die Metadaten aller Urteile gelesen (rund 120 MB statt 10 GB), dann der Score berechnet und erst danach die Volltexte der Auswahl geladen.

| Kontingent | Anzahl | Warum |
| --- | --- | --- |
| Neue Urteile oberster Gerichte (letzte 5 Jahre) | 2.000 | Neue Grundsatzentscheidungen hatten noch keine Zeit, oft zitiert zu werden |
| Instanzgerichte (OLG, OVG, LAG, LG, VG, ...) | 1.500 | Die tägliche Praxis wird auch von Instanzgerichten geprägt |
| Mindestens je Gerichtsbarkeit | 400 | Auch seltener zitierte Gebiete wie das Steuerrecht sind vertreten |
| Rest nach Bedeutungs-Score | bis 10.000 | Die meistzitierten Entscheidungen |

Alle Zahlen lassen sich in `config.py` ändern. Mit `DATENAUSWAHL = "stichprobe"` arbeitet CaseLocal wieder mit der Zufallsstichprobe.

**Warum veraltete Urteile nicht einfach aussortiert werden:** Neuer heißt nicht maßgeblicher – eine BGH-Grundsatzentscheidung von 2005 kann heute noch die Linie bestimmen. Die herrschende Meinung steckt zudem vor allem in der Literatur, die im Datenbestand fehlt. Und „pro Rechtsfrage nur das Neueste“ setzt voraus, Rechtsfragen zuverlässig zu erkennen; beim Aussortieren verschwänden womöglich gerade die tragenden Entscheidungen. CaseLocal gewichtet deshalb, kennzeichnet und warnt, statt auszuschließen.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Die Tests prüfen die Bausteine, die ohne Daten und ohne Ollama funktionieren: Bedeutungs-Score und Kontingente der Auswahl, Erkennen der Urteilsgliederung und Randnummern, Zerlegen in Abschnitte, FTS5-Anfragen, Filter und Rangfolge, Satzzerlegung und Markierung der Zitatprüfung, Vorauswahl für Rechtsprechungsänderungen und das Erkennen von Normzitaten.

## Datengrundlage und Dank

Die Urteile stammen aus dem Datensatz [court-decisions-germany](https://huggingface.co/datasets/openlegaldata/court-decisions-germany), die Zitierungen aus dem [legal-citation-graph-germany](https://huggingface.co/datasets/openlegaldata/legal-citation-graph-germany), beide von **[Open Legal Data](https://openlegaldata.io)**. Das Projekt sammelt deutsche Gerichtsentscheidungen, bereitet sie mit Metadaten (Gericht, Datum, Aktenzeichen, ECLI) und als sauberen Text auf und stellt sie frei zur Verfügung. Ohne diese Vorarbeit gäbe es CaseLocal nicht.

**Abgrenzung:** Von Open Legal Data stammen die Urteilstexte, ihre Metadaten und der Zitationsgraph. Selbst gebaut habe ich die Such- und Analyseschicht darauf: Bedeutungs-Score und Auswahl, Indexierung, hybride Suche, KI-Analyse mit Zitatprüfung, Hinweis auf Rechtsprechungsänderungen und die Oberfläche.

Wer dieses Projekt oder den Datensatz verwendet, sollte die Arbeit der Ersteller zitieren:

> Malte Ostendorff, Till Blume, Saskia Ostendorff: *Towards an Open Platform for Legal Information.* In: Proceedings of the ACM/IEEE Joint Conference on Digital Libraries (JCDL '20), 2020, S. 385–388. [doi:10.1145/3383583.3398616](https://doi.org/10.1145/3383583.3398616)

<details>
<summary>BibTeX</summary>

```bibtex
@inproceedings{10.1145/3383583.3398616,
author = {Ostendorff, Malte and Blume, Till and Ostendorff, Saskia},
title = {Towards an Open Platform for Legal Information},
year = {2020},
isbn = {9781450375856},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3383583.3398616},
doi = {10.1145/3383583.3398616},
booktitle = {Proceedings of the ACM/IEEE Joint Conference on Digital Libraries in 2020},
pages = {385–388},
numpages = {4},
keywords = {open data, open source, legal information system, legal data},
location = {Virtual Event, China},
series = {JCDL '20}
}
```

</details>

**Lizenzen**

- Datenbank: Open Legal Data, [Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/1-0/). Die Daten sind nicht Teil dieses Repositorys; jede Installation lädt sie selbst von Hugging Face.
- Urteilstexte: Gerichtsentscheidungen sind nach § 5 UrhG gemeinfrei.
- Code dieses Repositorys: MIT-Lizenz.

**Weitere offene Bausteine**, auf denen das Projekt aufsetzt: [Ollama](https://ollama.com), das Embedding-Modell [bge-m3](https://huggingface.co/BAAI/bge-m3) (BAAI), das Sprachmodell Gemma (Google DeepMind), [ChromaDB](https://www.trychroma.com), [SQLite](https://sqlite.org) und [Streamlit](https://streamlit.io).

**Grenzen:**

- Auch die Zitatprüfung erfolgt durch ein Sprachmodell und kann sich irren. Sie macht Fehler sichtbar, garantiert aber keine Richtigkeit.
- Der Zitationsgraph enthält nur Zitierungen **innerhalb** des Open-Legal-Data-Bestands. Nicht veröffentlichte Urteile und die Literatur fehlen; der Score misst also Bedeutung in diesem Bestand, nicht die herrschende Meinung.
- Neue Grundsatzurteile sind trotz Altersnormierung und eigenem Kontingent anfangs unterbewertet.
- Der Hinweis auf Rechtsprechungsänderungen ist eine Heuristik: Er findet nur Änderungen in Urteilen, die selbst in der Auswahl sind, sagt nicht, welche Seite überholt ist, und ersetzt nicht die Prüfung im Kommentar.
- Der Zitationsgraph enthält keine Zitierungen von EuGH-Urteilen. Sie können deshalb keinen Bedeutungs-Score erhalten und sind in der Auswahl nicht vertreten.
- Der Datenbestand umfasst 10.000 von rund 424.000 Urteilen.

**Hinweis:** Demo-Projekt, keine Rechtsberatung. KI-Zusammenfassungen können Fehler enthalten – maßgeblich ist immer der Urteilstext.
