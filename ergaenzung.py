"""Ergänzt die KI-Antwort per Code um Angaben, die das Sprachmodell nicht zuverlässig liefert.

  metadaten_einsetzen - Gericht, Datum und Aktenzeichen in Abschnitt 3 aus der Datenbank,
                        falsche Daten oder Aktenzeichen im übrigen Text werden korrigiert
  aenderungen_block   - Abschnitt 4: Rechtsprechungsänderungen (ändernde und dort zitierte Urteile)
  unionsrecht_block   - Abschnitt 5: Bezüge zum Unionsrecht (EuGH-Vorlagen, Richtlinien)
  antwort_ergaenzen   - alles zusammen, so wie es die App und bewertung.py aufrufen

Ergänzte Blöcke beginnen mit ">" (Zitat-Markdown): So sind sie als automatisch erkennbar,
und die Zitatprüfung lässt sie aus.

Das Sprachmodell schreibt nur "[n]". Ein 12B-Modell macht aus "2016-08-11" sonst
gelegentlich "20.08.2016" - solche Fehler lassen sich nur per Code sicher vermeiden.
"""
import re

import abweichung
import belege
import config
import llm
import normen
import suche

STICHPUNKT = re.compile(r"^(\s*[-*+]\s+)(.*)$")
GEDANKENSTRICH = re.compile(r"\s+[–—-]\s+")
TYP_KURZ = {"Urteil": "Urt. v.", "Beschluss": "Beschl. v."}


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
    for i, abschnitt in enumerate(belege.abschnitte(zeilen)):
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


def einfuegen(antwort: str, abschnitt: int, block: str) -> str:
    """Hängt einen Block an das Ende eines Abschnitts an (vor die Überschrift des nächsten).

    Fehlt der Abschnitt, kommt der Block ans Ende der Antwort.
    """
    if not block:
        return antwort
    zeilen = antwort.rstrip().split("\n")
    nummern = belege.abschnitte(zeilen)
    ende = next((i for i, n in enumerate(nummern) if n > abschnitt), len(zeilen))
    while ende > 0 and not zeilen[ende - 1].strip():
        ende -= 1                                      # Leerzeilen am Abschnittsende überspringen
    rest = zeilen[ende:]
    if rest and rest[0].strip():
        rest = [""] + rest                             # Leerzeile vor der nächsten Überschrift
    return "\n".join(zeilen[:ende] + ["", block] + rest).rstrip() + "\n"


def _verweis(u: dict) -> str:
    """"[1] Bundesarbeitsgericht, Urt. v. ..." - ohne Treffernummer mit Link zum Volltext."""
    if u.get("nr"):
        return f"[{u['nr']}] {urteilskopf(u)}"
    return f"{urteilskopf(u)} ([Volltext](https://de.openlegaldata.io/case/{u['slug']}))"


def aenderungen_block(gruppen: list[dict]) -> str:
    """Abschnitt 4: Rechtsprechungsänderungen als fester Block, per Code statt per LLM.

    Trennt sauber zwischen der Entscheidung, die eine Änderung beschreibt, und den früheren
    Treffern, die sie dabei zitiert. Ob diese die alte oder die neue Linie vertreten, wird
    bewusst nicht behauptet (siehe abweichung.py) - dafür gibt es die Originalstelle.
    """
    if not gruppen:
        return ""
    zeilen = ["> **Rechtsprechungsänderung** · automatisch erkannt, bitte im Volltext prüfen"]
    for g in gruppen:
        erklaerung = " ".join(g["erklaerung"].split())
        frueher = "; ".join(_verweis(b["treffer"]) for b in g["betroffen"])
        ob = ("Ob diese Entscheidungen die alte oder die neue Linie vertreten" if len(g["betroffen"]) > 1
              else "Ob diese Entscheidung die alte oder die neue Linie vertritt")
        aendernd = ("**Ändernde Entscheidung:**" if len(g["aendernd"]) == 1
                    else "**Ändernde Entscheidungen** (gleichlautende Serie):")
        zeilen += [">",
                   f"> - {aendernd} " + "; ".join(_verweis(a) for a in g["aendernd"])
                   + (f". {erklaerung}" if erklaerung else ""),
                   f"> - **Dort zitiert:** {frueher}. {ob}, zeigt die Originalstelle."]
    return "\n".join(zeilen)


def _ohne_doppelte(bezuege: list[dict]) -> list[dict]:
    """Jeder Fund nur einmal; der allgemeine Verweis "EuGH" entfällt, wenn ein genauerer da ist."""
    eindeutig = list({(b["art"], b["fund"]): b for b in reversed(bezuege)}.values())[::-1]
    if any(b["art"] in ("Vorlage", "Vorlagebeschluss", "EuGH-Rechtssache") for b in eindeutig):
        eindeutig = [b for b in eindeutig if b["art"] != "Rechtsprechung des EuGH"]
    return eindeutig


def unionsrecht_finden(t: dict, randnummern: list[int] | None = None) -> list[dict]:
    """Unionsrechtliche Bezüge eines Treffers: in Leitsatz und Tenor sowie im Auszug.

    Hat die Einzelprüfung Randnummern genannt, zählen im Auszug nur Bezüge in genau diesen
    Randnummern - dort steht die Begründung, auf die sich die Antwort stützt.
    Ist der Treffer selbst eine Vorlage an den EuGH, steht das an erster Stelle.
    """
    text = "\n\n".join(str(t.get(feld) or "") for feld in ("kontext", "bewertung"))
    bezuege = normen.unionsrecht_bezuege(text)
    if randnummern:
        bezuege = [b for b in bezuege if b["rn"] in randnummern]
    kopf = "\n\n".join(str(t.get(feld) or "") for feld in ("leitsatz", "tenor"))
    bezuege = [{**b, "rn": 0} for b in normen.unionsrecht_bezuege(kopf)] + bezuege
    if "vorlage" in (t.get("typ") or "").lower():
        bezuege.insert(0, {"art": "Vorlage", "fund": "", "rn": 0})
    return _ohne_doppelte(bezuege)


def _bezug_text(b: dict) -> str:
    """"Vorlagebeschluss 8 AZR 848/13 (A) (Rn. 38)" - mit Link, wo es einen gibt."""
    fund = b["fund"]
    im_bestand = suche.urteil_nach_aktenzeichen(fund) if b["art"] in ("Vorlagebeschluss", "EuGH-Rechtssache") else None
    if im_bestand:
        fund = f"[{fund}](https://de.openlegaldata.io/case/{im_bestand['slug']})"
    elif b["art"] == "EuGH-Rechtssache":
        fund = f"[{fund}]({normen.curia_url(fund)})"
    if b["art"] == "Vorlage":
        text = "Die Entscheidung ist selbst eine Vorlage an den EuGH"
    elif b["art"] in ("Richtlinie", "Rechtsprechung des EuGH"):
        text = fund if b["art"] == "Richtlinie" else "Verweis auf Rechtsprechung des EuGH"
    elif b["art"] == "Vorabentscheidungsverfahren":
        text = f"Vorabentscheidungsverfahren („{fund}“)"
    else:
        text = f"{b['art']} {fund}"
    return text + (f" (Rn. {b['rn']})" if b["rn"] else "")


def unionsrecht_block(ausgewertet: list[dict], pruefungen: dict | None = None,
                      gruppen: list[dict] = ()) -> str:
    """Abschnitt 5: Bezüge zum Unionsrecht, die das Modell sonst übersieht.

    Gesucht wird in den zitierten Randnummern der ausgewerteten Treffer und in den
    Originalstellen zu Rechtsprechungsänderungen (gruppen aus abweichung.entwicklung):
    Dort steht oft, welche Vorlage an den EuGH die Änderung ausgelöst hat.
    Die Entscheidungen des EuGH selbst sind nicht im Bestand und werden nicht ausgewertet -
    der Block sagt das ausdrücklich, damit die Lücke sichtbar bleibt.
    """
    funde: dict[str, list[dict]] = {}                   # Bezeichnung der Fundstelle -> Bezüge
    for t in ausgewertet:
        randnummern = (pruefungen or {}).get(t["nr"], {}).get("randnummern")
        funde[f"[{t['nr']}] {t['aktenzeichen']}"] = unionsrecht_finden(t, randnummern)
    for g in gruppen:
        for b in g["betroffen"]:
            von = b["von"]
            name = (f"[{von['nr']}] " if von.get("nr") else "") + f"{von['aktenzeichen']}, Stelle zur Rechtsprechungsänderung"
            funde.setdefault(name, []).extend(normen.unionsrecht_bezuege(b["stelle"]))
    zeilen = [f"> - {name}: " + "; ".join(_bezug_text(b) for b in _ohne_doppelte(bezuege))
              for name, bezuege in funde.items() if bezuege]
    if not zeilen:
        return ""
    return "\n".join(["> **Unionsrecht** · automatisch erkannt", ">", *zeilen, ">",
                      "> Die Entscheidungen des EuGH sind nicht im Bestand und wurden nicht ausgewertet. "
                      "Ob sie die Antwort ändern, muss gesondert geprüft werden."])


def antwort_ergaenzen(antwort: str, treffer: list[dict], pruefungen: dict | None = None) -> dict:
    """Alle Ergänzungen per Code, so wie sie die App und bewertung.py aufrufen.

    treffer sind alle Treffer (mit "abweichungen", falls geprüft), pruefungen das Ergebnis
    der Einzelprüfung. Berücksichtigt werden die Urteile, die das Modell ausgewertet hat.
    Ergebnis: {"antwort", "korrekturen", "entwicklung"}
    """
    if pruefungen is None:
        ausgewertet = treffer[: config.KI_TREFFER]
    else:
        ausgewertet = [t for t in treffer if pruefungen.get(t["nr"], {}).get("relevant")]

    antwort, korrekturen = metadaten_einsetzen(belege.rn_klammern(antwort), treffer)
    gruppen = abweichung.entwicklung(ausgewertet)
    antwort = einfuegen(antwort, 4, aenderungen_block(gruppen))
    antwort = einfuegen(antwort, 5, unionsrecht_block(ausgewertet, pruefungen, gruppen))
    return {"antwort": antwort, "korrekturen": korrekturen, "entwicklung": gruppen}
