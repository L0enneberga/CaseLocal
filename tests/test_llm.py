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


def test_pruefung_bereinigen_ohne_antwort_nennt_den_grund():
    # Lieferte das Modell nichts Verwertbares, soll das Urteil nicht stillschweigend verschwinden.
    p = pruefung_bereinigen({})
    assert p["relevant"] is False and "keine verwertbare Bewertung" in p["begruendung"]


def test_pruefung_bereinigen_jede_randnummer_nur_einmal():
    assert pruefung_bereinigen({"relevant": True, "randnummern": [18, 17, 18, "Rn. 18"]})["randnummern"] == [18, 17]


def test_json_retten_bei_abgeschnittener_einzelpruefung():
    # So sah eine echte Antwort aus: Das Modell wiederholte "18," bis zur Obergrenze.
    from llm import json_retten
    abgeschnitten = ('{"relevant": false, "begruendung": "Es geht um Container, nicht um Arbeitszimmer.", '
                     '"normen": ["§ 23 EStG"], "randnummern": [18, 18, 18, 18')
    assert json_retten(abgeschnitten) == {
        "relevant": False, "begruendung": "Es geht um Container, nicht um Arbeitszimmer.",
        "normen": ["§ 23 EStG"], "randnummern": [18, 18, 18]}


def test_json_retten_bei_abgeschnittener_zitatpruefung():
    from llm import json_retten
    abgeschnitten = ('{"pruefung": [{"aussage": 1, "urteil": "ja", "hinweis": "steht in Rn. 5, 6"}, '
                     '{"aussage": 2, "urteil": "nein", "hinweis": "Das Gericht sagt {etwas} and')
    # Der zweite Eintrag bleibt erhalten, soweit er vollständig war; der abgebrochene Hinweis fällt weg.
    assert json_retten(abgeschnitten) == {"pruefung": [
        {"aussage": 1, "urteil": "ja", "hinweis": "steht in Rn. 5, 6"}, {"aussage": 2, "urteil": "nein"}]}


def test_json_retten_ohne_verwertbaren_inhalt():
    from llm import json_retten
    assert json_retten("") == {} and json_retten("kein JSON") == {} and json_retten('{"relevant"') == {}


def test_json_chat_begrenzt_die_laenge_und_rettet_abgeschnittenes(monkeypatch):
    import ollama

    import config
    import llm
    aufrufe = []

    def chat(**argumente):
        aufrufe.append(argumente)
        return {"message": {"content": '{"relevant": true, "randnummern": [3, 3, 3'}}
    monkeypatch.setattr(ollama, "chat", chat)
    assert llm.json_chat("System", "Nutzer") == {"relevant": True, "randnummern": [3, 3]}
    assert aufrufe[0]["options"]["num_predict"] == config.JSON_MAX_TOKENS
    llm.json_chat("System", "Nutzer", denken=True)      # im Denkmodus zählen die Gedanken mit: keine Grenze
    assert "num_predict" not in aufrufe[1]["options"]


def test_datum_deutsch():
    from llm import datum_deutsch
    assert datum_deutsch("2016-08-11") == "11.08.2016"
    assert datum_deutsch("2016") == "2016"              # unbekanntes Format bleibt stehen
    assert datum_deutsch(None) == "" and datum_deutsch("") == ""


def test_vorladen_bleibt_still_wenn_ollama_fehlt(monkeypatch):
    import ollama

    import llm

    def nicht_erreichbar(**_):
        raise ConnectionError("Ollama läuft nicht")
    monkeypatch.setattr(ollama, "embed", nicht_erreichbar)
    assert llm.vorladen() is False
