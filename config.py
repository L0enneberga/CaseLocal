"""Zentrale Einstellungen des Projekts.

Alles, was du später ändern willst (Modelle, Datenmenge, Pfade),
steht hier an einer Stelle. Die anderen Dateien lesen nur diese Werte.
"""
from pathlib import Path

# --- Welche Urteile? -------------------------------------------------------
# "bedeutend":  die bedeutendsten Urteile aus dem Vollbestand, ausgewählt über den
#               Zitationsgraphen (siehe auswahl.py) - der Normalfall
# "stichprobe": die fertige Zufallsstichprobe DATENSATZ_VERSION (schnell, zum Ausprobieren)
DATENAUSWAHL = "bedeutend"

# --- Pfade ---------------------------------------------------------------
PROJEKT_ORDNER = Path(__file__).parent
DATEN_ORDNER = PROJEKT_ORDNER / "daten"          # wird NICHT auf GitHub hochgeladen
CHROMA_PFAD = DATEN_ORDNER / "chroma"            # Vektor-Datenbank
# Je Datenauswahl eine eigene Datenbank und ein eigener Suchindex, damit man wechseln kann.
# Nach Änderungen an der Zerlegung in index_bauen.py einen neuen Indexnamen wählen und neu bauen.
_BESTAENDE = {
    "stichprobe": ("urteile.db", "urteile_gegliedert"),
    "bedeutend": ("urteile_bedeutend.db", "bedeutend_gegliedert"),
}
SQLITE_PFAD = DATEN_ORDNER / _BESTAENDE[DATENAUSWAHL][0]   # Metadaten + Volltextindex
CHROMA_SAMMLUNG = _BESTAENDE[DATENAUSWAHL][1]              # Name des Suchindex

# --- Datensatz (Open Legal Data auf Hugging Face) -------------------------
DATENSATZ = "openlegaldata/court-decisions-germany"
ZITATIONSGRAPH = "openlegaldata/legal-citation-graph-germany"
VOLLBESTAND = "dump-20260520"                    # Stand des Vollbestands (ca. 424.000 Urteile)
DATENSATZ_VERSION = "dump-20260520-1k"           # nur für DATENAUSWAHL = "stichprobe"

# --- Auswahl der bedeutendsten Urteile (auswahl.py) ----------------------
AUSWAHL_GESAMT = 10_000            # so viele Urteile kommen in die Datenbank
AUSWAHL_NEUE_HOECHSTGERICHTE = 2_000   # neueste bedeutende Urteile von BVerfG, BGH, BAG, ... -
AUSWAHL_NEU_JAHRE = 5                  #   aus den letzten 5 Jahren (sie hatten noch keine Zeit,
                                       #   oft zitiert zu werden)
AUSWAHL_INSTANZGERICHTE = 1_500    # bedeutendste Urteile von OLG, OVG, LAG, LG, VG, ...
AUSWAHL_MINDESTENS_JE_GEBIET = 400 # jede Gerichtsbarkeit (z. B. Finanz-, Sozialgerichtsbarkeit)
                                   # ist mindestens so oft vertreten, sofern vorhanden

# --- Modelle (müssen vorher mit "ollama pull ..." geladen sein) ---------
EMBED_MODELL = "bge-m3"                          # rechnet Text in Zahlen (Embeddings) um
LLM_MODELL = "gemma4:12b"                        # beantwortet Fragen, vergibt Schlagworte

# --- Feineinstellungen ---------------------------------------------------
CHUNK_ZEICHEN = 1500          # Länge eines Textabschnitts
CHUNK_UEBERLAPPUNG = 200      # so viele Zeichen wiederholen sich zwischen zwei Abschnitten
MAX_CHUNKS_PRO_URTEIL = 40    # sehr lange Urteile werden gekürzt (spart Zeit)
EMBED_BATCH = 64              # so viele Abschnitte gehen gleichzeitig an das Embedding-Modell
LLM_KONTEXT = 16384           # wie viel Text das LLM auf einmal "sehen" darf (in Tokens);
                              # mit "ollama ps" prüfen, ob es noch zu 100 % auf der GPU läuft
LLM_DENKEN = False            # Gemma 4 "denkt" sonst vor jeder Antwort: viel langsamer,
                              # bei diesen Aufgaben kaum besser
KI_TREFFER = 6                # so viele der besten Treffer wertet das LLM für die Antwort aus

# Gewichtung der Urteilsteile bei der Bedeutungssuche (1.0 = neutral).
# Gründe und Leitsätze enthalten die Wertung des Gerichts, der Tatbestand
# vor allem den Vortrag der Parteien.
TEIL_GEWICHTE = {
    "Leitsatz": 1.05,
    "Gründe": 1.05,
    "Tenor": 1.0,
    "Tatbestand": 0.95,
    "Verfahrensgang": 0.95,
    "Sonstiges": 0.95,
}

# Rangfolge der Treffer: Die Relevanz zur Frage entscheidet, Bedeutung und
# Aktualität geben einen Zuschlag (0.25 = bis zu 25 % mehr Punkte).
RANG_BEDEUTUNG = 0.25         # für die meistzitierten Urteile im Bestand
RANG_AKTUALITAET = 0.10       # für ganz neue Urteile, nimmt mit dem Alter ab
AKTUALITAET_HALBWERT = 7      # nach so vielen Jahren ist der Aktualitätszuschlag halbiert
