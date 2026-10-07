"""Tests für das Verlinken von Normzitaten."""
from normen import verlinken

BASIS = "https://www.gesetze-im-internet.de"


def test_paragraph():
    assert verlinken("nach § 573 BGB") == f"nach [§ 573 BGB]({BASIS}/bgb/__573.html)"


def test_paragraph_mit_absatz_satz_und_buchstabe():
    assert verlinken("§ 573a Abs. 2 S. 1 BGB") == f"[§ 573a Abs. 2 S. 1 BGB]({BASIS}/bgb/__573a.html)"


def test_artikel_grundgesetz():
    assert verlinken("Art. 3 Abs. 1 GG") == f"[Art. 3 Abs. 1 GG]({BASIS}/gg/art_3.html)"


def test_unbekanntes_gesetz_bleibt_unveraendert():
    assert verlinken("§ 1 FantasieG") == "§ 1 FantasieG"


def test_text_ohne_normen():
    assert verlinken("Die Klage wird abgewiesen.") == "Die Klage wird abgewiesen."
