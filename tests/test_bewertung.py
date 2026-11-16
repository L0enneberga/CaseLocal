"""Tests für die Kennzahlen in bewertung.py (ohne Suche und ohne Sprachmodell)."""
import bewertung
import config


def test_suche_zusammenfassen(monkeypatch):
    monkeypatch.setattr(config, "KI_TREFFER", 6)
    ergebnisse = [{"rang": 1}, {"rang": 2}, {"rang": 6}, {"rang": 8}, {"rang": None}]
    assert bewertung.suche_zusammenfassen(ergebnisse) == {
        "fragen": 5, "top1": 1, "top5": 2, "ausgewertet": 3, "nicht_gefunden": 1,
        "mrr": round((1 + 1 / 2 + 1 / 6 + 1 / 8) / 5, 3)}


def test_suche_zusammenfassen_ohne_fragen():
    assert bewertung.suche_zusammenfassen([])["mrr"] is None
