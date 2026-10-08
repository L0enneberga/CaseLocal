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


def test_abschnitte_bilden_merkt_sich_teil_und_randnummern():
    from index_bauen import abschnitte_bilden
    text = "## Tenor\n\n:   Abgewiesen.\n\n## Gründe\n\n4\n:   Erstens.\n\n5\n:   Zweitens."
    assert abschnitte_bilden(text) == [
        {"text": ":   Abgewiesen.", "teil": "Tenor", "rn_von": 0, "rn_bis": 0},
        {"text": "4\n:   Erstens.\n\n5\n:   Zweitens.", "teil": "Gründe", "rn_von": 4, "rn_bis": 5},
    ]


def test_abschnitte_bilden_kuerzt_zuerst_den_tatbestand():
    from index_bauen import abschnitte_bilden
    lang = "\n\n".join("t" * 1400 for _ in range(60))
    text = f"## Tatbestand\n\n{lang}\n\n## Gründe\n\n1\n:   Die Begründung."
    abschnitte = abschnitte_bilden(text)
    assert len(abschnitte) == config.MAX_CHUNKS_PRO_URTEIL
    assert abschnitte[-1]["teil"] == "Gründe"
