"""Tests für die Ergänzungen der KI-Antwort per Code (ohne Sprachmodell)."""
from belege import abschnitte, daten_finden, metadaten_abweichungen
from ergaenzung import (aenderungen_block, antwort_ergaenzen, einfuegen, metadaten_einsetzen,
                        unionsrecht_block, urteilskopf)

BAG = {"nr": 1, "gericht": "Bundesarbeitsgericht", "typ": "Urteil", "datum": "2016-08-11",
       "aktenzeichen": "8 AZR 4/15", "kontext": "38\n:   Vgl. BAG 23. August 2012 - 8 AZR 285/11 - Rn. 18."}
BGH = {"nr": 2, "gericht": "Bundesgerichtshof", "typ": "Beschluss", "datum": "2016-12-14",
       "aktenzeichen": "VIII ZR 232/15"}


def test_daten_finden_in_allen_formaten():
    assert daten_finden("am 11.08.2016, am 23. August 2012 und am 2016-12-14") == [
        ("11.08.2016", "2016-08-11"), ("23. August 2012", "2012-08-23"), ("2016-12-14", "2016-12-14")]


def test_urteilskopf_aus_der_datenbank():
    assert urteilskopf(BAG) == "Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15"
    assert urteilskopf(BGH) == "Bundesgerichtshof, Beschl. v. 14.12.2016 – VIII ZR 232/15"


def test_abschnitte_erkennen_fette_ueberschriften_nicht_aber_listen():
    zeilen = ["**1. Kurzantwort**", "Text", "1. Listenpunkt", "### 3. Rechtsprechung", "- [1] – x"]
    assert abschnitte(zeilen) == [1, 1, 1, 3, 3]


def test_kopf_in_abschnitt_3_wird_eingesetzt():
    antwort = "**3. Rechtsprechung**\n- [1] – Das Gericht entschied, der Begriff ist formal (Rn. 38).\n- [2] – Ja [2]."
    neu, korrekturen = metadaten_einsetzen(antwort, [BAG, BGH])
    assert neu.split("\n")[1:] == [
        "- Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15 [1] – Das Gericht entschied, "
        "der Begriff ist formal (Rn. 38).",
        "- Bundesgerichtshof, Beschl. v. 14.12.2016 – VIII ZR 232/15 – Ja [2]."]
    assert korrekturen == []


def test_selbst_geschriebener_kopf_wird_ersetzt():
    antwort = "**3. Rechtsprechung**\n- Bundesarbeitsgericht, 20.08.2016, Az. 8 AZR 4/15 – Formaler Begriff [1]."
    neu, _ = metadaten_einsetzen(antwort, [BAG])
    assert neu.endswith("- Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15 – Formaler Begriff [1].")


def test_falsches_datum_wird_korrigiert_und_vermerkt():
    antwort = "**1. Kurzantwort**\nDas BAG entschied am 20.08.2016, der Begriff sei formal [1]."
    assert metadaten_abweichungen(antwort, [BAG])[0]["gefunden"] == "20.08.2016"
    neu, korrekturen = metadaten_einsetzen(antwort, [BAG])
    assert "am 11.08.2016" in neu and "20.08.2016" not in neu
    assert len(korrekturen) == 1 and "20.08.2016" in korrekturen[0]["hinweis"]


def test_im_urteil_zitierte_entscheidungen_sind_keine_abweichung():
    antwort = "Das BAG verweist auf sein Urteil vom 23. August 2012 (8 AZR 285/11) [1]."
    assert metadaten_abweichungen(antwort, [BAG]) == []


def test_falsches_aktenzeichen_bei_mehreren_quellen_nur_gemeldet():
    antwort = "So entschieden in 8 AZR 99/15 [1, 2]."
    abweichung = metadaten_abweichungen(antwort, [BAG, BGH])
    assert abweichung[0]["art"] == "Aktenzeichen" and abweichung[0]["richtig"] is None
    assert metadaten_einsetzen(antwort, [BAG, BGH])[0] == antwort



def test_aktenzeichen_mit_vor_und_nachsilbe_und_hinweise_sind_keine_abweichung():
    bsg = {"nr": 3, "gericht": "Bundessozialgericht", "typ": "Urteil", "datum": "2010-11-09",
           "aktenzeichen": "B 4 AS 27/10 R",
           "abweichungen": [{"datum": "2015-04-29", "aktenzeichen": "B 14 AS 19/14 R"}]}
    antwort = ("Das BSG (B 4 AS 27/10 R) wird von der Entscheidung vom 2015-04-29, "
               "B 14 AS 19/14 R, zitiert [3].")
    assert metadaten_abweichungen(antwort, [bsg]) == []

# --- Aufgabe 4: Rechtsprechungsänderungen per Code ----------------------------

AENDERND = {"id": 10, "nr": 1, "gericht": "Bundesarbeitsgericht", "typ": "Urteil", "datum": "2016-08-11",
            "aktenzeichen": "8 AZR 4/15", "slug": "bag-8-azr-4-15"}
FRUEHER = {"id": 20, "nr": 2, "gericht": "Bundesarbeitsgericht", "typ": "Urteil", "datum": "2012-08-23",
           "aktenzeichen": "8 AZR 285/11", "slug": "bag-8-azr-285-11"}


def zwei_treffer(monkeypatch):
    """Treffer 1 zitiert Treffer 2 an einer Stelle, an der er eine Rechtsprechungsänderung beschreibt."""
    import abweichung
    hinweis = {k: AENDERND[k] for k in ("id", "gericht", "typ", "datum", "aktenzeichen", "slug")}
    hinweis.update(instanz="Oberstes Gericht", erklaerung="Die subjektive Ernsthaftigkeit wird nicht mehr verlangt.",
                   stelle="... hält der Senat hieran nicht fest (8 AZR 285/11) ...")
    monkeypatch.setattr(abweichung, "pruefen", lambda t: [dict(hinweis)] if t["nr"] == 2 else [])
    treffer = [dict(AENDERND), dict(FRUEHER)]
    assert abweichung.alle_pruefen(treffer) == 1
    return treffer


def test_aendernde_und_betroffene_entscheidung_getrennt(monkeypatch):
    import abweichung
    treffer = zwei_treffer(monkeypatch)
    assert treffer[1]["abweichungen"][0]["nr"] == 1          # die ändernde Entscheidung ist Treffer [1]
    gruppen = abweichung.entwicklung(treffer)
    assert len(gruppen) == 1 and gruppen[0]["aendernd"]["nr"] == 1
    assert [b["treffer"]["nr"] for b in gruppen[0]["betroffen"]] == [2]
    block = aenderungen_block(gruppen)
    assert "**Ändernde Entscheidung:** [1] Bundesarbeitsgericht, Urt. v. 11.08.2016 – 8 AZR 4/15" in block
    assert "**Dort zitiert:** [2] Bundesarbeitsgericht, Urt. v. 23.08.2012 – 8 AZR 285/11" in block
    assert all(zeile.startswith(">") for zeile in block.split("\n"))
    assert "überholt" not in block                            # keine Behauptung, welche Linie gilt


def test_ohne_treffernummer_mit_link(monkeypatch):
    import abweichung
    treffer = zwei_treffer(monkeypatch)[1:]                   # ändernde Entscheidung kein Treffer
    treffer[0]["abweichungen"][0]["nr"] = None
    assert "([Volltext](https://de.openlegaldata.io/case/bag-8-azr-4-15))" in aenderungen_block(
        abweichung.entwicklung(treffer))


def test_block_kommt_ans_ende_von_abschnitt_4():
    antwort = "**4. Abweichende Entscheidungen**\nKeine gefunden.\n\n**5. Offen**\nNichts."
    assert einfuegen(antwort, 4, "> Block") == (
        "**4. Abweichende Entscheidungen**\nKeine gefunden.\n\n> Block\n\n**5. Offen**\nNichts.\n")
    assert einfuegen("Ohne Abschnitte.", 4, "> Block") == "Ohne Abschnitte.\n\n> Block\n"


def test_antwort_ergaenzen_mit_aenderung(monkeypatch):
    treffer = zwei_treffer(monkeypatch)
    antwort = "**3. Rechtsprechung**\n- [1] – Formaler Begriff.\n**4. Abweichende**\nKeine.\n**5. Offen**\nx"
    ergebnis = antwort_ergaenzen(antwort, treffer)
    assert "> - **Ändernde Entscheidung:** [1]" in ergebnis["antwort"]
    assert ergebnis["antwort"].index("Ändernde") < ergebnis["antwort"].index("**5. Offen**")
    from belege import aussagen_finden
    assert all("Ändernde" not in a["satz"] for a in aussagen_finden(ergebnis["antwort"]))


# --- Aufgabe 5: Unionsrecht ---------------------------------------------------

def test_unionsrecht_block_nur_aus_zitierten_randnummern(monkeypatch):
    import suche
    from test_normen import RN_38
    monkeypatch.setattr(suche, "urteil_nach_aktenzeichen", lambda az: None)   # ohne Datenbank
    t = {**BAG, "kontext": RN_38}
    block = unionsrecht_block([t], {1: {"relevant": True, "randnummern": [38]}})
    assert "> - [1] 8 AZR 4/15: Vorlagebeschluss 8 AZR 848/13 (A) (Rn. 38)" in block
    assert "[C-423/15](https://curia.europa.eu/juris/liste.jsf?num=C-423/15)" in block
    assert "Verweis auf Rechtsprechung des EuGH" not in block                # genauerer Verweis vorhanden
    assert "nicht im Bestand" in block
    assert unionsrecht_block([t], {1: {"relevant": True, "randnummern": [37]}}) == ""
