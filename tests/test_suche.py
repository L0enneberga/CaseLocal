"""Tests für suche.py. Aufruf:  pytest"""
from suche import Filter, fts_anfrage


def test_fts_anfrage_verbindet_begriffe_mit_or():
    assert fts_anfrage(["Eigenbedarf", "Kündigung"]) == '"Eigenbedarf"* OR "Kündigung"*'


def test_fts_anfrage_entfernt_stoppwoerter_und_kurze_woerter():
    assert fts_anfrage(["die", "wann", "zu", "Mietrecht"]) == '"Mietrecht"*'


def test_fts_anfrage_entfernt_sonderzeichen():
    # Anführungszeichen würden die FTS5-Anfrage sonst kaputt machen
    assert fts_anfrage(['"Kündigung"', "§ 573 BGB"]) == '"Kündigung"* OR "573 BGB"'


def test_fts_anfrage_mehrere_woerter_muessen_alle_vorkommen():
    assert fts_anfrage(["häufige Krankheit"]) == '("häufige"* AND "Krankheit"*)'
    assert fts_anfrage(["§ 1 KSchG Kündigung"]) == '("1 KSchG" AND "Kündigung"*)'


def test_fts_anfrage_leer():
    assert fts_anfrage(["und", "?"]) == ""


def test_leerer_filter_ergibt_keine_bedingung():
    assert Filter().sql() == ("", [])


def test_filter_mit_allen_feldern():
    bedingung, werte = Filter(["Arbeitsgerichtsbarkeit", "Sozialgerichtsbarkeit"], 2015, 2020).sql()
    assert bedingung == "gerichtsbarkeit IN (?, ?) AND datum >= ? AND datum <= ?"
    assert werte == ["Arbeitsgerichtsbarkeit", "Sozialgerichtsbarkeit", "2015-01-01", "2020-12-31"]


def test_rang_faktor_bedeutung_und_aktualitaet():
    from datetime import date

    import config
    from suche import aktualitaet, rang_faktor
    heute = date(2026, 1, 1)
    assert aktualitaet("2026-01-01", heute) == 1.0
    assert round(aktualitaet(f"{2026 - config.AKTUALITAET_HALBWERT}-01-01", heute), 2) == 0.5
    assert aktualitaet("", heute) == 0.0
    assert rang_faktor(0.0, "1990-01-01", heute) < rang_faktor(1.0, "1990-01-01", heute)
    assert rang_faktor(1.0, "2026-01-01", heute) == 1 + config.RANG_BEDEUTUNG + config.RANG_AKTUALITAET
