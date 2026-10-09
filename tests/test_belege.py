"""Tests für die Zitatprüfung (ohne Sprachmodell)."""
from belege import aussagen_finden, gesamturteil, markieren, quellen, saetze_teilen, zusammenfassung


def test_quellen():
    assert quellen("Das gilt [1, 3] und auch [2].") == [1, 3, 2]
    assert quellen("Ohne Beleg.") == []


def test_saetze_teilen_beachtet_abkuerzungen_und_daten():
    text = "Nach § 1 Abs. 2 KSchG gilt das z. B. ab dem 1. Juli [1]. Das Gericht entschied anders [2]."
    assert saetze_teilen(text) == ["Nach § 1 Abs. 2 KSchG gilt das z. B. ab dem 1. Juli [1].",
                                   "Das Gericht entschied anders [2]."]


def test_zitat_nach_dem_punkt_gehoert_zum_satz():
    assert saetze_teilen("Die Kündigung war unwirksam. [3] Weiter so.") == [
        "Die Kündigung war unwirksam. [3]", "Weiter so."]


def test_aussagen_finden_ignoriert_ueberschriften_und_saetze_ohne_beleg():
    antwort = "**1. Kurzantwort**\nEs kommt darauf an [1]. Ohne Beleg.\n\n- Stichpunkt mit Beleg [2]."
    assert aussagen_finden(antwort) == [
        {"satz": "Es kommt darauf an [1].", "quellen": [1]},
        {"satz": "Stichpunkt mit Beleg [2].", "quellen": [2]},
    ]


def test_gesamturteil_eine_tragende_quelle_genuegt():
    assert gesamturteil(["nein", "ja"]) == "ja"
    assert gesamturteil(["nein", "teilweise"]) == "teilweise"
    assert gesamturteil([]) == "unklar"


def test_markieren():
    antwort = "Satz eins [1]. Satz zwei [2].\n- Satz drei [1]."
    aussagen = aussagen_finden(antwort)
    for aussage, urteil in zip(aussagen, ["ja", "nein", "teilweise"]):
        aussage["urteil"] = urteil
    assert markieren(antwort, aussagen) == (
        "Satz eins [1]. :green[:material/check:] "
        ":red-background[Satz zwei \\[2\\].] :red[:material/close:]\n"
        "- :orange-background[Satz drei \\[1\\].] :orange[:material/help:]")
    assert zusammenfassung(aussagen) == {"ja": 1, "teilweise": 1, "nein": 1, "unklar": 0}


def test_randnummern_in_eckigen_klammern():
    from belege import rn_klammern
    antwort = rn_klammern("Das Gericht entschied so [Rn. 14, 15] [3].")
    assert antwort == "Das Gericht entschied so (Rn. 14, 15) [3]."
    assert aussagen_finden(antwort) == [{"satz": antwort, "quellen": [3]}]
