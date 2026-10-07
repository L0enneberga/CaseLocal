"""Die drei Suchfunktionen.

  schlagwortsuche   - klassisch: findet exakte Wörter (SQLite FTS5, Ranking mit BM25)
  semantische_suche - nach Bedeutung: vergleicht Embeddings (ChromaDB)
  hybride_suche     - kombiniert beide Trefferlisten zu einer
"""
import re
import sqlite3

import chromadb
import ollama

import config

STOPPWOERTER = {"der", "die", "das", "und", "oder", "ein", "eine", "einer", "ist", "sind",
                "wann", "wie", "was", "wer", "mit", "von", "für", "bei", "den",
                "dem", "des", "auf", "aus", "nach", "kann", "darf", "muss", "nicht", "sich"}


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(config.SQLITE_PFAD)
    db.row_factory = sqlite3.Row                       # Zeilen wie Dictionaries ansprechen
    return db


def anzahl_urteile() -> int:
    return _db().execute("SELECT COUNT(*) FROM urteile").fetchone()[0]


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


def schlagwortsuche(woerter: list[str], anzahl: int = 10) -> list[dict]:
    anfrage = fts_anfrage(woerter)
    if not anfrage:
        return []
    zeilen = _db().execute(
        # bm25(...): Relevanz; Treffer in Schlagworten zählen 5-fach, im Aktenzeichen 2-fach.
        # snippet(...): kurzer Auszug rund um den Treffer, Fundstellen **fett**.
        "SELECT rowid, snippet(urteile_fts, 3, '**', '**', ' … ', 60) AS auszug "
        "FROM urteile_fts WHERE urteile_fts MATCH ? "
        "ORDER BY bm25(urteile_fts, 1.0, 2.0, 5.0, 1.0) LIMIT ?",
        (anfrage, anzahl),
    ).fetchall()
    return [{"urteil_id": z["rowid"], "auszug": z["auszug"]} for z in zeilen]


def _sammlung():
    client = chromadb.PersistentClient(path=str(config.CHROMA_PFAD))
    return client.get_or_create_collection(name="urteile", metadata={"hnsw:space": "cosine"})


def semantische_suche(frage: str, anzahl: int = 10) -> list[dict]:
    vektor = ollama.embed(model=config.EMBED_MODELL, input=frage)["embeddings"][0]
    # Mehr Abschnitte holen als nötig, weil oft mehrere aus demselben Urteil kommen.
    ergebnis = _sammlung().query(query_embeddings=[vektor], n_results=anzahl * 4)
    beste: dict[int, dict] = {}
    for text, meta in zip(ergebnis["documents"][0], ergebnis["metadatas"][0]):
        uid = meta["urteil_id"]
        if uid not in beste:                           # nur den besten Abschnitt je Urteil behalten
            beste[uid] = {"urteil_id": uid, "auszug": text}
    return list(beste.values())[:anzahl]


def hybride_suche(frage: str, schlagworte: list[str], anzahl: int = 8) -> list[dict]:
    """Kombiniert beide Suchen mit 'Reciprocal Rank Fusion'.

    Jedes Urteil bekommt pro Liste 1 / (60 + Platz) Punkte. Wer in beiden
    Listen weit oben steht, landet ganz oben. Die Zahl 60 ist der übliche
    Standardwert dieses Verfahrens.
    """
    listen = {
        "Bedeutung": semantische_suche(frage, anzahl * 2),
        "Schlagwort": schlagwortsuche(schlagworte or frage.split(), anzahl * 2),
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
    db = _db()
    treffer = []
    for uid in rangliste:
        zeile = db.execute("SELECT * FROM urteile WHERE id = ?", (uid,)).fetchone()
        if zeile is None:
            continue
        eintrag = dict(zeile)
        eintrag.pop("text")                            # Volltext wird hier nicht gebraucht
        eintrag.update(auszug=auszug[uid], gefunden_durch=quelle[uid], punkte=punkte[uid])
        treffer.append(eintrag)
    return treffer
