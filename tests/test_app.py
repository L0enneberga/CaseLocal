"""Startet die Oberfläche testweise, ohne Browser (Streamlits AppTest). Aufruf:  pytest

Geprüft wird der Fall, den jede frische Installation zuerst sieht: Es sind noch keine
Daten geladen. Dafür braucht der Test weder Urteile noch Ollama.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import config

APP = str(Path(__file__).parent.parent / "app.py")


def test_app_ohne_daten_zeigt_einen_hinweis_statt_eines_fehlers(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PFAD", tmp_path / "urteile.db")
    monkeypatch.setattr(config, "CHROMA_PFAD", tmp_path / "chroma")
    monkeypatch.setattr(config, "NOTIZEN_DB", tmp_path / "notizen.db")
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert "noch keine Urteile geladen" in app.warning[0].value
    assert "setup.bat" in app.markdown[0].value
    assert not (tmp_path / "urteile.db").exists()       # nichts angelegt, nur geprüft
