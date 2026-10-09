"""Tests für die Zitatprüfung (ohne Sprachmodell)."""
from belege import aussagen_finden, gesamturteil, markieren, quellen, saetze_teilen, zusammenfassung


def test_quellen():
    assert quellen("Das gilt [1, 3] und auch [2].") == [1, 3, 2]
    assert quellen("Ohne Beleg.") == []


def test_saetze_teilen_beachtet_abkuerzungen_und_daten():
    text = "Nach § 1 Abs. 2 KSchG gilt das z. B. ab dem 1. Juli [1]. Das Gericht entschied anders [2]."
    assert saetze_teilen(text) == ["Nach § 1 Abs. 2 KSchG gilt das z. B. ab dem 1. Juli [1].",
                                   "Das Gericht entschied anders [2]."]


def test_zitat_nach_dem_punkt_gehoert_zum_satz():
    assert saetze_teilen("Die Kündigung war unwirksam. [3] Weiter so.") == [
        "Die Kündigung war unwirksam. [3]", "Weiter so."]


def test_aussagen_finden_ignoriert_ueberschriften_und_saetze_ohne_beleg():
    antwort = "**1. Kurzantwort**\nEs kommt darauf an [1]. Ohne Beleg.\n\n- Stichpunkt mit Beleg [2]."
    assert aussagen_finden(antwort) == [
        {"satz": "Es kommt darauf an [1].", "quellen": [1], "hinweis": False},
        {"satz": "Stichpunkt mit Beleg [2].", "quellen": [2], "hinweis": False},
    ]


def test_gesamturteil_alle_quellen_muessen_tragen():
    assert gesamturteil(["ja", "ja"]) == "ja"
    assert gesamturteil(["nein", "nein"]) == "nein"
    assert gesamturteil(["ja", "nein"]) == "teilweise"
    assert gesamturteil(["nein", "teilweise"]) == "teilweise"
    assert gesamturteil([]) == "unklar"


def test_pruefen_nennt_die_quelle_die_nicht_traegt(monkeypatch):
    import llm
    from belege import pruefen
    bewertung = {1: "ja", 3: "nein"}
    monkeypatch.setattr(llm, "aussagen_pruefen", lambda t, aussagen: [
        {"urteil": bewertung[t["nr"]], "hinweis": "anderes Thema" if t["nr"] == 3 else ""} for _ in aussagen])
    aussagen = pruefen("Der Begriff ist formal [1, 3].", [{"nr": 1}, {"nr": 3}])
    assert aussagen[0]["urteil"] == "teilweise"
    assert aussagen[0]["hinweise"] == ["[3] stützt diese Aussage nicht: anderes Thema"]


def test_hinweis_saetze_werden_nicht_geprueft(monkeypatch):
    import llm
    from belege import pruefen
    monkeypatch.setattr(llm, "aussagen_pruefen", lambda t, aussagen: [
        {"urteil": "ja", "hinweis": ""} for _ in aussagen])
    antwort = ("**4. Abweichende Entscheidungen**\n"
               "Ob das Urteil [3] von dieser Änderung betroffen ist, muss am Volltext geprüft werden.\n"
               "> Per Code ergänzt [1].\n"
               "**5. Was die gefundenen Urteile nicht beantworten**\n"
               "Wo die Schwelle zum Rechtsmissbrauch liegt, bleibt offen [1].")
    aussagen = pruefen(antwort, [{"nr": 1}, {"nr": 3}])
    assert [a["urteil"] for a in aussagen] == ["hinweis", "hinweis"]
    assert zusammenfassung(aussagen)["hinweis"] == 2 and zusammenfassung(aussagen)["ja"] == 0


def test_markieren():
    antwort = "Satz eins [1]. Satz zwei [2].\n- Satz drei [1]."
    aussagen = aussagen_finden(antwort)
    for aussage, urteil in zip(aussagen, ["ja", "nein", "teilweise"]):
        aussage["urteil"] = urteil
    assert markieren(antwort, aussagen) == (
        "Satz eins [1]. :green[:material/check:] "
        ":red-background[Satz zwei \\[2\\].] :red[:material/close:]\n"
        "- :orange-background[Satz drei \\[1\\].] :orange[:material/help:]")
    assert zusammenfassung(aussagen) == {"ja": 1, "teilweise": 1, "nein": 1, "unklar": 0, "hinweis": 0}


def test_randnummern_in_eckigen_klammern():
    from belege import rn_klammern
    antwort = rn_klammern("Das Gericht entschied so [Rn. 14, 15] [3].")
    assert antwort == "Das Gericht entschied so (Rn. 14, 15) [3]."
    assert aussagen_finden(antwort) == [{"satz": antwort, "quellen": [3], "hinweis": False}]
