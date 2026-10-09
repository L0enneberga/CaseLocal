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


# Rn. 38 aus BAG, Urt. v. 11.08.2016 - 8 AZR 4/15 (gekürzt, mit geschützten Leerzeichen wie im Datensatz)
RN_38 = ("37\n:   I. Der persönliche Anwendungsbereich des AGG ist eröffnet.\n\n"
         "38\n:   Soweit teilweise in der Rechtsprechung des Senats zusätzlich die „subjektive Ernsthaftigkeit "
         "der Bewerbung“ gefordert wurde *(ua. BAG 18.\xa0Juni 2015 -\xa08\xa0AZR 848/13\xa0(A)\xa0- Rn.\xa024)*, "
         "hält der Senat hieran nicht fest. Vgl. EuGH 28. Juli 2016 - C-423/15 - [Kratzer] und "
         "Richtlinie\xa02000/78/EG.")


def test_unionsrecht_erkennt_vorlagebeschluss_rechtssache_und_richtlinie():
    from normen import unionsrecht_bezuege
    bezuege = {(b["art"], b["fund"], b["rn"]) for b in unionsrecht_bezuege(RN_38)}
    assert ("Vorlagebeschluss", "8 AZR 848/13 (A)", 38) in bezuege
    assert ("EuGH-Rechtssache", "C-423/15", 38) in bezuege
    assert ("Richtlinie", "Richtlinie 2000/78/EG", 38) in bezuege
    assert unionsrecht_bezuege("37\n:   Ein rein nationaler Fall nach § 1 KSchG.") == []
