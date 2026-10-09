"""Tests für Gesetzestexte: Einlesen des XML von gesetze-im-internet.de und Nachschlagen.

Die Beispieldateien in tests/daten/ sind gekürzte echte Dateien (AGG, GG, BGB).
"""
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import config
import daten_laden
import gesetze_laden
import normen

DATEN = Path(__file__).parent / "daten"


@pytest.fixture
def gesetze_db(tmp_path, monkeypatch):
    """Eine leere Datenbank mit den drei Beispielgesetzen."""
    pfad = tmp_path / "test.db"
    monkeypatch.setattr(config, "SQLITE_PFAD", pfad)
    with closing(sqlite3.connect(pfad)) as db:
        daten_laden.tabellen_anlegen(db)
        for kurz in ("agg", "gg", "bgb"):
            gesetz = gesetze_laden.gesetz_lesen((DATEN / f"{kurz}_auszug.xml").read_bytes())
            gesetze_laden.gesetz_speichern(db, kurz, gesetz, "Wed, 06 May 2026 15:55:55 GMT")
    normen._namen.cache_clear()
    normen.geladene_gesetze.cache_clear()
    yield pfad
    normen._namen.cache_clear()
    normen.geladene_gesetze.cache_clear()


def test_gesetz_lesen():
    agg = gesetze_laden.gesetz_lesen((DATEN / "agg_auszug.xml").read_bytes())
    assert agg["gesetz"] == "AGG" and agg["titel"] == "Allgemeines Gleichbehandlungsgesetz"
    assert agg["stand"].startswith("Zuletzt geändert durch")
    paragraph_6 = next(n for n in agg["normen"] if n["nr"] == "6")
    assert paragraph_6["titel"] == "Persönlicher Anwendungsbereich"
    zeilen = paragraph_6["text"].split("\n")
    assert zeilen[0] == "(1) Beschäftigte im Sinne dieses Gesetzes sind"
    assert zeilen[1] == "1. Arbeitnehmerinnen und Arbeitnehmer,"           # Aufzählung auf eigener Zeile
    assert any(z.startswith("(2) Arbeitgeber") for z in zeilen)


def test_artikel_und_paragraph_normieren():
    gg = gesetze_laden.gesetz_lesen((DATEN / "gg_auszug.xml").read_bytes())
    assert [(n["art"], n["nr"]) for n in gg["normen"]] == [("Art.", "3")]
    assert gesetze_laden.paragraph_normieren("Art 3") == "Art. 3"
    assert gesetze_laden.paragraph_normieren("§  573a") == "§ 573a"


def test_normen_finden_mit_absatz():
    funde = normen.normen_finden("Nach § 6 Abs. 1 Satz 2 Alt. 1 AGG und Art. 3 Abs. 1 GG sowie § 31a SGB II.")
    assert [(f["art"], f["nr"], f["absatz"], f["gesetz"]) for f in funde] == [
        ("§", "6", "1", "AGG"), ("Art.", "3", "1", "GG"), ("§", "31a", None, "SGB II")]


def test_nachschlagen(gesetze_db):
    norm = normen.nachschlagen("§", "6", "AGG", absatz="1")
    assert norm["norm"] == "§ 6 Abs. 1 AGG" and norm["text"].startswith("(1) Beschäftigte")
    assert "(2)" not in norm["text"]                                        # nur der zitierte Absatz
    assert norm["url"] == "https://www.gesetze-im-internet.de/agg/__6.html"
    assert norm["stand"].startswith("Zuletzt geändert")
    assert normen.nachschlagen("Art.", "3", "GG", absatz="1")["text"] == "(1) Alle Menschen sind vor dem Gesetz gleich."
    assert normen.nachschlagen("§", "573a", "BGB")["titel"].startswith("Erleichterte Kündigung")
    assert normen.nachschlagen("§", "1", "XYZG") is None                    # unbekanntes Gesetz: kein Fehler


def test_norm_status(gesetze_db):
    assert normen.norm_status("§", "6", "AGG") == "gefunden"
    assert normen.norm_status("§", "999", "AGG") == "fehlt"
    assert normen.norm_status("§", "1", "TTDSG") == "nicht im Bestand"


def test_neue_gesetze_werden_verlinkt(gesetze_db):
    assert normen.verlinken("§ 15 Abs. 2 AGG") == "[§ 15 Abs. 2 AGG](https://www.gesetze-im-internet.de/agg/__15.html)"


def test_ohne_gesetzestabellen_kein_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PFAD", tmp_path / "fehlt.db")
    normen._namen.cache_clear()
    normen.geladene_gesetze.cache_clear()
    assert normen.nachschlagen("§", "6", "AGG") is None
    assert normen.norm_url("§", "573", "BGB").endswith("/bgb/__573.html")  # Ausweichliste
    assert not (tmp_path / "fehlt.db").exists()
    normen._namen.cache_clear()
    normen.geladene_gesetze.cache_clear()


def test_normtexte_fuers_material_mit_obergrenzen(gesetze_db, monkeypatch):
    import llm
    monkeypatch.setattr(config, "NORMEN_MAX", 2)
    monkeypatch.setattr(config, "NORMTEXT_ZEICHEN", 120)
    pruefungen = {
        1: {"relevant": True, "normen": ["§ 15 Abs. 2 AGG", "§ 6 Abs. 1 Satz 2 AGG", "§ 999 AGG"]},
        2: {"relevant": True, "normen": ["§ 15 Abs. 2 AGG", "Art. 3 Abs. 1 GG"]},
        3: {"relevant": False, "normen": ["§ 573 BGB"]},                  # aussortiert: zählt nicht
    }
    text = llm.normtexte(pruefungen)
    absaetze = text.split("\n\n")
    assert len(absaetze) == 2                                            # NORMEN_MAX
    assert absaetze[0].startswith("§ 15 Abs. 2 AGG – ")                  # am häufigsten genannt zuerst
    assert "(2) Wegen eines Schadens" in absaetze[0] and "(1)" not in absaetze[0]
    assert all(len(a.split("\n", 1)[1]) <= 120 + 4 for a in absaetze)  # NORMTEXT_ZEICHEN + " […]"
    assert "573" not in text and "999" not in text


def test_erfundene_norm_wird_erkannt(gesetze_db):
    from ergaenzung import normen_pruefen
    antwort = ("**2. Einschlägige Normen**\n- § 6 Abs. 1 AGG – Bewerberbegriff [1].\n- § 999 AGG – erfunden [1].\n"
               "- Art. 7 DSGVO – Einwilligung [2].\n> - § 998 AGG im Block per Code [1]")
    status = {n["fund"]: n["status"] for n in normen_pruefen(antwort)}
    assert status == {"§ 6 Abs. 1 AGG": "gefunden", "§ 999 AGG": "fehlt", "Art. 7 DSGVO": "nicht im Bestand"}
    wortlaut = next(n for n in normen_pruefen(antwort) if n["status"] == "gefunden")["wortlaut"]
    assert wortlaut["norm"] == "§ 6 Abs. 1 AGG" and wortlaut["text"].startswith("(1) Beschäftigte")


def test_kurzform_finden():
    vorhanden = {"sgb_2", "a_g", "ao_1977", "aufenthg_2004", "bdsg_1990", "bdsg_2018", "agg", "sgb2_48afkv"}
    assert gesetze_laden.kurzform_finden("SGB II", vorhanden) == "sgb_2"
    assert gesetze_laden.kurzform_finden("AÜG", vorhanden) == "a_g"
    assert gesetze_laden.kurzform_finden("ao-1977", vorhanden) == "ao_1977"
    assert gesetze_laden.kurzform_finden("AufenthG", vorhanden) == "aufenthg_2004"
    assert gesetze_laden.kurzform_finden("BDSG", vorhanden) == "bdsg_2018"              # neueste Fassung
    assert gesetze_laden.kurzform_finden("DSGVO", vorhanden) is None
    assert gesetze_laden.vergleichsform("AO 1977") == gesetze_laden.vergleichsform("AO")
    assert gesetze_laden.vergleichsform("SGB II") == gesetze_laden.vergleichsform("SGB 2")


def test_ohne_gesetzestexte(gesetze_db, monkeypatch):
    import llm
    monkeypatch.setattr(config, "NORMEN_MAX", 0)
    assert llm.normtexte({1: {"relevant": True, "normen": ["§ 15 Abs. 2 AGG"]}}) == ""


def test_zitatpruefung_bekommt_den_wortlaut(gesetze_db, monkeypatch):
    import llm
    gesendet = {}
    monkeypatch.setattr(llm, "json_chat", lambda system, nutzer, denken=False: gesendet.update(nutzer=nutzer) or {})
    t = {"nr": 1, "gericht": "BAG", "typ": "Urteil", "datum": "2016-08-11", "aktenzeichen": "8 AZR 4/15",
         "kontext": "38\n:   Text.", "kontext_fundstelle": "Gründe, Rn. 38"}
    llm.aussagen_pruefen(t, ["§ 15 Abs. 2 AGG – Anspruch auf Entschädigung"])
    assert "Gesetzestexte zu den in den Aussagen genannten Normen" in gesendet["nutzer"]
    assert "(2) Wegen eines Schadens" in gesendet["nutzer"]


def test_norm_in_mehreren_abschnitten(gesetze_db):
    from ergaenzung import normen_pruefen
    antwort = ("**1. Kurzantwort**\nNach § 15 Abs. 2 AGG nicht [1].\n"
               "**2. Einschlägige Normen**\n- § 15 Abs. 2 AGG – Entschädigung [1].")
    assert normen_pruefen(antwort)[0]["abschnitte"] == [1, 2]          # steht auch unter "Normen"
