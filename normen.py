"""Erkennt Normzitate wie "§ 573 Abs. 2 BGB" oder "Art. 3 GG" im Text
und verlinkt sie auf gesetze-im-internet.de.

Verlinkt werden nur Gesetze aus der Liste GESETZE, damit keine
falschen Links entstehen. Weitere Gesetze einfach ergänzen: Die
Kurzform in der Adresse steht auf gesetze-im-internet.de in der
Adresszeile, z. B. https://www.gesetze-im-internet.de/kschg/
"""
import re

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
