"""Zentrale Einstellungen des Projekts.

Alles, was du später ändern willst (Modelle, Datenmenge, Pfade),
steht hier an einer Stelle. Die anderen Dateien lesen nur diese Werte.
"""
from pathlib import Path

# --- Pfade ---------------------------------------------------------------
PROJEKT_ORDNER = Path(__file__).parent
DATEN_ORDNER = PROJEKT_ORDNER / "daten"          # wird NICHT auf GitHub hochgeladen
SQLITE_PFAD = DATEN_ORDNER / "urteile.db"        # Metadaten + Volltextindex
CHROMA_PFAD = DATEN_ORDNER / "chroma"            # Vektor-Datenbank

# --- Datensatz (Open Legal Data auf Hugging Face) -------------------------
DATENSATZ = "openlegaldata/court-decisions-germany"
DATENSATZ_VERSION = "dump-20260520-1k"           # später: "dump-20260520-10k"

# --- Modelle (müssen vorher mit "ollama pull ..." geladen sein) ---------
EMBED_MODELL = "bge-m3"                          # rechnet Text in Zahlen (Embeddings) um
LLM_MODELL = "gemma4:12b"                        # beantwortet Fragen, vergibt Schlagworte

# --- Feineinstellungen ---------------------------------------------------
CHUNK_ZEICHEN = 1500          # Länge eines Textabschnitts
CHUNK_UEBERLAPPUNG = 200      # so viele Zeichen wiederholen sich zwischen zwei Abschnitten
MAX_CHUNKS_PRO_URTEIL = 40    # sehr lange Urteile werden gekürzt (spart Zeit)
EMBED_BATCH = 32              # so viele Abschnitte gehen gleichzeitig an das Embedding-Modell
LLM_KONTEXT = 8192            # wie viel Text das LLM auf einmal "sehen" darf (in Tokens)
