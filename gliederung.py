"""Erkennt die Gliederung eines Urteils: Leitsatz, Tenor, Tatbestand, Gründe und Randnummern.

Die Urteile von Open Legal Data liegen als Markdown vor, meist so:

    ## Tenor
    :   Die Berufung wird zurückgewiesen.

    ## Gründe
    15
    :   Die Kündigung ist sozial ungerechtfertigt ...

Überschriften (#) trennen die Teile, eine Zahl auf eigener Zeile vor ":" ist die Randnummer.

Manche Gerichte (z. B. aus NRW) nutzen ein zweites Format: Überschriften ohne #
("**T a t b e s t a n d**", "Entscheidungsgründe:") und Randnummern auf eigener
Zeile, gefolgt von einer Leerzeile. normalisieren() bringt beides auf das erste Format.
"""
import re

# Überschrift im Urteil (Anfang, Groß-/Kleinschreibung egal)  ->  Teil, unter dem wir sie führen
TEILE = [
    (r"leitsatz|leitsätze|orientierungssatz", "Leitsatz"),
    (r"tenor", "Tenor"),
    (r"tatbestand|sachverhalt", "Tatbestand"),
    (r"entscheidungsgründe|gründe", "Gründe"),
    (r"verfahrensgang", "Verfahrensgang"),
    (r"fußnote|hinweis|anmerkung|literatur|weitere fundstellen|diese entscheidung", "Sonstiges"),
]

UEBERSCHRIFT = re.compile(r"^#{1,6}\s*(.+?)\s*$")
RANDNUMMER = re.compile(r"(?m)^(\d{1,4})\n:")
# Überschriften ohne #: nur, wenn die ganze Zeile genau eines dieser Wörter ist
OHNE_RAUTE = re.compile(r"tenor|tatbestand|gründe|entscheidungsgründe|leitsatz|leitsätze"
                        r"|orientierungssatz|verfahrensgang")


def normalisieren(text: str) -> str:
    """Bringt das zweite Randnummern-Format auf das erste und entfernt Datenmüll.

    "15\\n\\nDie Kündigung ..."  ->  "15\\n:   Die Kündigung ..."
    """
    text = re.sub(r"(?m)^#*blob#*nbsp;?\s*$", "", text)          # Rest aus der Datenaufbereitung
    return re.sub(r"(?m)^(\d{1,4})[ \t]*\n[ \t]*\n(?=[^\s\d])", r"\1\n:   ", text)


def _kompakt(zeile: str) -> str:
    """'**G r ü n d e :**' -> 'gründe' (Formatierung und Sperrschrift entfernen)."""
    sauber = zeile.strip().lstrip(":").strip("#*: ").strip()
    if re.fullmatch(r"(\w ){2,}\w", sauber):                       # g e s p e r r t
        sauber = sauber.replace(" ", "")
    return sauber.lower()


def teil_von(ueberschrift: str) -> str | None:
    """Ordnet eine Überschrift einem Teil zu. Unbekannte Überschriften ergeben None."""
    sauber = _kompakt(ueberschrift)
    for muster, teil in TEILE:
        if re.match(muster, sauber):
            return teil
    return None


def _ueberschrift(zeile: str) -> str | None:
    """Erkennt eine Überschriftenzeile und liefert ihren Teil, sonst None."""
    treffer = UEBERSCHRIFT.match(zeile)
    if treffer:
        return teil_von(treffer[1])
    if len(zeile) < 45 and OHNE_RAUTE.fullmatch(_kompakt(zeile)):
        return teil_von(zeile)
    return None


def teile_erkennen(text: str) -> list[tuple[str, str]]:
    """Zerlegt ein Urteil an seinen Überschriften.

    Ergebnis z. B.: [("Tenor", "..."), ("Tatbestand", "..."), ("Gründe", "...")]
    Unbekannte Zwischenüberschriften bleiben im laufenden Teil. Text vor der
    ersten Überschrift läuft unter "Sonstiges".
    """
    teile: list[tuple[str, str]] = []
    aktuell, zeilen = "Sonstiges", []
    for zeile in normalisieren(text).split("\n"):
        neuer_teil = _ueberschrift(zeile)
        if neuer_teil:
            teile.append((aktuell, "\n".join(zeilen).strip()))
            aktuell, zeilen = neuer_teil, []
        else:
            zeilen.append(zeile)
    teile.append((aktuell, "\n".join(zeilen).strip()))
    # Eine Randnummer direkt vor der nächsten Überschrift gehört zu keinem Text mehr
    teile = [(teil, re.sub(r"\n\s*\d{1,4}$", "", inhalt).strip()) for teil, inhalt in teile]
    return [(teil, inhalt) for teil, inhalt in teile if inhalt]


def teil_text(text: str, gesuchter_teil: str, max_zeichen: int = 1200) -> str:
    """Liefert den Text eines Teils (z. B. "Tenor"), gekürzt auf max_zeichen."""
    inhalt = "\n\n".join(i for t, i in teile_erkennen(text) if t == gesuchter_teil)
    if len(inhalt) > max_zeichen:
        inhalt = inhalt[:max_zeichen].rsplit(" ", 1)[0] + " […]"
    return inhalt


def randnummern(text: str) -> list[int]:
    """Alle Randnummern in einem Text, z. B. [15, 16, 17]."""
    return [int(n) for n in RANDNUMMER.findall(text)]


def fundstelle(teil: str, rn_von: int, rn_bis: int) -> str:
    """Kurze Bezeichnung eines Abschnitts, z. B. "Gründe, Rn. 15–17"."""
    if not rn_von:
        return teil
    if rn_von == rn_bis:
        return f"{teil}, Rn. {rn_von}"
    return f"{teil}, Rn. {rn_von}–{rn_bis}"


def lesbar(text: str, markdown: bool = False) -> str:
    """Macht die Randnummern lesbar: "15\\n:   Text" wird zu "Rn. 15: Text".

    Mit markdown=True wird die Randnummer fett gesetzt (für die Anzeige in der App).
    """
    ersatz = r"**Rn. \1** " if markdown else r"Rn. \1: "
    text = re.sub(r"(?m)^(\d{1,4})\n:\s+", ersatz, text)
    text = re.sub(r"(?m)^:\s+", "", text)                # Absätze ohne Randnummer
    return re.sub(r"(?m)^[^\S\n]+", "", text)            # Einrückungen (auch geschützte Leerzeichen)
                                                         # wären in Markdown Codeblöcke


def ab_randnummer(text: str, hoechstens: int = 400) -> str:
    """Beginnt ein Abschnitt mitten im Satz, lässt die Anzeige ihn ab der ersten Randnummer beginnen."""
    erste = RANDNUMMER.search(text)
    if erste and 0 < erste.start() <= hoechstens:
        return text[erste.start():]
    return text
