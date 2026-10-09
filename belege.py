"""Zitatprüfung: Werden die Aussagen der KI-Antwort von den zitierten Urteilen gestützt?

Ablauf:
  1. aussagen_finden  - zerlegt die Antwort in Sätze und merkt sich, welche Urteile [n] jeder Satz zitiert
  2. pruefen          - lässt das LLM je zitiertem Urteil alle Sätze prüfen, die sich darauf berufen
  3. markieren        - setzt die Ergebnisse als Farbmarkierung in die Antwort ein

Die Prüfung macht ein Sprachmodell. Sie macht Fehler sichtbar, ersetzt aber
nicht den Blick ins Urteil.
"""
import re

import llm

ZITAT = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
LISTENANFANG = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)")

# Abkürzungen, nach deren Punkt KEIN neuer Satz beginnt
ABKUERZUNGEN = {"abs.", "nr.", "art.", "rn.", "az.", "vgl.", "bzw.", "ca.", "ggf.", "insb.",
                "sog.", "ziff.", "lit.", "urt.", "beschl.", "var.", "alt.", "s.", "f.", "ff.",
                "z.", "b.", "d.", "h.", "i.", "v.", "u.", "a.", "o.", "e.", "m.", "w.", "bgbl.",
                "dr.", "st.", "rspr.", "strspr.", "anm.", "aufl.", "hs.", "halbs."}

STUFEN = {"ja": 3, "teilweise": 2, "nein": 1, "unklar": 0}


def rn_klammern(antwort: str) -> str:
    """Randnummern in eckigen Klammern ("[Rn. 14, 15]") in runde setzen ("(Rn. 14, 15)").

    Eckige Klammern sind den Urteilsnummern [n] vorbehalten; sonst hält die Zitatprüfung
    "[Rn. 14" für einen eigenen Satz.
    """
    return re.sub(r"\[(Rn\.[^\]]*)\]", r"(\1)", antwort)


def quellen(satz: str) -> list[int]:
    """Alle zitierten Urteilsnummern eines Satzes: "... [1, 3] ... [2]" -> [1, 3, 2]."""
    nummern = []
    for gruppe in ZITAT.findall(satz):
        for n in re.split(r"\s*[,;]\s*", gruppe):
            if int(n) not in nummern:
                nummern.append(int(n))
    return nummern


def saetze_teilen(text: str) -> list[str]:
    """Teilt einen Absatz in Sätze, ohne an Abkürzungen ("Abs.", "z. B.") oder Daten zu trennen.

    Zitate direkt nach dem Satzende ("... entschieden. [2]") gehören noch zum Satz.
    """
    saetze, start = [], 0
    for ende in re.finditer(r"[.!?](?:\s*\[\d+(?:\s*[,;]\s*\d+)*\])*(?=\s+\S|\s*$)", text):
        if ende.group(0) == ".":
            wort = text[start:ende.end()].split()[-1].lower().lstrip("([„\"")
            if wort in ABKUERZUNGEN or re.fullmatch(r"\d+\.", wort):
                continue                               # Abkürzung oder "1. Juli": kein Satzende
        satz = text[start:ende.end()].strip()
        if satz:
            saetze.append(satz)
        start = ende.end()
    if text[start:].strip():
        saetze.append(text[start:].strip())
    return saetze


def aussagen_finden(antwort: str) -> list[dict]:
    """Alle Sätze der Antwort, die mindestens ein Urteil zitieren.

    Ergebnis: [{"satz": "...", "quellen": [2, 3]}, ...]
    """
    aussagen = []
    for zeile in antwort.split("\n"):
        if zeile.lstrip().startswith("#"):
            continue                                   # Überschriften enthalten keine Aussagen
        koerper = LISTENANFANG.sub("", zeile)
        for satz in saetze_teilen(koerper):
            if quellen(satz):
                aussagen.append({"satz": satz, "quellen": quellen(satz)})
    return aussagen


def gesamturteil(einzelurteile: list[str]) -> str:
    """Zitiert ein Satz mehrere Urteile, zählt das beste Ergebnis (eine tragende Quelle genügt)."""
    return max(einzelurteile, key=lambda u: STUFEN[u], default="unklar")


def pruefen(antwort: str, treffer: list[dict], fortschritt=None) -> list[dict]:
    """Prüft alle zitierenden Sätze der Antwort gegen die zitierten Urteile.

    Pro zitiertem Urteil gibt es EINEN Aufruf des LLM mit allen Sätzen, die es
    zitieren. fortschritt(nr, anzahl) wird vor jedem Aufruf aufgerufen (für die Anzeige).
    Ergebnis: Aussagen aus aussagen_finden, ergänzt um "urteil" und "hinweise".
    """
    aussagen = aussagen_finden(rn_klammern(antwort))
    nach_nr = {t["nr"]: t for t in treffer}
    je_quelle: dict[int, list[int]] = {}               # Urteilsnummer -> Indizes der Aussagen
    for i, aussage in enumerate(aussagen):
        aussage.update(einzel=[], hinweise=[])
        for n in aussage["quellen"]:
            if n in nach_nr:
                je_quelle.setdefault(n, []).append(i)
            else:
                aussage["einzel"].append("nein")
                aussage["hinweise"].append(f"[{n}] gibt es in der Trefferliste nicht.")

    for schritt, (n, indizes) in enumerate(sorted(je_quelle.items()), 1):
        if fortschritt:
            fortschritt(schritt, len(je_quelle))
        texte = [ZITAT.sub("", aussagen[i]["satz"]).strip() for i in indizes]
        for i, ergebnis in zip(indizes, llm.aussagen_pruefen(nach_nr[n], texte)):
            aussagen[i]["einzel"].append(ergebnis["urteil"])
            if ergebnis["hinweis"]:
                aussagen[i]["hinweise"].append(f"[{n}] {ergebnis['hinweis']}")

    for aussage in aussagen:
        aussage["urteil"] = gesamturteil(aussage.pop("einzel"))
    return aussagen


def _maskieren(satz: str) -> str:
    """Eckige Klammern maskieren, damit Streamlits Farbsyntax :farbe[...] nicht durcheinanderkommt."""
    return satz.replace("[", "\\[").replace("]", "\\]")


def markieren(antwort: str, aussagen: list[dict]) -> str:
    """Setzt die Prüfergebnisse als Streamlit-Markdown in die Antwort ein.

    gestützt: grünes Häkchen · teilweise: orange hinterlegt · nicht gestützt: rot hinterlegt
    """
    zeichen = {
        "ja": lambda s: f"{s} :green[:material/check:]",
        "teilweise": lambda s: f":orange-background[{_maskieren(s)}] :orange[:material/help:]",
        "nein": lambda s: f":red-background[{_maskieren(s)}] :red[:material/close:]",
        "unklar": lambda s: f"{s} :gray[:material/question_mark:]",
    }
    zeilen = antwort.split("\n")
    z = 0                                              # Aussagen kommen in Reihenfolge der Antwort
    for aussage in aussagen:
        for k in range(z, len(zeilen)):
            if aussage["satz"] in zeilen[k]:
                markiert = zeichen[aussage["urteil"]](aussage["satz"])
                zeilen[k] = zeilen[k].replace(aussage["satz"], markiert, 1)
                z = k
                break
    return "\n".join(zeilen)


def zusammenfassung(aussagen: list[dict]) -> dict[str, int]:
    """Zählt die Ergebnisse: {"ja": 7, "teilweise": 2, "nein": 1, "unklar": 0}"""
    zaehler = {stufe: 0 for stufe in STUFEN}
    for aussage in aussagen:
        zaehler[aussage["urteil"]] += 1
    return zaehler
