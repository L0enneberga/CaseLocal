"""Tests für das Erkennen der Urteilsgliederung."""
from gliederung import fundstelle, lesbar, randnummern, teil_text, teile_erkennen

URTEIL = """## Tenor

:   Die Berufung wird zurückgewiesen.

## Tatbestand

1
:   Die Parteien streiten über eine Kündigung.

## Entscheidungsgründe

2
:   Die Berufung ist unbegründet.

3
:   Die Kündigung ist sozial gerechtfertigt."""

# Zweites Format: Überschriften ohne #, Randnummer auf eigener Zeile mit Leerzeile danach
URTEIL_NRW = """Tenor

Die Klage wird abgewiesen.

**T a t b e s t a n d**

2

Der Kläger wendet sich gegen einen Bescheid.

Entscheidungsgründe:

5

Die Klage ist unbegründet."""


def test_teile_werden_erkannt():
    assert [t for t, _ in teile_erkennen(URTEIL)] == ["Tenor", "Tatbestand", "Gründe"]


def test_zweites_format_wird_erkannt():
    teile = teile_erkennen(URTEIL_NRW)
    assert [t for t, _ in teile] == ["Tenor", "Tatbestand", "Gründe"]
    assert randnummern(teile[2][1]) == [5]


def test_unbekannte_zwischenueberschrift_bleibt_im_teil():
    text = "## Gründe\n\n1\n:   Erster Punkt.\n\n### II. Zur Kündigung\n\n2\n:   Zweiter Punkt."
    assert [t for t, _ in teile_erkennen(text)] == ["Gründe"]


def test_text_vor_der_ersten_ueberschrift():
    assert teile_erkennen("Vorspann\n\n## Tenor\n\n:   Abgewiesen.")[0] == ("Sonstiges", "Vorspann")


def test_randnummern():
    assert randnummern(URTEIL) == [1, 2, 3]


def test_teil_text_kuerzt():
    assert teil_text(URTEIL, "Tenor") == ":   Die Berufung wird zurückgewiesen."
    assert teil_text("## Tenor\n\n" + "wort " * 500, "Tenor", 50).endswith(" […]")


def test_fundstelle():
    assert fundstelle("Gründe", 15, 17) == "Gründe, Rn. 15–17"
    assert fundstelle("Gründe", 15, 15) == "Gründe, Rn. 15"
    assert fundstelle("Tenor", 0, 0) == "Tenor"


def test_lesbar():
    assert lesbar("2\n:   Die Berufung.") == "Rn. 2: Die Berufung."
    assert lesbar("2\n:   Die Berufung.", markdown=True) == "**Rn. 2** Die Berufung."
    assert lesbar(":   Abgewiesen.") == "Abgewiesen."


def test_verwaiste_randnummer_vor_ueberschrift_wird_entfernt():
    text = "Tenor\n\nDie Klage wird abgewiesen.\n\n1\n\n**T a t b e s t a n d**\n\n2\n\nSachverhalt."
    assert teile_erkennen(text)[0] == ("Tenor", "Die Klage wird abgewiesen.")


def test_lesbar_entfernt_einrueckungen():
    assert lesbar("1. Abgewiesen.\n\n    Kosten trägt der Kläger.") == "1. Abgewiesen.\n\nKosten trägt der Kläger."


REVISION = """## Gründe

5
:   Die Revision hat Erfolg.

6
:   I. Das Berufungsgericht hat zur Begründung seiner Entscheidung ausgeführt:

7
:   Die Kündigung sei wirksam.

8
:   II. Diese Beurteilung hält rechtlicher Nachprüfung nicht stand.

9
:   Die Kündigung ist unwirksam."""


def test_wiedergabe_der_vorinstanz_wird_erkannt():
    from gliederung import vorinstanz_randnummern
    assert vorinstanz_randnummern(REVISION) == [6, 7]
    assert vorinstanz_randnummern(REVISION.replace("II. Diese Beurteilung hält rechtlicher Nachprüfung nicht stand.",
                                                   "Weiter so.")) == []          # ohne Ende: nichts markieren
    assert "Rn. 7 [Wiedergabe der Vorinstanz]: Die Kündigung sei wirksam." in lesbar(REVISION, vorinstanz={6, 7})


def test_bewertung_nach_der_vorinstanz():
    from gliederung import bewertung_nach_vorinstanz
    text, von, bis = bewertung_nach_vorinstanz(REVISION, [6, 7])
    assert (von, bis) == (8, 9)
    assert text.startswith("8\n:   II. Diese Beurteilung") and "Die Kündigung ist unwirksam." in text
    assert bewertung_nach_vorinstanz(REVISION, []) == ("", 0, 0)


def test_ab_randnummer():
    from gliederung import ab_randnummer
    assert ab_randnummer("Satzrest.\n\n5\n:   Neuer Absatz.") == "5\n:   Neuer Absatz."
    assert ab_randnummer("5\n:   Absatz.") == "5\n:   Absatz."
    assert ab_randnummer("Ohne Randnummer.") == "Ohne Randnummer."


def test_lesbar_entfernt_geschuetzte_leerzeichen_am_zeilenanfang():
    assert lesbar("Abgewiesen.\n\n\xa0\xa0\xa0\xa0Kosten trägt der Kläger.") == "Abgewiesen.\n\nKosten trägt der Kläger."
