"""Tests für die Ergänzungen der KI-Antwort per Code (ohne Sprachmodell)."""
from belege import abschnitte, daten_finden, metadaten_abweichungen
from ergaenzung import metadaten_einsetzen, urteilskopf

BAG = {"nr": 1, "gericht": "Bundesarbeitsgericht", "typ": "Urteil", "datum": "2016-08-11",
       "aktenzeichen": "8 AZR 4/15", "kontext": "38\n:   Vgl. BAG 23. August 2012 - 8 AZR 285/11 - Rn. 18."}
BGH = {"nr": 2, "gericht": "Bundesgerichtshof", "typ": "Beschluss", "datum": "2016-12-14",
       "aktenzeichen": "VIII ZR 232/15"}


def test_daten_finden_in_allen_formaten():
    assert daten_finden("am 11.08.2016, am 23. August 2012 und am 2016-12-14") == [
        ("11.08.2016", "2016-08-11"), ("23. August 2012", "2012-08-23"), ("2016-12-14", "2016-12-14")]


def test_urteilskopf_aus_der_datenbank():
    assert urteilskopf(BAG) == "Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15"
    assert urteilskopf(BGH) == "Bundesgerichtshof, Beschl. v. 14.12.2016 – VIII ZR 232/15"


def test_abschnitte_erkennen_fette_ueberschriften_nicht_aber_listen():
    zeilen = ["**1. Kurzantwort**", "Text", "1. Listenpunkt", "### 3. Rechtsprechung", "- [1] – x"]
    assert abschnitte(zeilen) == [1, 1, 1, 3, 3]


def test_kopf_in_abschnitt_3_wird_eingesetzt():
    antwort = "**3. Rechtsprechung**\n- [1] – Das Gericht entschied, der Begriff ist formal (Rn. 38).\n- [2] – Ja [2]."
    neu, korrekturen = metadaten_einsetzen(antwort, [BAG, BGH])
    assert neu.split("\n")[1:] == [
        "- Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15 [1] – Das Gericht entschied, "
        "der Begriff ist formal (Rn. 38).",
        "- Bundesgerichtshof, Beschl. v. 14.12.2016 – VIII ZR 232/15 – Ja [2]."]
    assert korrekturen == []


def test_selbst_geschriebener_kopf_wird_ersetzt():
    antwort = "**3. Rechtsprechung**\n- Bundesarbeitsgericht, 20.08.2016, Az. 8 AZR 4/15 – Formaler Begriff [1]."
    neu, _ = metadaten_einsetzen(antwort, [BAG])
    assert neu.endswith("- Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15 – Formaler Begriff [1].")


def test_falsches_datum_wird_korrigiert_und_vermerkt():
    antwort = "**1. Kurzantwort**\nDas BAG entschied am 20.08.2016, der Begriff sei formal [1]."
    assert metadaten_abweichungen(antwort, [BAG])[0]["gefunden"] == "20.08.2016"
    neu, korrekturen = metadaten_einsetzen(antwort, [BAG])
    assert "am 11.08.2016" in neu and "20.08.2016" not in neu
    assert len(korrekturen) == 1 and "20.08.2016" in korrekturen[0]["hinweis"]


def test_im_urteil_zitierte_entscheidungen_sind_keine_abweichung():
    antwort = "Das BAG verweist auf sein Urteil vom 23. August 2012 (8 AZR 285/11) [1]."
    assert metadaten_abweichungen(antwort, [BAG]) == []


def test_falsches_aktenzeichen_bei_mehreren_quellen_nur_gemeldet():
    antwort = "So entschieden in 8 AZR 99/15 [1, 2]."
    abweichung = metadaten_abweichungen(antwort, [BAG, BGH])
    assert abweichung[0]["art"] == "Aktenzeichen" and abweichung[0]["richtig"] is None
    assert metadaten_einsetzen(antwort, [BAG, BGH])[0] == antwort
