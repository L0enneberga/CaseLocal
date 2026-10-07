"""Die drei Suchfunktionen.

  schlagwortsuche   - klassisch: findet exakte Wörter (SQLite FTS5, Ranking mit BM25)
  semantische_suche - nach Bedeutung: vergleicht Embeddings (ChromaDB)
  hybride_suche     - kombiniert beide Trefferlisten zu einer

Alle drei lassen sich mit einem Filter (Gerichtsbarkeit, Zeitraum) einschränken.
"""
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache

import chromadb
import ollama

import config

STOPPWOERTER = {"der", "die", "das", "und", "oder", "ein", "eine", "einer", "ist", "sind",
                "wann", "wie", "was", "wer", "mit", "von", "für", "bei", "den",
                "dem", "des", "auf", "aus", "nach", "kann", "darf", "muss", "nicht", "sich"}


@dataclass
class Filter:
    """Einschränkungen für die Suche. Leere Werte bedeuten: nicht filtern."""
    gerichtsbarkeiten: list[str] = field(default_factory=list)
    von_jahr: int | None = None
    bis_jahr: int | None = None

    def sql(self) -> tuple[str, list]:
        """Übersetzt den Filter in eine SQL-Bedingung für die Tabelle urteile.

        Beispiel: Filter(["Arbeitsgerichtsbarkeit"], 2020)
          ->  ("gerichtsbarkeit IN (?) AND datum >= ?", ["Arbeitsgerichtsbarkeit", "2020-01-01"])
        """
        bedingungen, werte = [], []
        if self.gerichtsbarkeiten:
            platzhalter = ", ".join("?" for _ in self.gerichtsbarkeiten)
            bedingungen.append(f"gerichtsbarkeit IN ({platzhalter})")
            werte += self.gerichtsbarkeiten
        if self.von_jahr:
            bedingungen.append("datum >= ?")
            werte.append(f"{self.von_jahr}-01-01")
        if self.bis_jahr:
            bedingungen.append("datum <= ?")
            werte.append(f"{self.bis_jahr}-12-31")
        return " AND ".join(bedingungen), werte


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(config.SQLITE_PFAD)
    db.row_factory = sqlite3.Row                       # Zeilen wie Dictionaries ansprechen
    return db


def anzahl_urteile() -> int:
    with closing(_db()) as db:                         # Verbindung danach wieder schließen
        return db.execute("SELECT COUNT(*) FROM urteile").fetchone()[0]


def gerichtsbarkeiten() -> list[str]:
    """Alle Gerichtsbarkeiten im Bestand (für die Auswahl in der Seitenleiste)."""
    with closing(_db()) as db:
        zeilen = db.execute("SELECT DISTINCT gerichtsbarkeit FROM urteile "
                            "WHERE gerichtsbarkeit != '' ORDER BY 1").fetchall()
    return [z[0] for z in zeilen]


def jahresspanne() -> tuple[int, int]:
    """Ältestes und neuestes Entscheidungsjahr im Bestand."""
    with closing(_db()) as db:
        von, bis = db.execute("SELECT MIN(datum), MAX(datum) FROM urteile "
                              "WHERE datum != ''").fetchone()
    return int(von[:4]), int(bis[:4])


def fts_anfrage(woerter: list[str]) -> str:
    """Baut aus Suchbegriffen eine FTS5-Anfrage.

    Beispiel: ["Eigenbedarf", "Kündigung"]  ->  "Eigenbedarf"* OR "Kündigung"*
    Das Sternchen ist eine Präfixsuche: "Eigenbedarf"* findet auch "Eigenbedarfskündigung".
    """
    teile = []
    for wort in woerter:
        wort = re.sub(r"[^\w§ ]", " ", wort).strip()   # Sonderzeichen entfernen
        wort = re.sub(r"\s+", " ", wort)
        if len(wort) < 3 or wort.lower() in STOPPWOERTER:
            continue
        teile.append(f'"{wort}"*')
    return " OR ".join(teile)


def schlagwortsuche(woerter: list[str], anzahl: int = 10, filter: Filter | None = None) -> list[dict]:
    anfrage = fts_anfrage(woerter)
    if not anfrage:
        return []
    bedingung, werte = (filter or Filter()).sql()
    with closing(_db()) as db:
        zeilen = db.execute(
            # bm25(...): Relevanz; Treffer in Schlagworten zählen 5-fach, im Aktenzeichen 2-fach.
            # snippet(...): kurzer Auszug rund um den Treffer, Fundstellen **fett**.
            # JOIN: verbindet den Volltextindex mit der Tabelle urteile, damit wir filtern können.
            "SELECT urteile_fts.rowid AS id, "
            "snippet(urteile_fts, 3, '**', '**', ' … ', 60) AS auszug "
            "FROM urteile_fts JOIN urteile ON urteile.id = urteile_fts.rowid "
            "WHERE urteile_fts MATCH ? " + (f"AND {bedingung} " if bedingung else "") +
            "ORDER BY bm25(urteile_fts, 1.0, 2.0, 5.0, 1.0) LIMIT ?",
            (anfrage, *werte, anzahl),
        ).fetchall()
    return [{"urteil_id": z["id"], "auszug": z["auszug"]} for z in zeilen]


@lru_cache(maxsize=1)                                  # nur einmal öffnen, dann wiederverwenden
def _sammlung():
    client = chromadb.PersistentClient(path=str(config.CHROMA_PFAD))
    return client.get_or_create_collection(name="urteile", metadata={"hnsw:space": "cosine"})


def _erlaubte_ids(ids: list[int], filter: Filter) -> set[int]:
    """Welche dieser Urteile passen zum Filter? (Prüfung per SQL)"""
    bedingung, werte = filter.sql()
    if not bedingung or not ids:
        return set(ids)
    platzhalter = ", ".join("?" for _ in ids)
    with closing(_db()) as db:
        zeilen = db.execute(f"SELECT id FROM urteile WHERE id IN ({platzhalter}) AND {bedingung}",
                            (*ids, *werte)).fetchall()
    return {z[0] for z in zeilen}


def semantische_suche(frage: str, anzahl: int = 10, filter: Filter | None = None) -> list[dict]:
    filter = filter or Filter()
    vektor = ollama.embed(model=config.EMBED_MODELL, input=frage)["embeddings"][0]
    # Mehr Abschnitte holen als nötig, weil oft mehrere aus demselben Urteil kommen
    # und der Filter danach noch Urteile aussortiert.
    faktor = 4 if not filter.sql()[0] else 15
    sammlung = _sammlung()
    ergebnis = sammlung.query(query_embeddings=[vektor],
                              n_results=min(anzahl * faktor, max(sammlung.count(), 1)))
    beste: dict[int, dict] = {}
    for text, meta in zip(ergebnis["documents"][0], ergebnis["metadatas"][0]):
        uid = meta["urteil_id"]
        if uid not in beste:                           # nur den besten Abschnitt je Urteil behalten
            beste[uid] = {"urteil_id": uid, "auszug": text}
    erlaubt = _erlaubte_ids(list(beste), filter)
    return [t for uid, t in beste.items() if uid in erlaubt][:anzahl]


def hybride_suche(frage: str, schlagworte: list[str], anzahl: int = 8,
                  filter: Filter | None = None) -> list[dict]:
    """Kombiniert beide Suchen mit 'Reciprocal Rank Fusion'.

    Jedes Urteil bekommt pro Liste 1 / (60 + Platz) Punkte. Wer in beiden
    Listen weit oben steht, landet ganz oben. Die Zahl 60 ist der übliche
    Standardwert dieses Verfahrens.
    """
    listen = {
        "Bedeutung": semantische_suche(frage, anzahl * 2, filter),
        "Schlagwort": schlagwortsuche(schlagworte or frage.split(), anzahl * 2, filter),
    }
    punkte: dict[int, float] = {}
    auszug: dict[int, str] = {}
    quelle: dict[int, list[str]] = {}
    for name, liste in listen.items():
        for platz, t in enumerate(liste, 1):
            uid = t["urteil_id"]
            punkte[uid] = punkte.get(uid, 0) + 1 / (60 + platz)
            auszug.setdefault(uid, t["auszug"])        # Abschnitt aus Bedeutungssuche bevorzugt
            quelle.setdefault(uid, []).append(name)

    rangliste = sorted(punkte, key=punkte.get, reverse=True)[:anzahl]
    treffer = []
    with closing(_db()) as db:
        for uid in rangliste:
            zeile = db.execute("SELECT * FROM urteile WHERE id = ?", (uid,)).fetchone()
            if zeile is None:
                continue
            eintrag = dict(zeile)
            eintrag.pop("text")                        # Volltext wird hier nicht gebraucht
            eintrag.update(auszug=auszug[uid], gefunden_durch=quelle[uid], punkte=punkte[uid])
            treffer.append(eintrag)
    return treffer
