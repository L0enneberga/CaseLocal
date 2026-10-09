"""Erkennt Normzitate wie "§ 573 Abs. 2 BGB" oder "Art. 3 GG" im Text, schlägt ihren
Wortlaut nach und verlinkt sie auf gesetze-im-internet.de. Außerdem: Bezüge zum
Unionsrecht (EuGH-Vorlagen, Rechtssachen, Richtlinien), siehe unionsrecht_bezuege.

Die Gesetzestexte lädt gesetze_laden.py in die Tabellen gesetze, gesetz_namen und normen.
Sind sie (noch) nicht geladen, verlinkt das Modul nur die Gesetze aus der Liste GESETZE.
Der Wortlaut wird immer per Code nachgeschlagen, nie vom Sprachmodell erzeugt.
"""
import re
import sqlite3
from contextlib import closing
from functools import lru_cache

import config
import gliederung

# Ausweichliste, solange gesetze_laden.py nicht gelaufen ist:
# Abkürzung im Urteil  ->  Kurzform in der Adresse bei gesetze-im-internet.de
GESETZE = {
    "BGB": "bgb", "ZPO": "zpo", "StGB": "stgb", "StPO": "stpo", "HGB": "hgb",
    "GG": "gg", "VwGO": "vwgo", "VwVfG": "vwvfg", "GVG": "gvg", "ArbGG": "arbgg",
    "KSchG": "kschg", "BetrVG": "betrvg", "SGG": "sgg", "FGO": "fgo", "AO": "ao_1977",
    "EStG": "estg", "InsO": "inso", "GmbHG": "gmbhg", "UrhG": "urhg", "BRAO": "brao",
}

# § 573 BGB | § 573a Abs. 2 S. 1 BGB | Art. 3 Abs. 1 GG | § 6 Abs. 1 Satz 2 Alt. 1 AGG | § 31a SGB II
MUSTER = re.compile(
    r"(?P<art>§|Art\.)\s*(?P<nr>\d+[a-z]?)"
    r"(?:\s+(?:Abs\.|Absatz)\s*(?P<absatz>\d+[a-z]?))?"
    r"(?:\s+(?:Abs\.|Absatz|S\.|Satz|Nr\.|Alt\.|Var\.|Halbs\.|Hs\.|lit\.|Buchst\.)\s*\w+\)?)*"
    r"\s+(?P<gesetz>[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*(?:\s(?:[IVX]{1,4}|\d{1,2})\b)?)"
)


def _abfrage(sql: str, werte: tuple = ()) -> list[tuple]:
    """Fragt die Gesetzestabellen ab. Gibt es sie (noch) nicht, ist das Ergebnis leer."""
    try:                                               # nur lesen: legt keine leere Datei an
        with closing(sqlite3.connect(f"file:{config.SQLITE_PFAD}?mode=ro", uri=True)) as db:
            return db.execute(sql, werte).fetchall()
    except sqlite3.OperationalError:
        return []


@lru_cache(maxsize=1)
def _namen() -> dict[str, str]:
    """Alle bekannten Schreibweisen von Gesetzen -> Kurzform ("SGB II" -> "sgb_2")."""
    return dict(_abfrage("SELECT name, kurzform FROM gesetz_namen"))


@lru_cache(maxsize=1)
def geladene_gesetze() -> dict[str, dict]:
    """Kurzform -> {"gesetz", "titel", "stand"} aller geladenen Gesetze."""
    return {k: {"gesetz": g, "titel": t, "stand": s}
            for k, g, t, s in _abfrage("SELECT kurzform, gesetz, titel, stand FROM gesetze")}


def kurzform(gesetz: str) -> str | None:
    """Kurzform eines Gesetzes für die Adresse bei gesetze-im-internet.de, sonst None."""
    gesetz = " ".join(gesetz.split())
    return _namen().get(gesetz) or GESETZE.get(gesetz)


def norm_url(art: str, nr: str, gesetz: str) -> str | None:
    """Baut die Adresse einer Norm, z. B. ("§", "573", "BGB") -> .../bgb/__573.html"""
    kurz = kurzform(gesetz)
    if kurz is None:
        return None
    seite = f"art_{nr}" if art == "Art." else f"__{nr}"
    return f"https://www.gesetze-im-internet.de/{kurz}/{seite}.html"


def normen_finden(text: str) -> list[dict]:
    """Alle Normzitate eines Textes, jedes nur einmal.

    Ergebnis: [{"fund": "§ 6 Abs. 1 Satz 2 AGG", "art": "§", "nr": "6", "absatz": "1", "gesetz": "AGG"}, ...]
    """
    gefunden = {}
    for m in MUSTER.finditer(text):
        fund = " ".join(m[0].split())
        gefunden.setdefault(fund, {"fund": fund, "art": m["art"], "nr": m["nr"],
                                   "absatz": m["absatz"], "gesetz": " ".join(m["gesetz"].split())})
    return list(gefunden.values())


def absatz_text(text: str, absatz: str) -> str:
    """Nur ein Absatz einer Norm: Zeilen ab "(2)" bis vor den nächsten Absatz. Fehlt er: ""."""
    zeilen, drin = [], False
    for zeile in text.split("\n"):
        nummer = re.match(r"\((\d+[a-z]?)\)", zeile)
        if nummer:
            drin = nummer[1] == absatz
        if drin:
            zeilen.append(zeile)
    return "\n".join(zeilen)


def nachschlagen(art: str, nr: str, gesetz: str, absatz: str | None = None) -> dict | None:
    """Wortlaut einer Norm aus der Datenbank, z. B. nachschlagen("§", "6", "AGG", absatz="1").

    Ergebnis: {"norm": "§ 6 Abs. 1 AGG", "titel", "text", "stand", "url"} - oder None, wenn
    das Gesetz nicht geladen ist oder die Norm darin nicht vorkommt. Mit absatz nur dieser Absatz
    (gibt es ihn nicht, die ganze Norm).
    """
    kurz = kurzform(gesetz)
    if kurz is None:
        return None
    zeilen = _abfrage("SELECT n.titel, n.text, n.url, g.stand, g.gesetz FROM normen n "
                      "JOIN gesetze g ON g.kurzform = n.kurzform WHERE n.kurzform = ? AND n.art = ? AND n.nr = ?",
                      (kurz, art, nr))
    if not zeilen:
        return None
    titel, text, url, stand, abkuerzung = zeilen[0]
    teil = absatz_text(text, absatz) if absatz else ""
    return {"norm": f"{art} {nr}" + (f" Abs. {absatz}" if teil else "") + f" {abkuerzung}",
            "titel": titel, "text": teil or text, "stand": stand, "url": url}


def norm_status(art: str, nr: str, gesetz: str) -> str:
    """"gefunden", "fehlt" (Gesetz geladen, Norm gibt es darin nicht) oder "nicht im Bestand"."""
    kurz = kurzform(gesetz)
    if kurz is None or kurz not in geladene_gesetze():
        return "nicht im Bestand"
    return "gefunden" if nachschlagen(art, nr, gesetz) else "fehlt"


def zitierte_normen(urteil_id: int, hoechstens: int = 10) -> list[dict]:
    """Normen, die ein Urteil laut Zitationsgraph am häufigsten zitiert: [{"norm", "url"}, ...]"""
    zeilen = _abfrage("SELECT gesetz, paragraph FROM norm_zitierungen WHERE urteil_id = ? "
                      "ORDER BY anzahl DESC, paragraph LIMIT ?", (urteil_id, hoechstens))
    ergebnis = []
    for gesetz, paragraph in zeilen:
        teile = paragraph.split(" ", 1)
        url = norm_url(teile[0], teile[1], gesetz) if len(teile) == 2 else None
        ergebnis.append({"norm": f"{paragraph} {gesetz}", "url": url})
    return ergebnis


def verlinken(text: str) -> str:
    """Ersetzt bekannte Normzitate durch Markdown-Links: [§ 573 BGB](https://...)"""
    def ersetzen(treffer: re.Match) -> str:
        url = norm_url(treffer["art"], treffer["nr"], treffer["gesetz"])
        return f"[{treffer[0]}]({url})" if url else treffer[0]

    return MUSTER.sub(ersetzen, text)


# --- Unionsrecht --------------------------------------------------------------

# Art des Bezugs  ->  Suchmuster. Reihenfolge = Wichtigkeit.
UNIONSRECHT = [
    ("Vorlagebeschluss", re.compile(r"\b(?:[IVX]+[a-z]?|\d{1,2})\s+[A-Z][A-Za-z]{1,4}\s+\d{1,4}/\d{2}\s*\(A\)")),
    ("EuGH-Rechtssache", re.compile(r"\bC-\d{1,3}/\d{2}\b")),
    ("Vorabentscheidungsverfahren", re.compile(r"\bVorabentscheidung\w*|\bArt\.\s*267\s+AEUV")),
    ("Richtlinie", re.compile(r"\bRichtlinie\s+(?:\(E[GU]\)\s+)?(?:Nr\.\s*)?\d{2,4}/\d{1,4}(?:/E[GUW]{1,2}G?)?")),
    ("Rechtsprechung des EuGH", re.compile(r"\bEuGH\b|Gerichtshof der Europäischen Union")),
]


def curia_url(rechtssache: str) -> str:
    """Suche nach einer Rechtssache ("C-423/15") in der Rechtsprechungsdatenbank des EuGH."""
    return f"https://curia.europa.eu/juris/liste.jsf?num={rechtssache}"


def unionsrecht_bezuege(text: str) -> list[dict]:
    """Findet Hinweise auf Unionsrecht in einem Urteilsauszug.

    Ergebnis: [{"art": "Vorlagebeschluss", "fund": "8 AZR 848/13 (A)", "rn": 38}, ...]
    "rn" ist die Randnummer, in der die Stelle steht (0, wenn keine davor steht).
    Jeder Fund kommt nur einmal vor, mit seiner ersten Randnummer.
    """
    text = gliederung.normalisieren(text)
    gefunden: dict[tuple[str, str], dict] = {}
    for art, muster in UNIONSRECHT:
        for treffer in muster.finditer(text):
            fund = " ".join(treffer[0].split())
            if art == "Rechtsprechung des EuGH":
                fund = "EuGH"
            davor = gliederung.RANDNUMMER.findall(text[:treffer.start()])
            gefunden.setdefault((art, fund), {"art": art, "fund": fund, "rn": int(davor[-1]) if davor else 0})
    return list(gefunden.values())
