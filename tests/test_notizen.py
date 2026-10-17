"""Tests für notizen.py. Aufruf:  pytest

Jeder Test bekommt von pytest einen eigenen leeren Ordner (tmp_path). Die echte
daten/notizen.db wird nie angefasst.
"""
import pytest

import notizen

QUELLEN = [{"id": 1, "nr": 2, "gericht": "Bundesgerichtshof", "datum": "2015-03-18",
            "aktenzeichen": "VIII ZR 185/14", "slug": "bgh-2015-03-18-viii-zr-18514"}]


@pytest.fixture
def pfad(tmp_path):
    """Eine leere Notizen-Datenbank im Wegwerf-Ordner des Tests."""
    datei = tmp_path / "notizen.db"
    notizen.tabellen_anlegen(datei)
    return datei


def speichern(pfad, akte="Mietrecht", frage="Schönheitsreparaturen?", notiz=""):
    """Kurzform für die Tests: ein Eintrag mit festen Beispielwerten."""
    return notizen.eintrag_speichern(akte, frage, "Nach den Urteilen nein [2].", QUELLEN,
                                     modell="gemma4:12b", notiz=notiz, pfad=pfad)


def test_tabellen_anlegen_zweimal_schadet_nicht(pfad):
    notizen.tabellen_anlegen(pfad)                     # zweiter Aufruf, der erste lief in der Fixture
    assert notizen.eintraege_laden(pfad=pfad) == []


def test_ordner_wird_bei_bedarf_angelegt(tmp_path):
    datei = tmp_path / "gibt_es_noch_nicht" / "notizen.db"
    notizen.tabellen_anlegen(datei)
    assert datei.exists()


def test_speichern_und_laden_ergibt_dieselben_daten(pfad):
    eintrag_id = speichern(pfad, notiz="für Montag")
    eintraege = notizen.eintraege_laden(pfad=pfad)
    assert len(eintraege) == 1
    e = eintraege[0]
    assert e["id"] == eintrag_id
    assert (e["akte"], e["frage"], e["antwort"]) == ("Mietrecht", "Schönheitsreparaturen?",
                                                     "Nach den Urteilen nein [2].")
    assert e["quellen"] == QUELLEN                     # JSON hin und zurück, Umlaute inklusive
    assert (e["modell"], e["notiz"]) == ("gemma4:12b", "für Montag")


def test_akte_ohne_namen_wird_abgelehnt(pfad):
    with pytest.raises(ValueError):
        speichern(pfad, akte="   ")


def test_akten_auflisten_nennt_jede_akte_einmal(pfad):
    speichern(pfad, akte="Mietrecht")
    speichern(pfad, akte="arbeitsrecht")
    speichern(pfad, akte="Mietrecht")
    assert notizen.akten_auflisten(pfad) == ["arbeitsrecht", "Mietrecht"]   # Groß/klein egal


def test_neue_akte_ist_schon_vor_dem_ersten_eintrag_da(pfad):
    assert notizen.akte_anlegen("  Mandat Müller ", pfad=pfad) == "Mandat Müller"
    assert notizen.akten_auflisten(pfad) == ["Mandat Müller"]
    assert notizen.eintraege_laden("Mandat Müller", pfad=pfad) == []


def test_akte_zweimal_anlegen_ergibt_eine_akte(pfad):
    notizen.akte_anlegen("Mietrecht", pfad=pfad)
    speichern(pfad, akte="Mietrecht")
    notizen.akte_anlegen("Mietrecht", pfad=pfad)
    assert notizen.akten_auflisten(pfad) == ["Mietrecht"]


def test_akte_ohne_namen_laesst_sich_nicht_anlegen(pfad):
    with pytest.raises(ValueError):
        notizen.akte_anlegen("", pfad=pfad)


def test_laden_neueste_zuerst_und_nur_eine_akte(pfad):
    erste = speichern(pfad, akte="Mietrecht", frage="erste")
    speichern(pfad, akte="Arbeitsrecht", frage="andere Akte")
    zweite = speichern(pfad, akte="Mietrecht", frage="zweite")
    eintraege = notizen.eintraege_laden("Mietrecht", pfad=pfad)
    assert [e["id"] for e in eintraege] == [zweite, erste]


def test_notiz_aendern(pfad):
    eintrag_id = speichern(pfad)
    notizen.notiz_aendern(eintrag_id, "Rn. 15 nachlesen", pfad=pfad)
    assert notizen.eintraege_laden(pfad=pfad)[0]["notiz"] == "Rn. 15 nachlesen"


def test_eintrag_loeschen(pfad):
    bleibt = speichern(pfad, frage="bleibt")
    weg = speichern(pfad, frage="weg")
    notizen.eintrag_loeschen(weg, pfad=pfad)
    assert [e["id"] for e in notizen.eintraege_laden(pfad=pfad)] == [bleibt]


def test_quellen_schnappschuss_behaelt_nur_die_angaben_zum_urteil():
    treffer = [{**QUELLEN[0], "text": "sehr langer Volltext", "punkte": 0.03}]
    assert notizen.quellen_schnappschuss(treffer) == QUELLEN


def test_quelle_text():
    assert notizen.quelle_text(QUELLEN[0]) == "[2] Bundesgerichtshof, 18.03.2015, Az. VIII ZR 185/14"
    assert notizen.quelle_text({"aktenzeichen": "1 BvR 1/20"}) == "Gericht unbekannt, Az. 1 BvR 1/20"


def test_zeitpunkt_deutsch():
    assert notizen.zeitpunkt_deutsch("2026-10-17T14:44:00") == "17.10.2026, 14:44"
    assert notizen.zeitpunkt_deutsch("unbekannt") == "unbekannt"
