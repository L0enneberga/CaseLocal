"""Die Weboberfläche: Einstieg und Navigation.

Aufruf:  streamlit run app.py   (oder Doppelklick auf start.bat)
Danach öffnet sich der Browser mit http://localhost:8501

Hier entsteht auch die Kopfzeile, die auf beiden Seiten gleich ist: Logo, Status und der
Schalter für helles und dunkles Design. Die beiden Seiten liegen im Ordner seiten/:
  recherche.py  - Frage stellen, Antwort mit Fundstellen, Ablage in einer Akte
  akten.py      - "Meine Akten": gespeicherte Recherchen lesen, Notizen ändern, löschen

st.navigation legt fest, wie die Seiten in der Seitenleiste heißen. Ohne sie nähme Streamlit
den Dateinamen, und die Startseite hieße "app".
"""
from pathlib import Path

import streamlit as st

import config
import notizen
import suche

ORDNER = Path(__file__).parent

st.set_page_config(page_title="CaseLocal", page_icon="⚖️", layout="wide")
# Gestaltung für alle Seiten (siehe DESIGN.md). Steht hier, damit jede Seite sie bekommt.
st.html(f"<style>{(ORDNER / 'static' / 'caselocal.css').read_text(encoding='utf-8')}</style>")
# Kopfzeile mit Logo, Status und dem Schalter hell/dunkel (static/thema_schalter.html).
# Der Schalter braucht etwas JavaScript, deshalb unsafe_allow_javascript. Unbedenklich, weil alles
# aus diesem Projekt stammt (feste Datei, Werte aus config.py), keine Eingabe von außen.
schalter = (ORDNER / "static" / "thema_schalter.html").read_text(encoding="utf-8")
st.html(f'<header class="cl-top"><span class="cl-mark"><i></i>CaseLocal</span>'
        f'<span class="cl-status"><span class="cl-live" title="Läuft lokal, kein Text verlässt den Rechner">'
        f'Lokal</span><span class="cl-opt">{config.LLM_MODELL} · {suche.bestand_text()} · Bundesrecht</span>'
        f'</span>{schalter}</header>', unsafe_allow_javascript=True)

if config.NOTIZEN_AKTIV:
    notizen.tabellen_anlegen()                         # legt notizen.db beim ersten Start an

seiten = [
    st.Page("seiten/recherche.py", title="Recherche", icon=":material/search:", default=True),
    st.Page("seiten/akten.py", title="Meine Akten", icon=":material/folder_open:"),
]
st.navigation(seiten).run()
