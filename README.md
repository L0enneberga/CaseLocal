# LexLokal - lokale KI-Recherche in deutscher Rechtsprechung

[![Tests](https://github.com/L0enneberga/LexLokal/actions/workflows/tests.yml/badge.svg)](https://github.com/L0enneberga/LexLokal/actions/workflows/tests.yml)

Durchsuchbare Datenbank deutscher Gerichtsentscheidungen mit Schlagwortsuche, semantischer Suche und KI-Zusammenfassung. **Alles läuft lokal**: Kein Text verlässt den Rechner, und es entstehen keine API-Kosten.

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

## Installation

Voraussetzungen: Python 3.11+, [Ollama](https://ollama.com/download), ein Hugging-Face-Account mit akzeptierten Bedingungen für den [Datensatz](https://huggingface.co/datasets/openlegaldata/court-decisions-germany).

```bash
git clone https://github.com/L0enneberga/LexLokal.git
cd LexLokal
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

## Daten und Lizenz

- Urteile: [Open Legal Data](https://openlegaldata.io), Datenbank unter Open Database License (ODbL 1.0). Gerichtsentscheidungen sind nach § 5 UrhG gemeinfrei. Die Daten sind nicht Teil dieses Repositorys.
- Code: MIT-Lizenz.

**Hinweis:** Demo-Projekt, keine Rechtsberatung. KI-Zusammenfassungen können Fehler enthalten – maßgeblich ist immer der Urteilstext.
