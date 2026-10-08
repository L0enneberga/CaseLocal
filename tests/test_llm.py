"""Tests für das Aufbereiten der LLM-Antworten (ohne Sprachmodell)."""
from llm import pruefung_bereinigen
from suche import zusammenfuegen


def test_pruefung_bereinigen_mit_ungenauer_antwort():
    p = pruefung_bereinigen({"relevant": "ja", "entscheidung": " Unwirksam. ",
                             "randnummern": ["Rn. 15", 17, "x"], "normen": ["§ 1 KSchG", ""]})
    assert p == {"relevant": True, "begruendung": "", "entscheidung": "Unwirksam.",
                 "rechtssatz": "", "normen": ["§ 1 KSchG"], "randnummern": [15, 17]}


def test_pruefung_bereinigen_leere_antwort():
    assert pruefung_bereinigen({})["relevant"] is False


def test_zusammenfuegen_entfernt_ueberlappung():
    erster = "A" * 100 + " Das ist der Teil, der sich wiederholt."
    zweiter = "Das ist der Teil, der sich wiederholt. Und weiter."
    assert zusammenfuegen(erster, zweiter) == "A" * 100 + " Das ist der Teil, der sich wiederholt. Und weiter."
