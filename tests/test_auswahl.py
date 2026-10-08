"""Tests für die Auswahl der bedeutendsten Urteile (ohne Download)."""
from datetime import date

import pandas as pd

from auswahl import auswaehlen, bedeutung_berechnen, gerichtsbarkeit, instanz, rangwerte


def test_instanz():
    assert instanz("Bundesgericht", "Bundesgerichtshof") == "Oberstes Gericht"
    assert instanz(None, "Europäischer Gerichtshof") == "Oberstes Gericht"
    assert instanz(None, "Oberverwaltungsgericht Nordrhein-Westfalen") == "Obergericht"
    assert instanz(None, "Kammergericht") == "Obergericht"
    assert instanz(None, "Landesarbeitsgericht Köln") == "Obergericht"
    assert instanz("Landgericht", "Landgericht Bonn") == "Eingangsgericht"
    assert instanz(None, "Verwaltungsgericht Köln") == "Eingangsgericht"


def test_gerichtsbarkeit_aus_dem_namen_wenn_sie_fehlt():
    assert gerichtsbarkeit(None, "Bundesgerichtshof") == "Ordentliche Gerichtsbarkeit"
    assert gerichtsbarkeit(None, "Bundesfinanzhof") == "Finanzgerichtsbarkeit"
    assert gerichtsbarkeit(None, "Bundesverfassungsgericht") == "Verfassungsgerichtsbarkeit"
    assert gerichtsbarkeit(None, "Bayerischer Verwaltungsgerichtshof") == "Verwaltungsgerichtsbarkeit"
    assert gerichtsbarkeit("Arbeitsgerichtsbarkeit", "egal") == "Arbeitsgerichtsbarkeit"


def _meta():
    return pd.DataFrame({
        "slug": ["bgh-alt", "bgh-neu", "lg", "ag", "bfh"],
        "instanz": ["Oberstes Gericht", "Oberstes Gericht", "Eingangsgericht", "Eingangsgericht", "Oberstes Gericht"],
        "gerichtsbarkeit": ["Ordentliche Gerichtsbarkeit"] * 4 + ["Finanzgerichtsbarkeit"],
        "datum": ["2005-01-01", "2025-06-01", "2020-01-01", "2020-01-01", "2010-01-01"],
    })


def test_bedeutung_zitierungen_alter_und_instanz():
    kanten = pd.DataFrame({"von_slug": ["bgh-neu", "lg", "ag", "lg"],
                           "nach_slug": ["bgh-alt", "bgh-alt", "bgh-alt", "bgh-neu"]})
    m = bedeutung_berechnen(_meta(), kanten, date(2026, 5, 20)).set_index("slug")
    assert m.loc["bgh-alt", "zitiert_von"] == 3
    assert m.loc["bgh-alt", "gewichtet"] == 3.0 + 1.0 + 1.0      # Zitat vom BGH zählt dreifach
    assert m.loc["ag", "score"] == 0                              # nie zitiert
    # Eine Zitierung in einem Jahr wiegt mehr als dieselbe Zahl verteilt über 20 Jahre
    assert m.loc["bgh-neu", "score"] > m.loc["lg", "score"]


def test_auswahl_in_kontingenten():
    meta = pd.DataFrame({
        "slug": [f"u{i}" for i in range(8)],
        "instanz": ["Oberstes Gericht"] * 5 + ["Obergericht"] * 2 + ["Oberstes Gericht"],
        "gerichtsbarkeit": ["Ordentliche Gerichtsbarkeit"] * 7 + ["Finanzgerichtsbarkeit"],
        "datum": ["2010-01-01"] * 4 + ["2025-01-01"] + ["2015-01-01"] * 2 + ["2012-01-01"],
        "alter": [16, 16, 16, 16, 1, 11, 11, 14],
        "score": [9, 8, 7, 6, 0.5, 3, 2, 0.1],
        "zitiert_von": [90, 80, 70, 60, 1, 30, 20, 1],
    })
    auswahl = auswaehlen(meta, gesamt=5, neue_hoechst=1, neu_jahre=5, instanzgerichte=1,
                         mindestens_je_gebiet=1)
    gruende = dict(zip(auswahl.slug, auswahl.grund))
    # Die ordentliche Gerichtsbarkeit ist über u4 und u5 schon vertreten, die Finanzgerichtsbarkeit
    # bekommt über das Gebiets-Kontingent u7, der Rest geht nach Score.
    assert gruende == {"u4": "neu", "u5": "Instanzgericht", "u7": "Gebiet", "u0": "Bedeutung", "u1": "Bedeutung"}
    assert list(rangwerte(auswahl.sort_values("score")).round(1)) == [0.2, 0.4, 0.6, 0.8, 1.0]


def test_kuerzen_streicht_nur_im_kontingent_bedeutung():
    from auswahl import auf_gesamtzahl_kuerzen
    auswahl = pd.DataFrame({"slug": ["a", "b", "c", "d"], "score": [9.0, 5.0, 0.5, 0.1],
                            "grund": ["Bedeutung", "Bedeutung", "Instanzgericht", "neu"]})
    assert set(auf_gesamtzahl_kuerzen(auswahl, 3).slug) == {"a", "c", "d"}
