"""Ergänzt die KI-Antwort per Code um Angaben, die das Sprachmodell nicht zuverlässig liefert.

  metadaten_einsetzen - Gericht, Datum und Aktenzeichen in Abschnitt 3 aus der Datenbank,
                        falsche Daten oder Aktenzeichen im übrigen Text werden korrigiert
  antwort_ergaenzen   - alles zusammen, so wie es die App und bewertung.py aufrufen

Das Sprachmodell schreibt nur "[n]". Ein 12B-Modell macht aus "2016-08-11" sonst
gelegentlich "20.08.2016" - solche Fehler lassen sich nur per Code sicher vermeiden.
"""
import re

import belege
import llm

# "**3. Rechtsprechung**" oder "### 3. Rechtsprechung" - nicht aber ein Listenpunkt "3. Weiter"
ABSCHNITT = re.compile(r"^\s*(?:#{1,6}\s*\**|\*\*)\s*(\d)\.\s*[^*\n]+?\**\s*$")
STICHPUNKT = re.compile(r"^(\s*[-*+]\s+)(.*)$")
GEDANKENSTRICH = re.compile(r"\s+[–—-]\s+")
TYP_KURZ = {"Urteil": "Urt. v.", "Beschluss": "Beschl. v."}


def abschnitte(zeilen: list[str]) -> list[int]:
    """Nummer des Abschnitts, in dem jede Zeile steht (0 = vor dem ersten Abschnitt)."""
    aktuell, ergebnis = 0, []
    for zeile in zeilen:
        treffer = ABSCHNITT.match(zeile)
        if treffer:
            aktuell = int(treffer[1])
        ergebnis.append(aktuell)
    return ergebnis


def urteilskopf(t: dict) -> str:
    """"Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15" (alles aus der Datenbank)."""
    typ = TYP_KURZ.get(t.get("typ") or "", f"{t.get('typ') or 'Entscheidung'} vom")
    return (f"{t.get('gericht') or 'Gericht unbekannt'}, {typ} {llm.datum_deutsch(t.get('datum') or '')} "
            f"– {t.get('aktenzeichen')}")


def _stichpunkt_mit_kopf(inhalt: str, nach_nr: dict[int, dict]) -> str | None:
    """Setzt den Kopf aus der Datenbank vor einen Stichpunkt aus Abschnitt 3.

    "[1] – Das Gericht entschied ... [1]."  ->  "Bundesarbeitsgericht, Urt. v. ... – Das Gericht ... [1]."
    Hat das LLM trotz Anweisung selbst einen Kopf geschrieben ("BAG, 20.08.2016, 8 AZR 4/15 – ..."),
    wird dieser ersetzt. Ergebnis None: Stichpunkt bleibt unverändert.
    """
    vorne = re.match(r"\[(\d+)\]\s*(?:[–—:-]\s*)?", inhalt)
    if vorne:
        nr, rest = int(vorne[1]), inhalt[vorne.end():]
    else:
        teile = GEDANKENSTRICH.split(inhalt, maxsplit=1)
        nummern = [n for n in belege.quellen(inhalt) if n in nach_nr]
        if len(teile) < 2 or not nummern or not (belege.DATUM.search(teile[0])
                                                 or belege.AKTENZEICHEN.search(teile[0])):
            return None
        nr, rest = nummern[0], re.sub(r"^\[\d+\]\s*", "", teile[1])
    if nr not in nach_nr:
        return None
    beleg = "" if nr in belege.quellen(rest) else f" [{nr}]"
    return f"{urteilskopf(nach_nr[nr])}{beleg} – {rest}"


def metadaten_einsetzen(antwort: str, treffer: list[dict]) -> tuple[str, list[dict]]:
    """Gericht, Datum und Aktenzeichen kommen aus der Datenbank, nie vom Sprachmodell.

    1. In Abschnitt 3 bekommt jeder Stichpunkt den Kopf seines Urteils.
    2. Sicherheitsnetz für den übrigen Text: Ein Datum oder Aktenzeichen, das nicht zum
       zitierten Urteil passt, wird korrigiert (nur, wenn der Satz genau ein Urteil zitiert).
    Ergebnis: (Antwort, Korrekturen) - jede Korrektur als {"satz", "hinweis"}.
    """
    nach_nr = {t["nr"]: t for t in treffer}
    zeilen = antwort.split("\n")
    for i, abschnitt in enumerate(abschnitte(zeilen)):
        punkt = STICHPUNKT.match(zeilen[i])
        if abschnitt == 3 and punkt:
            neu = _stichpunkt_mit_kopf(punkt[2], nach_nr)
            if neu:
                zeilen[i] = punkt[1] + neu
    antwort = "\n".join(zeilen)

    korrekturen, aktuell = [], {}                      # ursprünglicher Satz -> korrigierter Satz
    for a in belege.metadaten_abweichungen(antwort, treffer):
        satz = aktuell.get(a["satz"], a["satz"])
        if not a["richtig"] or satz not in antwort:
            continue
        aktuell[a["satz"]] = satz.replace(a["gefunden"], a["richtig"], 1)
        antwort = antwort.replace(satz, aktuell[a["satz"]], 1)
        korrekturen.append({"satz": aktuell[a["satz"]], "hinweis": f"{a['art']} korrigiert: „{a['gefunden']}“ → "
                            f"„{a['richtig']}“ (laut Datenbank für [{a['nr']}])."})
    return antwort, korrekturen


def antwort_ergaenzen(antwort: str, treffer: list[dict], pruefungen: dict | None = None) -> dict:
    """Alle Ergänzungen per Code. Ergebnis: {"antwort", "korrekturen"}"""
    antwort, korrekturen = metadaten_einsetzen(belege.rn_klammern(antwort), treffer)
    return {"antwort": antwort, "korrekturen": korrekturen}
