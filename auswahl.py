"""Wählt die bedeutendsten Urteile aus dem Vollbestand von Open Legal Data aus.

Wird von daten_laden.py aufgerufen, wenn in config.py DATENAUSWAHL = "bedeutend" steht.

Idee: Wie oft ein Urteil von anderen Gerichten zitiert wird, ist der klassische
Maßstab für seine Bedeutung. Open Legal Data veröffentlicht dazu einen
Zitationsgraphen mit rund 7,4 Millionen Zitierungen.

Ablauf:
  1. Zitationsgraph laden (ca. 70 MB) - wer zitiert wen?
  2. Nur die Metadaten des Vollbestands lesen (Gericht, Datum, ...), nicht die 10 GB Volltext
  3. Bedeutungs-Score je Urteil berechnen:
       Zitierungen, gewichtet nach Instanz des zitierenden Gerichts
       geteilt durch das Alter (neue Urteile hatten noch keine Zeit, zitiert zu werden)
       mal einem Faktor für die Instanz des Urteils selbst
  4. Auswahl in Kontingenten (siehe config.py):
       neueste bedeutende Urteile der obersten Gerichte, bedeutendste Urteile der
       Instanzgerichte, Mindestanzahl je Gerichtsbarkeit, Rest nach Score
  5. Nur für die Auswahl die Volltexte laden
"""
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config

INSTANZEN = ["Oberstes Gericht", "Obergericht", "Eingangsgericht"]
# Gewicht einer Zitierung je nach Instanz des ZITIERENDEN Gerichts
ZITIER_GEWICHT = {"Oberstes Gericht": 3.0, "Obergericht": 1.5, "Eingangsgericht": 1.0}
# Faktor für die Instanz des Urteils SELBST
INSTANZ_FAKTOR = {"Oberstes Gericht": 2.0, "Obergericht": 1.3, "Eingangsgericht": 1.0}

OBERSTE = re.compile(r"^(Bundes|Gemeinsamer Senat|Europäischer Gerichtshof|Gerichtshof der Europäischen)")
OBER = re.compile(r"Oberlandesgericht|Kammergericht|Oberverwaltungsgericht|Verwaltungsgerichtshof"
                  r"|Landesarbeitsgericht|Landessozialgericht|Finanzgericht|Oberstes Landesgericht"
                  r"|Verfassungsgerichtshof|Staatsgerichtshof|Landesverfassungsgericht"
                  r"|Verfassungsgericht des Landes|Anwaltsgerichtshof|Dienstgerichtshof")
# Gerichtsbarkeit aus dem Gerichtsnamen, falls sie im Datensatz fehlt (z. B. beim BGH)
GEBIETE = [
    (r"Europäischer Gerichtshof|Gerichtshof der Europäischen", "Europäische Gerichtsbarkeit"),
    (r"Verfassungsgericht|Verfassungsgerichtshof|Staatsgerichtshof", "Verfassungsgerichtsbarkeit"),
    (r"Arbeitsgericht", "Arbeitsgerichtsbarkeit"),
    (r"Sozialgericht", "Sozialgerichtsbarkeit"),
    (r"Finanzgericht|Finanzhof", "Finanzgerichtsbarkeit"),
    (r"Verwaltungsgericht", "Verwaltungsgerichtsbarkeit"),
]


def instanz(level_of_appeal: str | None, gericht: str | None) -> str:
    """Ordnet ein Gericht einer von drei Stufen zu: Oberstes Gericht, Obergericht, Eingangsgericht."""
    gericht = gericht or ""
    if level_of_appeal == "Bundesgericht" or OBERSTE.search(gericht):
        return "Oberstes Gericht"
    if level_of_appeal == "Oberlandesgericht" or OBER.search(gericht):
        return "Obergericht"
    return "Eingangsgericht"


def gerichtsbarkeit(angegeben: str | None, gericht: str | None) -> str:
    """Gerichtsbarkeit laut Datensatz, sonst aus dem Gerichtsnamen abgeleitet."""
    if isinstance(angegeben, str) and angegeben:
        return angegeben
    for muster, gebiet in GEBIETE:
        if re.search(muster, gericht or "", re.IGNORECASE):     # "Bundesfinanzhof" enthält "finanzhof"
            return gebiet
    return "Ordentliche Gerichtsbarkeit"            # BGH, OLG, LG, AG, Kammergericht, ...


# --- 1. und 2.: Zitationsgraph und Metadaten laden -------------------------

def _dateien(repo: str) -> list[str]:
    from huggingface_hub import HfFileSystem
    return sorted(HfFileSystem().glob(f"datasets/{repo}/{config.VOLLBESTAND}/*.parquet"))


def zitierungen_laden() -> pd.DataFrame:
    """Alle Zitierungen von Urteil zu Urteil: Spalten von_slug, nach_slug."""
    from huggingface_hub import HfFileSystem
    fs = HfFileSystem()
    teile = []
    for datei in _dateien(config.ZITATIONSGRAPH):
        with fs.open(datei) as f:
            teile.append(pq.read_table(f, columns=["from_type", "from_slug", "to_type", "to_slug"]))
    kanten = pa.concat_tables(teile).to_pandas()
    kanten = kanten[(kanten.from_type == "Case") & (kanten.to_type == "Case")
                    & (kanten.from_slug != kanten.to_slug)]          # Selbstzitate zählen nicht
    return (kanten.rename(columns={"from_slug": "von_slug", "to_slug": "nach_slug"})
            [["von_slug", "nach_slug"]].drop_duplicates())


def _metadaten_einer_datei(nummer_und_datei: tuple[int, str]) -> pa.Table:
    """Liest aus EINER Parquet-Datei nur die kleinen Spalten - die Volltexte bleiben auf dem Server."""
    from huggingface_hub import HfFileSystem
    nummer, datei = nummer_und_datei
    tabellen = []
    with HfFileSystem().open(datei, block_size=2**20) as f:
        parquet = pq.ParquetFile(f)
        for block in range(parquet.metadata.num_row_groups):
            t = parquet.read_row_group(block, columns=["id", "slug", "court", "file_number", "date", "type", "ecli"])
            t = t.append_column("datei", pa.array([nummer] * t.num_rows, pa.int16()))
            t = t.append_column("block", pa.array([block] * t.num_rows, pa.int16()))
            tabellen.append(t)
    return pa.concat_tables(tabellen)


def metadaten_laden() -> pd.DataFrame:
    """Metadaten aller Urteile des Vollbestands, mit Instanz und Gerichtsbarkeit."""
    with ThreadPoolExecutor(8) as pool:                # 8 Dateien gleichzeitig laden
        tabellen = list(pool.map(_metadaten_einer_datei, enumerate(_dateien(config.DATENSATZ))))
    meta = pa.concat_tables(tabellen).flatten().to_pandas()
    meta = meta.rename(columns={"court.name": "gericht", "court.jurisdiction": "jurisdiction",
                                "court.level_of_appeal": "level", "file_number": "aktenzeichen",
                                "date": "datum", "type": "typ"})
    meta["instanz"] = [instanz(l, g) for l, g in zip(meta.level, meta.gericht)]
    meta["gerichtsbarkeit"] = [gerichtsbarkeit(j, g) for j, g in zip(meta.jurisdiction, meta.gericht)]
    return meta


# --- 3.: Bedeutungs-Score --------------------------------------------------

def alter_in_jahren(datum: pd.Series, stichtag: date) -> pd.Series:
    tage = (pd.Timestamp(stichtag) - pd.to_datetime(datum.str[:10], errors="coerce")).dt.days
    return (tage / 365.25).clip(lower=0).fillna(30)   # ohne Datum: als alt behandeln


def bedeutung_berechnen(meta: pd.DataFrame, kanten: pd.DataFrame, stichtag: date) -> pd.DataFrame:
    """Ergänzt die Spalten zitiert_von, gewichtet, alter und score.

    score = log(1 + gewichtete Zitierungen / (Alter + 2)) * Instanzfaktor
    Die +2 verhindert, dass ein ganz neues Urteil mit einer einzigen Zitierung
    gleich ganz oben landet. Der Logarithmus dämpft Ausreißer (Massenverfahren).
    """
    instanz_von = dict(zip(meta.slug, meta.instanz))
    kanten = kanten.assign(gewicht=kanten.von_slug.map(instanz_von).map(ZITIER_GEWICHT).fillna(1.0))
    je_urteil = kanten.groupby("nach_slug").agg(zitiert_von=("von_slug", "size"),
                                                gewichtet=("gewicht", "sum"))
    meta = meta.join(je_urteil, on="slug")
    meta[["zitiert_von", "gewichtet"]] = meta[["zitiert_von", "gewichtet"]].fillna(0)
    meta["zitiert_von"] = meta.zitiert_von.astype(int)
    meta["alter"] = alter_in_jahren(meta.datum, stichtag)
    meta["score"] = np.log1p(meta.gewichtet / (meta.alter + 2)) * meta.instanz.map(INSTANZ_FAKTOR)
    return meta


# --- 4.: Auswahl in Kontingenten -------------------------------------------

def auswaehlen(meta: pd.DataFrame, gesamt: int, neue_hoechst: int, neu_jahre: float,
               instanzgerichte: int, mindestens_je_gebiet: int) -> pd.DataFrame:
    """Wählt `gesamt` Urteile aus. Spalte "grund" sagt, über welches Kontingent.

    1. neue_hoechst:  neueste bedeutende Urteile der obersten Gerichte (nicht älter als neu_jahre)
    2. instanzgerichte: bedeutendste Urteile von Ober- und Eingangsgerichten
    3. mindestens_je_gebiet: die bedeutendsten je Gerichtsbarkeit, bis jede so oft vertreten ist
    4. der Rest nach Score
    """
    nach_score = meta.sort_values(["score", "datum"], ascending=False)
    gewaehlt: dict[int, str] = {}                    # Zeilenindex -> Grund

    def nehmen(kandidaten: pd.DataFrame, anzahl: int, grund: str) -> None:
        for i in kandidaten.index:
            if len(gewaehlt) >= gesamt or anzahl <= 0:
                return
            if i not in gewaehlt:
                gewaehlt[i] = grund
                anzahl -= 1

    neu = nach_score[(nach_score.instanz == "Oberstes Gericht") & (nach_score.alter <= neu_jahre)]
    nehmen(neu, neue_hoechst, "neu")
    nehmen(nach_score[nach_score.instanz != "Oberstes Gericht"], instanzgerichte, "Instanzgericht")
    for gebiet, gruppe in nach_score.groupby("gerichtsbarkeit", sort=True):
        vorhanden = sum(1 for i in gruppe.index if i in gewaehlt)
        nehmen(gruppe[gruppe.zitiert_von > 0], mindestens_je_gebiet - vorhanden, "Gebiet")
    nehmen(nach_score, gesamt, "Bedeutung")
    auswahl = meta.loc[list(gewaehlt)].copy()
    auswahl["grund"] = [gewaehlt[i] for i in auswahl.index]
    return auswahl


def auf_gesamtzahl_kuerzen(auswahl: pd.DataFrame, gesamt: int) -> pd.DataFrame:
    """Streicht überzählige Urteile, und zwar nur die schwächsten aus dem Kontingent "Bedeutung".

    Die anderen Kontingente holen bewusst auch weniger zitierte Urteile herein
    (neue Entscheidungen, Instanzgerichte) und bleiben deshalb vollständig.
    """
    ueberzahl = len(auswahl) - gesamt
    if ueberzahl <= 0:
        return auswahl
    weg = auswahl[auswahl.grund == "Bedeutung"].nsmallest(ueberzahl, "score").index
    return auswahl.drop(weg).sort_values("score", ascending=False).head(gesamt)


def rangwerte(auswahl: pd.DataFrame) -> pd.Series:
    """Bedeutung als Rang innerhalb der Auswahl: 0 = am wenigsten, 1 = am meisten zitiert."""
    return auswahl.score.rank(pct=True).round(4)


# --- 5.: Volltexte nur für die Auswahl laden -------------------------------

CACHE_ORDNER = config.DATEN_ORDNER / "cache_volltexte"   # bereits geladene Volltexte


def _volltexte_eines_blocks(auftrag: tuple[str, int, set[int]]) -> dict[int, str]:
    """Volltexte der gewünschten Urteile aus einem Datenblock.

    Bereits geladene Texte liegen im Zwischenspeicher, damit eine erneute
    Auswahl (z. B. mit anderen Einstellungen) nicht alles neu herunterlädt.
    """
    from huggingface_hub import HfFileSystem
    datei, block, ids = auftrag
    cache = CACHE_ORDNER / f"{datei.rsplit('/', 1)[-1].removesuffix('.parquet')}_{block}.parquet"
    if cache.exists():
        t = pq.read_table(cache)
        vorhanden = dict(zip(t.column("id").to_pylist(), t.column("text").to_pylist()))
        if ids <= vorhanden.keys():
            return {i: vorhanden[i] for i in ids}
    with HfFileSystem().open(datei, block_size=2**22) as f:
        t = pq.ParquetFile(f).read_row_group(block, columns=["id", "markdown_content"])
    texte = {i: text for i, text in zip(t.column("id").to_pylist(), t.column("markdown_content").to_pylist())
             if i in ids}
    CACHE_ORDNER.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"id": list(texte), "text": list(texte.values())}), cache)
    return texte


def volltexte_laden(auswahl: pd.DataFrame, fortschritt=print) -> dict[int, str]:
    """Lädt nur die Datenblöcke, in denen ausgewählte Urteile liegen, und daraus nur den Text."""
    dateien = _dateien(config.DATENSATZ)
    auftraege = [(dateien[d], int(b), set(gruppe.id)) for (d, b), gruppe in auswahl.groupby(["datei", "block"])]
    texte: dict[int, str] = {}
    with ThreadPoolExecutor(4) as pool:
        for nr, ergebnis in enumerate(pool.map(_volltexte_eines_blocks, auftraege), 1):
            texte.update(ergebnis)
            if nr % 10 == 0 or nr == len(auftraege):
                fortschritt(f"  {nr}/{len(auftraege)} Datenblöcke geladen ({len(texte)} Volltexte)")
    return texte


def laden(fortschritt=print) -> tuple[list[dict], pd.DataFrame]:
    """Führt alle Schritte aus.

    Ergebnis: (Urteile als Liste von Dictionaries für daten_laden.py,
               Zitierungen zwischen den ausgewählten Urteilen: von_id, nach_id)
    """
    fortschritt("1/5 Lade den Zitationsgraphen ...")
    kanten = zitierungen_laden()
    fortschritt(f"    {len(kanten):,} Zitierungen zwischen Urteilen".replace(",", "."))
    fortschritt("2/5 Lese die Metadaten des Vollbestands (ohne Volltexte) ...")
    meta = metadaten_laden()
    fortschritt(f"    {len(meta):,} Urteile im Vollbestand".replace(",", "."))
    fortschritt("3/5 Berechne den Bedeutungs-Score ...")
    meta = bedeutung_berechnen(meta, kanten, date.fromisoformat(
        f"{config.VOLLBESTAND[5:9]}-{config.VOLLBESTAND[9:11]}-{config.VOLLBESTAND[11:13]}"))
    fortschritt("4/5 Wähle die Urteile aus ...")
    # etwas mehr auswählen: Urteile ohne brauchbaren Text fallen beim Speichern heraus
    puffer = math.ceil(config.AUSWAHL_GESAMT * 1.03)
    auswahl = auswaehlen(meta, puffer, config.AUSWAHL_NEUE_HOECHSTGERICHTE, config.AUSWAHL_NEU_JAHRE,
                         config.AUSWAHL_INSTANZGERICHTE, config.AUSWAHL_MINDESTENS_JE_GEBIET)
    fortschritt("    " + ", ".join(f"{k}: {v}" for k, v in auswahl.grund.value_counts().items()))
    fortschritt("5/5 Lade die Volltexte der Auswahl ...")
    texte = volltexte_laden(auswahl, fortschritt)

    auswahl = auswahl[auswahl.id.map(lambda i: len(texte.get(i) or "") >= 200)]   # leere Texte weg
    auswahl = auf_gesamtzahl_kuerzen(auswahl, config.AUSWAHL_GESAMT)
    auswahl["bedeutung"] = rangwerte(auswahl)
    urteile = [{
        "id": int(z.id), "slug": z.slug, "court": {"name": z.gericht, "jurisdiction": z.gerichtsbarkeit},
        "date": z.datum, "file_number": z.aktenzeichen, "type": z.typ, "ecli": z.ecli,
        "markdown_content": texte[z.id], "instanz": z.instanz, "zitiert_von": int(z.zitiert_von),
        "bedeutung": float(z.bedeutung), "auswahl_grund": z.grund,
    } for z in auswahl.itertuples()]

    id_von = dict(zip(auswahl.slug, auswahl.id))
    intern = kanten[kanten.von_slug.isin(id_von) & kanten.nach_slug.isin(id_von)]
    zitierungen = pd.DataFrame({"von_id": intern.von_slug.map(id_von), "nach_id": intern.nach_slug.map(id_von)})
    return urteile, zitierungen
