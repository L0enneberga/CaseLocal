"""Tests für suche.py. Aufruf:  pytest"""
from suche import Filter, fts_anfrage


def test_fts_anfrage_verbindet_begriffe_mit_or():
    assert fts_anfrage(["Eigenbedarf", "Kündigung"]) == '"Eigenbedarf"* OR "Kündigung"*'


def test_fts_anfrage_entfernt_stoppwoerter_und_kurze_woerter():
    assert fts_anfrage(["die", "wann", "zu", "Mietrecht"]) == '"Mietrecht"*'


def test_fts_anfrage_entfernt_sonderzeichen():
    # Anführungszeichen würden die FTS5-Anfrage sonst kaputt machen
    assert fts_anfrage(['"Kündigung"', "§ 573 BGB"]) == '"Kündigung"* OR "573 BGB"'


def test_fts_anfrage_mehrere_woerter_muessen_alle_vorkommen():
    assert fts_anfrage(["häufige Krankheit"]) == '("häufige"* AND "Krankheit"*)'
    assert fts_anfrage(["§ 1 KSchG Kündigung"]) == '("1 KSchG" AND "Kündigung"*)'


def test_fts_anfrage_leer():
    assert fts_anfrage(["und", "?"]) == ""


def test_leerer_filter_ergibt_keine_bedingung():
    assert Filter().sql() == ("", [])


def test_filter_mit_allen_feldern():
    bedingung, werte = Filter(["Arbeitsgerichtsbarkeit", "Sozialgerichtsbarkeit"], 2015, 2020).sql()
    assert bedingung == "gerichtsbarkeit IN (?, ?) AND datum >= ? AND datum <= ?"
    assert werte == ["Arbeitsgerichtsbarkeit", "Sozialgerichtsbarkeit", "2015-01-01", "2020-12-31"]


def test_rang_faktor_bedeutung_und_aktualitaet():
    from datetime import date

    import config
    from suche import aktualitaet, rang_faktor
    heute = date(2026, 1, 1)
    assert aktualitaet("2026-01-01", heute) == 1.0
    assert round(aktualitaet(f"{2026 - config.AKTUALITAET_HALBWERT}-01-01", heute), 2) == 0.5
    assert aktualitaet("", heute) == 0.0
    assert rang_faktor(0.0, "1990-01-01", heute) < rang_faktor(1.0, "1990-01-01", heute)
    assert rang_faktor(1.0, "2026-01-01", heute) == 1 + config.RANG_BEDEUTUNG + config.RANG_AKTUALITAET


# --- Begriffe für die Schlagwortsuche -------------------------------------------

def test_suchbegriffe_ergaenzt_die_woerter_der_frage():
    from suche import suchbegriffe
    begriffe = suchbegriffe("Verfällt der Urlaub nach § 7 Abs. 3 BUrlG?", ["Urlaubsverfall", "Urlaub"])
    # KI-Begriffe zuerst, das Normzitat bleibt ganz, "Urlaub" kommt nicht doppelt vor
    assert begriffe == ["Urlaubsverfall", "Urlaub", "§ 7 Abs. 3 BUrlG", "Verfällt", "der", "nach"]


def test_suchbegriffe_ohne_ki_begriffe_nimmt_die_frage():
    from suche import suchbegriffe
    assert suchbegriffe("Eigenbedarf Tochter", []) == ["Eigenbedarf", "Tochter"]


def test_suchbegriffe_lassen_sich_abschalten(monkeypatch):
    import config
    from suche import suchbegriffe
    monkeypatch.setattr(config, "FRAGEWOERTER_MITSUCHEN", False)
    assert suchbegriffe("Verfällt der Urlaub?", ["Urlaubsverfall"]) == ["Urlaubsverfall"]
    assert suchbegriffe("Verfällt der Urlaub?", []) == ["Verfällt", "der", "Urlaub"]   # Notfall bleibt


# --- Bedeutungssuche mit Filter ---------------------------------------------------
# Die Tests ersetzen ChromaDB durch eine kleine Attrappe: Sie kennt nur die Reihenfolge der
# Abschnitte (bester zuerst) und zu welchem Urteil jeder gehört. Ollama wird nicht gebraucht,
# weil die Tests den Vektor der Frage selbst mitgeben.

class Attrappe:
    """Steht für die ChromaDB-Sammlung. urteil_ids: das Urteil jedes Abschnitts, bester zuerst."""

    def __init__(self, urteil_ids):
        self.urteil_ids = urteil_ids
        self.aufrufe = []                              # merkt sich, wie gesucht wurde

    def count(self):
        return len(self.urteil_ids)

    def query(self, query_embeddings, n_results, where=None):
        self.aufrufe.append({"n_results": n_results, "where": where})
        abschnitte = list(enumerate(self.urteil_ids))
        if where:
            erlaubt = set(where["urteil_id"]["$in"])
            abschnitte = [(i, u) for i, u in abschnitte if u in erlaubt]
        abschnitte = abschnitte[:n_results]
        return {"ids": [[f"{u}-{i}" for i, u in abschnitte]],
                "documents": [[f"Abschnitt {i}" for i, _ in abschnitte]],
                "metadatas": [[{"urteil_id": u, "teil": "Gründe"} for _, u in abschnitte]],
                "distances": [[i / 10_000 for i, _ in abschnitte]]}


def suche_mit(monkeypatch, urteil_ids, erlaubt, anzahl):
    """Führt semantische_suche mit der Attrappe aus. Ergebnis: (gefundene Urteile, Attrappe)."""
    import suche
    sammlung = Attrappe(urteil_ids)
    monkeypatch.setattr(suche, "_sammlung", lambda: sammlung)
    monkeypatch.setattr(suche, "_gefilterte_ids", lambda filter: erlaubt)
    treffer = suche.semantische_suche("Frage", anzahl, Filter(von_jahr=2020), vektor=[0.1, 0.2])
    return [t["urteil_id"] for t in treffer], sammlung


def test_bedeutungssuche_sucht_weiter_bis_genug_urteile_da_sind(monkeypatch):
    # Die ersten 12 Abschnitte stammen alle aus Urteil 1: 3 x 4 Abschnitte reichen nicht.
    urteil_ids = [1] * 12 + [2, 3, 4]
    gefunden, sammlung = suche_mit(monkeypatch, urteil_ids, None, anzahl=3)
    assert gefunden == [1, 2, 3]
    assert len(sammlung.aufrufe) == 2 and sammlung.aufrufe[0]["n_results"] == 12


def test_bedeutungssuche_haelt_den_filter_ein(monkeypatch):
    gefunden, _ = suche_mit(monkeypatch, [1, 2, 3, 4, 5, 6], {2, 4, 6}, anzahl=2)
    assert gefunden == [2, 4]


def test_bedeutungssuche_findet_auch_bei_engem_filter_genug(monkeypatch):
    # Früher: Filter erst NACH der Suche. Lagen die erlaubten Urteile weit hinten, blieb die
    # Liste (fast) leer. Jetzt sucht ChromaDB im zweiten Schritt nur in den erlaubten Urteilen.
    import config
    monkeypatch.setattr(config, "SUCHTIEFE_MAX", 16)
    urteil_ids = list(range(100, 200)) + [7, 8, 9]     # 7, 8, 9 liegen hinter 100 anderen Abschnitten
    gefunden, sammlung = suche_mit(monkeypatch, urteil_ids, {7, 8, 9}, anzahl=2)
    assert gefunden == [7, 8]
    assert sammlung.aufrufe[-1]["where"] == {"urteil_id": {"$in": [7, 8, 9]}}


def test_bedeutungssuche_ohne_erlaubte_urteile_ist_leer(monkeypatch):
    gefunden, sammlung = suche_mit(monkeypatch, [1, 2, 3], set(), anzahl=2)
    assert gefunden == [] and sammlung.aufrufe == []


# --- Ist die App eingerichtet? -----------------------------------------------------

def test_einrichtung_fehlt_ohne_datenbank(tmp_path, monkeypatch):
    import config
    import suche
    monkeypatch.setattr(config, "SQLITE_PFAD", tmp_path / "urteile.db")
    assert "keine Urteile geladen" in suche.einrichtung_fehlt()
    assert not (tmp_path / "urteile.db").exists()       # die Prüfung legt keine leere Datei an


def test_einrichtung_fehlt_ohne_urteile_und_ohne_index(tmp_path, monkeypatch):
    import sqlite3
    from contextlib import closing

    import config
    import daten_laden
    import suche
    monkeypatch.setattr(config, "SQLITE_PFAD", tmp_path / "urteile.db")
    monkeypatch.setattr(config, "CHROMA_PFAD", tmp_path / "chroma")
    with closing(sqlite3.connect(config.SQLITE_PFAD)) as db:
        daten_laden.tabellen_anlegen(db)
        db.commit()
        assert "enthält noch keine Urteile" in suche.einrichtung_fehlt()
        db.execute("INSERT INTO urteile (id, aktenzeichen, text) VALUES (1, 'VIII ZR 185/14', 'Text')")
        db.commit()
    assert "Suchindex" in suche.einrichtung_fehlt()
    assert not (tmp_path / "chroma").exists()
