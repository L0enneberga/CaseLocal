"""Tests für das Zerlegen der Urteile in Abschnitte."""
import config
from index_bauen import in_abschnitte_teilen


def test_kurzer_text_bleibt_ein_abschnitt():
    assert in_abschnitte_teilen("Tenor.\n\nGründe.") == ["Tenor.\n\nGründe."]


def test_abschnitte_sind_nicht_zu_lang():
    text = "\n\n".join(f"Absatz {i}: " + "x" * 400 for i in range(30))
    for abschnitt in in_abschnitte_teilen(text):
        assert len(abschnitt) <= config.CHUNK_ZEICHEN * 1.5


def test_riesen_absatz_wird_hart_geschnitten():
    abschnitte = in_abschnitte_teilen("y" * 10_000)
    assert len(abschnitte) > 1
    assert "".join(abschnitte).count("y") >= 10_000      # nichts geht verloren (Überlappung zählt doppelt)


def test_aufeinanderfolgende_abschnitte_ueberlappen():
    text = "\n\n".join(f"Absatz {i} " + "z" * 500 for i in range(10))
    erster, zweiter = in_abschnitte_teilen(text)[:2]
    assert zweiter.startswith(erster[-config.CHUNK_UEBERLAPPUNG:])


def test_maximale_anzahl_abschnitte():
    text = "\n\n".join("w" * 1000 for _ in range(500))
    assert len(in_abschnitte_teilen(text)) == config.MAX_CHUNKS_PRO_URTEIL
