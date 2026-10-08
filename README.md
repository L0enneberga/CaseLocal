# CaseLocal - lokale KI-Recherche in deutscher Rechtsprechung

[![Tests](https://github.com/L0enneberga/CaseLocal/actions/workflows/tests.yml/badge.svg)](https://github.com/L0enneberga/CaseLocal/actions/workflows/tests.yml)

Durchsuchbare Datenbank deutscher Gerichtsentscheidungen mit Schlagwortsuche, semantischer Suche und KI-Zusammenfassung. **Alles läuft lokal**: Kein Text verlässt den Rechner, und es entstehen keine API-Kosten.

> **Datengrundlage:** CaseLocal nutzt den Urteilsdatensatz von [Open Legal Data](https://openlegaldata.io) (Ostendorff, Blume & Ostendorff, 2020). Das Sammeln, Aufbereiten und offene Bereitstellen von über 400.000 Gerichtsentscheidungen ist ihre Arbeit, nicht meine. Herzlichen Dank dafür! Details und Zitat: [Datengrundlage und Dank](#datengrundlage-und-dank).

![Suche mit KI-Zusammenfassung](docs/screenshot1.png)

![Gefundene Urteile mit Fundstellen](docs/screenshot2.png)

## Was das Projekt kann

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

Frage ──► LLM: Suchbegriffe ──► hybride Suche ──► LLM: Antwort mit [Fundstellen] ──► Streamlit
```

| Datei | Aufgabe |
| --- | --- |
| `config.py` | Alle Einstellungen (Modelle, Pfade, Datenmenge) |
| `daten_laden.py` | Lädt Urteile von Hugging Face in SQLite |
| `index_bauen.py` | Teilt Urteile in Abschnitte, berechnet Embeddings |
| `schlagworte.py` | Optional: KI-Verschlagwortung |
| `suche.py` | Schlagwort-, semantische und hybride Suche, Filter |
| `normen.py` | Erkennt Normzitate und verlinkt sie |
| `llm.py` | Prompts und Aufrufe an das Sprachmodell |
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
python daten_laden.py            # 1. Urteile laden (1.000er-Stichprobe)
python index_bauen.py            # 2. Suchindex bauen
python schlagworte.py --anzahl 100   # 3. optional: KI-Schlagworte
streamlit run app.py             # 4. App starten -> http://localhost:8501
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Die Tests prüfen die Bausteine, die ohne Daten und ohne Ollama funktionieren: FTS5-Anfragen, Filter, das Zerlegen in Abschnitte und das Erkennen von Normzitaten.

## Datengrundlage und Dank

Die Urteile stammen aus dem Datensatz [court-decisions-germany](https://huggingface.co/datasets/openlegaldata/court-decisions-germany) von **[Open Legal Data](https://openlegaldata.io)**. Das Projekt sammelt deutsche Gerichtsentscheidungen, bereitet sie mit Metadaten (Gericht, Datum, Aktenzeichen, ECLI) und als sauberen Text auf und stellt sie frei zur Verfügung. Ohne diese Vorarbeit gäbe es CaseLocal nicht.

**Abgrenzung:** Von Open Legal Data stammen die Urteilstexte und ihre Metadaten. Selbst gebaut habe ich die Such- und Analyseschicht darauf: Indexierung, hybride Suche, KI-Verschlagwortung, RAG-Antworten und die Oberfläche.

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

**Hinweis:** Demo-Projekt, keine Rechtsberatung. KI-Zusammenfassungen können Fehler enthalten – maßgeblich ist immer der Urteilstext.
