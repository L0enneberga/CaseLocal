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
import threading
from pathlib import Path

import streamlit as st

import config
import llm
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
fehlt = suche.einrichtung_fehlt()                      # None, wenn Urteile und Suchindex da sind
bestand = "noch nicht eingerichtet" if fehlt else f"{suche.bestand_text()} · Bundesrecht"
st.html(f'<header class="cl-top"><span class="cl-mark"><i></i>CaseLocal</span>'
        f'<span class="cl-status"><span class="cl-live" title="Läuft lokal, kein Text verlässt den Rechner">'
        f'Lokal</span><span class="cl-opt">{config.LLM_MODELL} · {bestand}</span>'
        f'</span>{schalter}</header>', unsafe_allow_javascript=True)

if fehlt:
    # Die Daten lädt jede Installation selbst. Ohne sie gibt es nichts zu durchsuchen:
    # erklären, was zu tun ist, und hier aufhören (st.stop), statt mit einem Fehler abzubrechen.
    st.warning(f"**{fehlt}** Urteile, Gesetzestexte und Suchindex sind nicht Teil des Repositorys, "
               "jede Installation lädt sie selbst.", icon=":material/database:")
    st.markdown("Unter Windows genügt ein Doppelklick auf **`setup.bat`**. Von Hand, in dieser Reihenfolge:")
    st.code("python daten_laden.py      # Urteile auswählen und laden (ca. 3 GB)\n"
            "python index_bauen.py      # Suchindex bauen (2 bis 3 Stunden, lässt sich unterbrechen)\n"
            "python gesetze_laden.py    # die meistzitierten Bundesgesetze laden", language="bash")
    st.caption("Voraussetzungen und Einzelheiten stehen in der README. Danach diese Seite neu laden.")
    st.stop()


@st.cache_resource(show_spinner=False)                 # nur einmal je Start der App, nicht bei jedem Klick
def modelle_vorladen() -> None:
    """Lädt die Modelle im Hintergrund, während man die erste Frage tippt (siehe llm.vorladen)."""
    threading.Thread(target=llm.vorladen, daemon=True).start()


modelle_vorladen()
if config.NOTIZEN_AKTIV:
    notizen.tabellen_anlegen()                         # legt notizen.db beim ersten Start an

seiten = [
    st.Page("seiten/recherche.py", title="Recherche", icon=":material/search:", default=True),
    st.Page("seiten/akten.py", title="Meine Akten", icon=":material/folder_open:"),
]
st.navigation(seiten).run()
