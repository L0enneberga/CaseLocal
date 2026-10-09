"""Erkennt Normzitate wie "§ 573 Abs. 2 BGB" oder "Art. 3 GG" im Text
und verlinkt sie auf gesetze-im-internet.de. Außerdem: Bezüge zum Unionsrecht
(EuGH-Vorlagen, Rechtssachen, Richtlinien), siehe unionsrecht_bezuege.

Verlinkt werden nur Gesetze aus der Liste GESETZE, damit keine
falschen Links entstehen. Weitere Gesetze einfach ergänzen: Die
Kurzform in der Adresse steht auf gesetze-im-internet.de in der
Adresszeile, z. B. https://www.gesetze-im-internet.de/kschg/
"""
import re

import gliederung

# Abkürzung im Urteil  ->  Kurzform in der Adresse bei gesetze-im-internet.de
GESETZE = {
    "BGB": "bgb", "ZPO": "zpo", "StGB": "stgb", "StPO": "stpo", "HGB": "hgb",
    "GG": "gg", "VwGO": "vwgo", "VwVfG": "vwvfg", "GVG": "gvg", "ArbGG": "arbgg",
    "KSchG": "kschg", "BetrVG": "betrvg", "SGG": "sgg", "FGO": "fgo", "AO": "ao_1977",
    "EStG": "estg", "InsO": "inso", "GmbHG": "gmbhg", "UrhG": "urhg", "BRAO": "brao",
}

# § 573 BGB | § 573a Abs. 2 S. 1 BGB | Art. 3 Abs. 1 GG
MUSTER = re.compile(
    r"(?P<art>§|Art\.)\s*(?P<nr>\d+[a-z]?)"
    r"(?:\s+(?:Abs\.|S\.|Satz|Nr\.)\s*\d+[a-z]?)*"
    r"\s+(?P<gesetz>[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*)\b"
)


def norm_url(art: str, nr: str, gesetz: str) -> str | None:
    """Baut die Adresse einer Norm, z. B. ("§", "573", "BGB") -> .../bgb/__573.html"""
    kurz = GESETZE.get(gesetz)
    if kurz is None:
        return None
    seite = f"art_{nr}" if art == "Art." else f"__{nr}"
    return f"https://www.gesetze-im-internet.de/{kurz}/{seite}.html"


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
