"""Zitatprüfung: Werden die Aussagen der KI-Antwort von den zitierten Urteilen gestützt?

Ablauf:
  1. aussagen_finden  - zerlegt die Antwort in Sätze und merkt sich, welche Urteile [n] jeder Satz zitiert
  2. pruefen          - lässt das LLM je zitiertem Urteil alle Sätze prüfen, die sich darauf berufen
  3. markieren        - setzt die Ergebnisse als Farbmarkierung in die Antwort ein

Geprüft werden nur Aussagen über Urteilsinhalte. Hinweis-Sätze ("muss am Volltext geprüft
werden", alles in Abschnitt 5) bekommen den Status "hinweis" und werden nicht gezählt.
Zeilen, die mit ">" beginnen, hat der Code selbst ergänzt (siehe ergaenzung.py) - sie
werden gar nicht geprüft.

Die Prüfung macht ein Sprachmodell. Sie macht Fehler sichtbar, ersetzt aber
nicht den Blick ins Urteil.
"""
import re

import llm

ZITAT = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
LISTENANFANG = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)")
# "**3. Rechtsprechung**" oder "### 3. Rechtsprechung" - nicht aber ein Listenpunkt "3. Weiter"
ABSCHNITT = re.compile(r"^\s*(?:#{1,6}\s*\**|\*\*)\s*(\d)\.\s*[^*\n]+?\**\s*$")
NICHT_BEANTWORTET = 5                                  # Abschnitt "Was die Urteile nicht beantworten"
# Sätze, die nichts über den Inhalt eines Urteils behaupten
HINWEIS_SATZ = re.compile(
    r"(?:am|im) Volltext (?:zu )?(?:prüfen|geprüft|nachzulesen)|keine gefunden"
    r"|das (?:vorliegende )?Material (?:beantwortet|sagt|enthält|äußert sich|lässt)[^.]{0,60}?nicht"
    r"|keine Rechtsberatung|(?:nicht|kaum) beantwortet|lässt sich (?:dem Material|den Urteilen) nicht entnehmen",
    re.IGNORECASE)

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


def abschnitte(zeilen: list[str]) -> list[int]:
    """Nummer des Abschnitts, in dem jede Zeile steht (0 = vor dem ersten Abschnitt)."""
    aktuell, ergebnis = 0, []
    for zeile in zeilen:
        treffer = ABSCHNITT.match(zeile)
        if treffer:
            aktuell = int(treffer[1])
        ergebnis.append(aktuell)
    return ergebnis


def aussagen_finden(antwort: str) -> list[dict]:
    """Alle Sätze der Antwort, die mindestens ein Urteil zitieren.

    Ergebnis: [{"satz": "...", "quellen": [2, 3], "hinweis": False}, ...]
    "hinweis" ist True bei Sätzen, die nichts über ein Urteil behaupten (werden nicht geprüft).
    """
    aussagen = []
    zeilen = antwort.split("\n")
    for zeile, abschnitt in zip(zeilen, abschnitte(zeilen)):
        if zeile.lstrip().startswith(("#", ">")):
            continue                                   # Überschriften und Ergänzungen per Code
        koerper = LISTENANFANG.sub("", zeile)
        for satz in saetze_teilen(koerper):
            if quellen(satz):
                hinweis = abschnitt == NICHT_BEANTWORTET or bool(HINWEIS_SATZ.search(satz))
                aussagen.append({"satz": satz, "quellen": quellen(satz), "hinweis": hinweis})
    return aussagen


def gesamturteil(einzelurteile: list[str]) -> str:
    """Zitiert ein Satz mehrere Urteile, gilt er nur als gestützt, wenn ALLE ihn tragen.

    Alle gleich -> dieses Ergebnis; gemischt (z. B. ja + nein) -> "teilweise".
    """
    if not einzelurteile:
        return "unklar"
    return einzelurteile[0] if len(set(einzelurteile)) == 1 else "teilweise"


def _quellenhinweis(n: int, urteil: str, hinweis: str) -> str:
    """Warum eine Quelle die Aussage nicht (ganz) trägt, z. B. "[3] stützt diese Aussage nicht: ..." """
    text = {"nein": f"[{n}] stützt diese Aussage nicht", "teilweise": f"[{n}] stützt sie nur teilweise",
            "unklar": f"[{n}] konnte nicht geprüft werden"}[urteil]
    return f"{text}: {hinweis}" if hinweis else f"{text}."


def pruefen(antwort: str, treffer: list[dict], fortschritt=None) -> list[dict]:
    """Prüft alle zitierenden Sätze der Antwort gegen die zitierten Urteile.

    Pro zitiertem Urteil gibt es EINEN Aufruf des LLM mit allen Sätzen, die es
    zitieren. fortschritt(nr, anzahl) wird vor jedem Aufruf aufgerufen (für die Anzeige).
    Ergebnis: Aussagen aus aussagen_finden, ergänzt um "urteil" und "hinweise"
    (je Quelle, die die Aussage nicht trägt). Hinweis-Sätze haben das Urteil "hinweis".
    """
    aussagen = aussagen_finden(rn_klammern(antwort))
    nach_nr = {t["nr"]: t for t in treffer}
    je_quelle: dict[int, list[int]] = {}               # Urteilsnummer -> Indizes der Aussagen
    for i, aussage in enumerate(aussagen):
        aussage.update(einzel=[], hinweise=[])
        if aussage["hinweis"]:
            continue
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
            if ergebnis["urteil"] != "ja":
                aussagen[i]["hinweise"].append(_quellenhinweis(n, ergebnis["urteil"], ergebnis["hinweis"]))

    for aussage in aussagen:
        einzel = aussage.pop("einzel")
        aussage["urteil"] = "hinweis" if aussage["hinweis"] else gesamturteil(einzel)
    return aussagen


# --- Gericht, Datum und Aktenzeichen in der Antwort ----------------------------

MONATE = {"januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
DATUM = re.compile(r"\b(\d{1,2})\.\s?(?:(\d{1,2})\.|(" + "|".join(MONATE) + r")\s)\s?(\d{4})\b"
                   r"|\b(\d{4})-(\d{2})-(\d{2})\b", re.IGNORECASE)
# "8 AZR 4/15", "VIII ZR 232/15", "1 BvL 7/16", "2 StR 519/20"
AKTENZEICHEN = re.compile(r"\b(?:[IVX]+[a-z]?|\d{1,2})\s+[A-Z][A-Za-z]{1,4}\s+\d{1,4}/\d{2}\b")


def daten_finden(text: str) -> list[tuple[str, str]]:
    """Alle Datumsangaben im Text als (Fundtext, JJJJ-MM-TT).

    Erkennt "11.08.2016", "11. August 2016" und "2016-08-11".
    """
    gefunden = []
    for m in DATUM.finditer(text):
        if m[5]:
            iso = f"{m[5]}-{m[6]}-{m[7]}"
        else:
            monat = int(m[2]) if m[2] else MONATE[m[3].lower()]
            iso = f"{m[4]}-{monat:02d}-{int(m[1]):02d}"
        gefunden.append((m[0], iso))
    return gefunden


def _az(aktenzeichen: str) -> str:
    return " ".join((aktenzeichen or "").split())


def _material(t: dict) -> str:
    """Der Text, den das LLM über ein Urteil gesehen hat (dort zitierte Daten sind erlaubt):
    Leitsatz, Tenor, Auszüge und die Hinweise auf spätere Rechtsprechungsänderungen."""
    teile = [str(t.get(feld) or "") for feld in ("leitsatz", "tenor", "kontext", "bewertung")]
    teile += [f"{a.get('datum')} {a.get('aktenzeichen')}" for a in t.get("abweichungen") or []]
    return " ".join(teile)


def _bekannt(az: str, erlaubte: set[str]) -> bool:
    """"14 AS 19/14" ist Teil von "B 14 AS 19/14 R" - das Muster erfasst Vor- und Nachsilben nicht."""
    return any(_az(az) in e for e in erlaubte)


def metadaten_abweichungen(antwort: str, treffer: list[dict]) -> list[dict]:
    """Findet Daten und Aktenzeichen in der Antwort, die nicht zum zitierten Urteil passen.

    Erlaubt ist, was zum Kopf eines zitierten Urteils gehört oder in dessen Material steht
    (Urteile zitieren andere Urteile), außerdem Aktenzeichen anderer Treffer samt ihrem Datum.
    Ergebnis je Fund:
    {"satz", "art": "Datum" | "Aktenzeichen", "gefunden", "richtig" (nur bei genau einer Quelle), "nr"}
    """
    nach_nr = {t["nr"]: t for t in treffer}
    abweichungen = []
    for aussage in aussagen_finden(antwort):
        zitierte = [nach_nr[n] for n in aussage["quellen"] if n in nach_nr]
        if not zitierte:
            continue
        einzige = zitierte[0] if len(zitierte) == 1 else None
        material = " ".join(_material(t) for t in zitierte)
        genannte = [t for t in treffer if _az(t["aktenzeichen"]) in _az(aussage["satz"])]
        erlaubte_daten = ({t["datum"] for t in zitierte + genannte}
                          | {iso for _, iso in daten_finden(material)})
        for fund, iso in daten_finden(aussage["satz"]):
            if iso not in erlaubte_daten:
                abweichungen.append({"satz": aussage["satz"], "art": "Datum", "gefunden": fund,
                                     "richtig": llm.datum_deutsch(einzige["datum"]) if einzige else None,
                                     "nr": einzige["nr"] if einzige else None})
        erlaubte_az = {_az(t["aktenzeichen"]) for t in treffer} | {_az(material)}
        for fund in AKTENZEICHEN.findall(aussage["satz"]):
            if not _bekannt(fund, erlaubte_az):
                abweichungen.append({"satz": aussage["satz"], "art": "Aktenzeichen", "gefunden": fund,
                                     "richtig": einzige["aktenzeichen"] if einzige else None,
                                     "nr": einzige["nr"] if einzige else None})
    return abweichungen


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
        "hinweis": lambda s: f"{s} :gray[:material/info:]",
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
    """Zählt die Ergebnisse: {"ja": 7, "teilweise": 2, "nein": 1, "unklar": 0, "hinweis": 2}"""
    zaehler = {stufe: 0 for stufe in [*STUFEN, "hinweis"]}
    for aussage in aussagen:
        zaehler[aussage["urteil"]] += 1
    return zaehler
