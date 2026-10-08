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
