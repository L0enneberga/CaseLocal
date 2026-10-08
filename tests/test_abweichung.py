"""Tests für den Hinweis auf Rechtsprechungsänderungen (ohne Sprachmodell)."""
from abweichung import az_muster, fundstellen, verdaechtige_stellen

TEXT = ("Einleitung. " * 80 + "Der Senat hält an seiner Rechtsprechung (Urteil vom 1. Juli 2010 - VIII ZR 12/09) "
        "nicht mehr fest. " + "Weiter im Text. " * 40 + "Vgl. auch BGH, VIII ZR 99/09, NJW 2010, 1.")


def test_az_muster_toleriert_leerzeichen():
    assert az_muster("VIII ZR 12/09").search("VIII ZR 12 / 09")
    assert not az_muster("VIII ZR 12/09").search("VIII ZR 13/09")
    assert az_muster("") is None


def test_fundstellen_um_das_aktenzeichen():
    stellen = fundstellen(TEXT, "VIII ZR 12/09")
    assert len(stellen) == 1 and "nicht mehr fest" in stellen[0]


def test_nur_stellen_mit_hinweiswort_sind_verdaechtig():
    assert verdaechtige_stellen(TEXT, "VIII ZR 12/09")
    assert verdaechtige_stellen(TEXT, "VIII ZR 99/09") == []


def test_aenderung_bestaetigt():
    from abweichung import aenderung_bestaetigt
    assert aenderung_bestaetigt({"aenderung": True})
    assert aenderung_bestaetigt({"aenderung": "ja"})
    assert not aenderung_bestaetigt({"aenderung": False})
    assert not aenderung_bestaetigt({})
