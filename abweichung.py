"""Weist darauf hin, wenn neuere Rechtsprechung im Zusammenhang mit einem Urteil eine
Rechtsprechungsänderung erörtert.

Ablauf für ein Urteil:
  1. Welche NEUEREN Urteile der Datenbank zitieren es, und zwar von gleicher
     oder höherer Instanz? (Tabelle "zitierungen", aus dem Zitationsgraphen)
  2. Stellen im zitierenden Urteil suchen, an denen das Aktenzeichen steht.
  3. Steht dort eine typische Formulierung wie "hält nicht mehr fest",
     "Aufgabe der Rechtsprechung" oder "in Abkehr von"? (schnelle Vorauswahl)
  4. Nur dann prüft das LLM: Wird an der Stelle wirklich eine Änderung der
     Rechtsprechung beschrieben, und welche?

Die App zeigt das Ergebnis als festen Block in Abschnitt 4 der Antwort (siehe entwicklung):
welche Entscheidung die Änderung beschreibt und welche früheren Treffer sie dabei zitiert.

Bewusst NICHT automatisiert: die Entscheidung, ob das gefundene Urteil die alte
(aufgegebene) oder die neue Linie vertritt. Im Test mit 40 echten Fällen lag das
Sprachmodell dabei etwa jedes zweite Mal falsch - typischerweise, wenn das Urteil
selbst die Änderung eingeleitet hat und deshalb als Beleg zitiert wird. Deshalb
zeigt die App einen Prüfhinweis mit der Originalstelle statt eines Urteils "überholt".

Das ist eine Heuristik: Sie findet nur Urteile innerhalb der Datenbank und
ersetzt nicht die Prüfung im Kommentar.
"""
import re
import sqlite3
from contextlib import closing

import config
import llm

RANG = {"Oberstes Gericht": 3, "Obergericht": 2, "Eingangsgericht": 1}

# Typische Formulierungen, mit denen Gerichte von früherer Rechtsprechung abrücken.
# Bewusst eng gefasst: Allerweltswörter wie "entgegen" würden zu viele Stellen liefern.
HINWEISWORTE = re.compile(
    r"nicht mehr fest|hält .{0,60}?nicht (?:mehr )?fest|(?:wird|werden) aufgegeben"
    r"|gibt .{0,80}?(?:Rechtsprechung|Auffassung|Ansicht) auf"
    r"|Aufgabe (?:der|seiner|ihrer) (?:bisherigen )?(?:Rechtsprechung|Auffassung)"
    r"|Rechtsprechungsänderung|Änderung (?:der|seiner|ihrer) (?:bisherigen )?Rechtsprechung"
    r"|in Abkehr|weicht .{0,80}?\bab\b|abweichend von (?:der|dem|seiner|ihrer)|überholt"
    r"|nicht (?:mehr )?anzuschließen|vermag .{0,60}?nicht (?:mehr )?zu folgen",
    re.IGNORECASE,
)

PROMPT_AENDERUNG = """Du bist juristische Rechercheassistenz für deutsches Recht.
Die Textstellen stammen aus einer Gerichtsentscheidung. Beschreibt das Gericht hier eine Änderung
der Rechtsprechung, also dass es an einer früheren Auffassung nicht mehr festhält, sie aufgibt oder
ausdrücklich einschränkt? Nur ja, wenn der Text das ausdrücklich sagt. Bloßes Zitieren, Bestätigen
("hieran hält der Senat fest") oder Abgrenzen im Einzelfall ist keine Änderung.
Antworte ausschließlich als JSON:
{"aenderung": true oder false, "erklaerung": "1 Satz: Welche Auffassung wird aufgegeben, welche gilt jetzt?"}"""


def az_muster(aktenzeichen: str) -> re.Pattern | None:
    """Suchmuster für ein Aktenzeichen, tolerant bei Leerzeichen: "III ZR 303/20" findet auch "III ZR 303 / 20"."""
    teile = re.findall(r"\w+|[^\w\s]", aktenzeichen or "")
    if len(teile) < 2:
        return None
    return re.compile(r"\s*".join(re.escape(t) for t in teile))


def fundstellen(text: str, aktenzeichen: str, umfang: int = 400, hoechstens: int = 3) -> list[str]:
    """Textstellen rund um jede Nennung des Aktenzeichens."""
    muster = az_muster(aktenzeichen)
    if muster is None:
        return []
    stellen = []
    for treffer in muster.finditer(text):
        stellen.append(text[max(0, treffer.start() - umfang): treffer.end() + umfang // 2])
        if len(stellen) >= hoechstens:
            break
    return stellen


def verdaechtige_stellen(text: str, aktenzeichen: str) -> list[str]:
    """Nur die Stellen, an denen eine Formulierung für eine Rechtsprechungsänderung steht."""
    return [s for s in fundstellen(text, aktenzeichen) if HINWEISWORTE.search(s)]


def neuere_zitierende(db: sqlite3.Connection, t: dict, hoechstens: int = 8) -> list[dict]:
    """Neuere Urteile der Datenbank, die t zitieren, von gleicher oder höherer Instanz."""
    zeilen = db.execute(
        "SELECT u.id, u.gericht, u.typ, u.datum, u.aktenzeichen, u.slug, u.instanz, u.text "
        "FROM zitierungen z JOIN urteile u ON u.id = z.von_id "
        "WHERE z.nach_id = ? AND u.datum > ? ORDER BY u.datum DESC",
        (t["id"], t["datum"] or ""),
    ).fetchall()
    spalten = ["id", "gericht", "typ", "datum", "aktenzeichen", "slug", "instanz", "text"]
    kandidaten = [dict(zip(spalten, z)) for z in zeilen]
    eigener_rang = RANG.get(t.get("instanz"), 1)
    return [k for k in kandidaten if RANG.get(k["instanz"], 1) >= eigener_rang][:hoechstens]


def aenderung_bestaetigt(antwort: dict) -> bool:
    wert = antwort.get("aenderung")
    return wert is True or str(wert).strip().lower() in ("true", "ja")


def pruefen(t: dict, hoechstens: int = 3) -> list[dict]:
    """Sucht neuere Urteile, die im Zusammenhang mit t eine Rechtsprechungsänderung erörtern.

    Liefert höchstens `hoechstens` Hinweise, die neuesten zuerst (oft wiederholen
    mehrere Urteile derselben Serie wortgleich dieselbe Stelle).
    Ergebnis: [{"id", "gericht", "typ", "datum", "aktenzeichen", "slug", "instanz",
                "erklaerung", "stelle"}, ...]
    """
    with closing(sqlite3.connect(config.SQLITE_PFAD)) as db:
        kandidaten = neuere_zitierende(db, t)
    hinweise = []
    for k in kandidaten:
        if len(hinweise) >= hoechstens:
            break
        stellen = verdaechtige_stellen(k.pop("text"), t["aktenzeichen"])
        if not stellen:
            continue
        antwort = llm.json_chat(PROMPT_AENDERUNG, "Textstellen:\n\n" + "\n\n[…]\n\n".join(stellen))
        if aenderung_bestaetigt(antwort):
            hinweise.append({**k, "erklaerung": str(antwort.get("erklaerung") or "").strip(),
                             "stelle": " ".join(stellen[0].split())})
    return hinweise


def alle_pruefen(treffer: list[dict]) -> int:
    """Prüft alle Treffer und merkt sich bei jedem Hinweis die Treffernummer der ändernden
    Entscheidung ("nr"), falls sie selbst unter den Treffern ist. Ergebnis: Anzahl betroffener Treffer."""
    nr_von_id = {t["id"]: t["nr"] for t in treffer}
    for t in treffer:
        t["abweichungen"] = pruefen(t)
        for a in t["abweichungen"]:
            a["nr"] = nr_von_id.get(a["id"])
    return sum(bool(t["abweichungen"]) for t in treffer)


def entwicklung(treffer: list[dict]) -> list[dict]:
    """Ordnet die Hinweise nach der ändernden Entscheidung, die älteste zuerst.

    Ergebnis: [{"aendernd": {gericht, datum, aktenzeichen, slug, nr, ...}, "erklaerung",
                "betroffen": [{"treffer": t, "stelle": "..."}]}, ...]
    "betroffen" sind die früheren Treffer, die die ändernde Entscheidung an der Stelle zitiert.
    """
    gruppen: dict[int, dict] = {}
    for t in treffer:
        for a in t.get("abweichungen") or []:
            gruppe = gruppen.setdefault(a["id"], {"aendernd": a, "erklaerung": "", "betroffen": []})
            gruppe["erklaerung"] = gruppe["erklaerung"] or a["erklaerung"]
            gruppe["betroffen"].append({"treffer": t, "stelle": a["stelle"]})
    for gruppe in gruppen.values():
        gruppe["betroffen"].sort(key=lambda b: b["treffer"]["datum"] or "")
    return sorted(gruppen.values(), key=lambda g: g["aendernd"]["datum"] or "")
