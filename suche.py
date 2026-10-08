"""Die drei Suchfunktionen.

  schlagwortsuche   - klassisch: findet exakte Wörter (SQLite FTS5, Ranking mit BM25)
  semantische_suche - nach Bedeutung: vergleicht Embeddings (ChromaDB)
  hybride_suche     - kombiniert beide Trefferlisten zu einer

Alle drei lassen sich mit einem Filter (Gerichtsbarkeit, Zeitraum) einschränken.
Die Bedeutungssuche gewichtet die Urteilsteile (Gründe höher als Tatbestand).
"""
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache

import chromadb
import ollama

import config
import gliederung

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


def _begriff(begriff: str) -> str:
    """Übersetzt EINEN Suchbegriff in FTS5-Syntax.

    Normzitate bleiben als feste Wortfolge erhalten, die übrigen Wörter müssen
    alle vorkommen, aber nicht direkt hintereinander:
      "Kündigung"                      ->  "Kündigung"*
      "häufige Krankheit"              ->  ("häufige"* AND "Krankheit"*)
      "§ 1 KSchG Kündigung"            ->  ("1 KSchG" AND "Kündigung"*)
    """
    teile = []
    for norm in re.findall(r"\d+[a-z]?\s+[A-ZÄÖÜ][\wÄÖÜäöüß]*", begriff):     # z. B. "573 BGB"
        teile.append(f'"{norm}"')
        begriff = begriff.replace(norm, " ")
    for wort in re.sub(r"[^\w ]", " ", begriff).split():                  # Sonderzeichen entfernen
        if len(wort) >= 3 and wort.lower() not in STOPPWOERTER and not wort.isdigit():
            teile.append(f'"{wort}"*')
    if len(teile) > 1:
        return "(" + " AND ".join(teile) + ")"
    return teile[0] if teile else ""


def fts_anfrage(woerter: list[str]) -> str:
    """Baut aus Suchbegriffen eine FTS5-Anfrage.

    Beispiel: ["Eigenbedarf", "Kündigung"]  ->  "Eigenbedarf"* OR "Kündigung"*
    Das Sternchen ist eine Präfixsuche: "Eigenbedarf"* findet auch "Eigenbedarfskündigung".
    Begriffe aus mehreren Wörtern siehe _begriff().
    """
    teile = [_begriff(wort) for wort in woerter]
    return " OR ".join(t for t in teile if t)


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
    return client.get_or_create_collection(name=config.CHROMA_SAMMLUNG,
                                           metadata={"hnsw:space": "cosine"})


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


def einbetten(text: str) -> list[float]:
    """Rechnet einen Text (z. B. die Frage) in ein Embedding um."""
    return ollama.embed(model=config.EMBED_MODELL, input=text)["embeddings"][0]


def _abschnitte_bewerten(ergebnis: dict) -> list[dict]:
    """Macht aus einer ChromaDB-Antwort eine Liste von Abschnitten, beste zuerst.

    Die Ähnlichkeit (1 - Abstand) wird mit dem Gewicht des Urteilsteils
    multipliziert: Ein Abschnitt aus den Gründen zählt etwas mehr als einer
    aus dem Tatbestand (siehe TEIL_GEWICHTE in config.py).
    """
    abschnitte = []
    for aid, text, meta, abstand in zip(ergebnis["ids"][0], ergebnis["documents"][0],
                                        ergebnis["metadatas"][0], ergebnis["distances"][0]):
        teil = meta.get("teil", "Sonstiges")
        abschnitte.append({
            "urteil_id": meta["urteil_id"], "abschnitt_id": aid, "auszug": text, "teil": teil,
            "rn_von": meta.get("rn_von", 0), "rn_bis": meta.get("rn_bis", 0),
            "wert": (1 - abstand) * config.TEIL_GEWICHTE.get(teil, 1.0),
        })
    return sorted(abschnitte, key=lambda a: a["wert"], reverse=True)


def semantische_suche(frage: str, anzahl: int = 10, filter: Filter | None = None,
                      vektor: list[float] | None = None) -> list[dict]:
    filter = filter or Filter()
    vektor = vektor or einbetten(frage)
    # Mehr Abschnitte holen als nötig, weil oft mehrere aus demselben Urteil kommen
    # und der Filter danach noch Urteile aussortiert.
    faktor = 4 if not filter.sql()[0] else 15
    sammlung = _sammlung()
    ergebnis = sammlung.query(query_embeddings=[vektor],
                              n_results=min(anzahl * faktor, max(sammlung.count(), 1)))
    beste: dict[int, dict] = {}
    for abschnitt in _abschnitte_bewerten(ergebnis):
        beste.setdefault(abschnitt["urteil_id"], abschnitt)   # nur den besten Abschnitt je Urteil
    erlaubt = _erlaubte_ids(list(beste), filter)
    return [t for uid, t in beste.items() if uid in erlaubt][:anzahl]


def _bester_abschnitt(urteil_id: int, vektor: list[float]) -> dict | None:
    """Sucht den passendsten Abschnitt innerhalb eines bestimmten Urteils.

    Wird für Urteile gebraucht, die nur die Schlagwortsuche gefunden hat.
    """
    ergebnis = _sammlung().query(query_embeddings=[vektor], n_results=5,
                                 where={"urteil_id": urteil_id})
    abschnitte = _abschnitte_bewerten(ergebnis)
    return abschnitte[0] if abschnitte else None


def zusammenfuegen(erster: str, zweiter: str) -> str:
    """Hängt zwei aufeinanderfolgende Abschnitte aneinander, ohne die Überlappung doppelt."""
    for laenge in range(min(len(erster), len(zweiter), config.CHUNK_UEBERLAPPUNG + 50), 20, -1):
        if erster.endswith(zweiter[:laenge]):
            return erster + zweiter[laenge:]
    return erster + "\n\n" + zweiter


def _umgebung(abschnitt_id: str) -> tuple[str, int, int]:
    """Bester Abschnitt plus Vorgänger und Nachfolger als ein zusammenhängender Text.

    Abschnitts-IDs haben die Form "325566-3" (Urteil 325566, Abschnitt 3).
    Ergebnis: (Text, erste Randnummer, letzte Randnummer)
    """
    urteil_id, nr = abschnitt_id.rsplit("-", 1)
    ids = [f"{urteil_id}-{n}" for n in (int(nr) - 1, int(nr), int(nr) + 1) if n >= 0]
    gefunden = _sammlung().get(ids=ids)
    stuecke = sorted(zip(gefunden["ids"], gefunden["documents"], gefunden["metadatas"]),
                     key=lambda s: int(s[0].rsplit("-", 1)[1]))
    text = ""
    for _, dokument, _ in stuecke:
        text = zusammenfuegen(text, dokument) if text else dokument
    rn = [m.get(k, 0) for _, _, m in stuecke for k in ("rn_von", "rn_bis") if m.get(k, 0)]
    return text, min(rn, default=0), max(rn, default=0)


def hybride_suche(frage: str, schlagworte: list[str], anzahl: int = 8,
                  filter: Filter | None = None) -> list[dict]:
    """Kombiniert beide Suchen mit 'Reciprocal Rank Fusion'.

    Jedes Urteil bekommt pro Liste 1 / (60 + Platz) Punkte. Wer in beiden
    Listen weit oben steht, landet ganz oben. Die Zahl 60 ist der übliche
    Standardwert dieses Verfahrens.

    Jeder Treffer bekommt außerdem seinen besten Abschnitt mit Fundstelle
    (z. B. "Gründe, Rn. 15–17"), die Nachbarabschnitte sowie Leitsatz und Tenor.
    """
    vektor = einbetten(frage)
    listen = {
        "Bedeutung": semantische_suche(frage, anzahl * 2, filter, vektor),
        "Schlagwort": schlagwortsuche(schlagworte or frage.split(), anzahl * 2, filter),
    }
    punkte: dict[int, float] = {}
    beste: dict[int, dict] = {}
    quelle: dict[int, list[str]] = {}
    for name, liste in listen.items():
        for platz, t in enumerate(liste, 1):
            uid = t["urteil_id"]
            punkte[uid] = punkte.get(uid, 0) + 1 / (60 + platz)
            beste.setdefault(uid, t)                   # Abschnitt aus Bedeutungssuche bevorzugt
            quelle.setdefault(uid, []).append(name)

    rangliste = sorted(punkte, key=punkte.get, reverse=True)[:anzahl]
    treffer = []
    with closing(_db()) as db:
        for uid in rangliste:
            zeile = db.execute("SELECT * FROM urteile WHERE id = ?", (uid,)).fetchone()
            if zeile is None:
                continue
            eintrag = dict(zeile)
            volltext = eintrag.pop("text")
            # Nur per Schlagwort gefunden? Dann den passendsten Abschnitt im Urteil suchen.
            abschnitt = beste[uid] if "abschnitt_id" in beste[uid] else _bester_abschnitt(uid, vektor)
            if abschnitt:
                kontext, rn_von, rn_bis = _umgebung(abschnitt["abschnitt_id"])
                fundstelle = gliederung.fundstelle(abschnitt["teil"], abschnitt["rn_von"],
                                                   abschnitt["rn_bis"])
                auszug = abschnitt["auszug"]
            else:                                      # Urteil (noch) nicht im Bedeutungs-Index
                kontext, rn_von, rn_bis = beste[uid]["auszug"], 0, 0
                fundstelle, auszug = "Volltext", beste[uid]["auszug"]
            eintrag.update(
                auszug=auszug, fundstelle=fundstelle,
                kontext=kontext, kontext_fundstelle=gliederung.fundstelle("Auszug", rn_von, rn_bis),
                leitsatz=gliederung.teil_text(volltext, "Leitsatz"),
                tenor=gliederung.teil_text(volltext, "Tenor"),
                gefunden_durch=quelle[uid], punkte=punkte[uid],
            )
            treffer.append(eintrag)
    for nr, eintrag in enumerate(treffer, 1):
        eintrag["nr"] = nr                             # die Nummer, mit der die Antwort zitiert: [nr]
    return treffer
