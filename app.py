"""Die Weboberfläche.

Aufruf:  streamlit run app.py
Danach öffnet sich der Browser mit http://localhost:8501
"""
import ollama
import streamlit as st

import config
import llm
import normen
import suche

OLLAMA_FEHLER = "Ollama ist nicht erreichbar. Bitte die Ollama-App starten und neu suchen."

st.set_page_config(page_title="LexLokal", page_icon="⚖️", layout="wide")
st.title("LexLokal")
st.caption(f"{suche.anzahl_urteile():,} Urteile · Modell: {config.LLM_MODELL} · "
           "Lokale KI-Recherche in deutscher Rechtsprechung".replace(",", "."))

# --- Seitenleiste mit Einstellungen ---------------------------------------
with st.sidebar:
    st.header("Einstellungen")
    anzahl = st.slider("Anzahl Treffer", 3, 20, 8)
    ki_schlagworte = st.toggle("Frage per KI in Schlagworte übersetzen", value=True)
    ki_antwort = st.toggle("KI-Zusammenfassung erzeugen", value=True)

    st.header("Filter")
    auswahl = st.multiselect("Gerichtsbarkeit", suche.gerichtsbarkeiten(),
                             placeholder="alle")
    erstes, letztes = suche.jahresspanne()
    von, bis = st.slider("Entscheidungsjahr", erstes, letztes, (erstes, letztes))
    filter = suche.Filter(
        gerichtsbarkeiten=auswahl,
        von_jahr=von if von > erstes else None,         # volle Spanne = nicht filtern
        bis_jahr=bis if bis < letztes else None,
    )
    st.divider()
    st.caption("Daten: [Open Legal Data](https://openlegaldata.io) – vielen Dank an die Ersteller "
               "(Ostendorff, Blume & Ostendorff, [JCDL 2020](https://doi.org/10.1145/3383583.3398616)). "
               "Lizenz: ODbL 1.0. Keine Rechtsberatung.")

# --- Suchfeld --------------------------------------------------------------
# Ein Formular sorgt dafür, dass auch die Enter-Taste die Suche startet.
with st.form("suchformular"):
    frage = st.text_input("Frage oder Schlagworte",
                          placeholder="z. B. Eigenbedarfskündigung wegen Wohnbedarf der Tochter")
    gesendet = st.form_submit_button("Suchen", type="primary")

if gesendet and frage.strip():
    try:
        with st.spinner("Suche läuft ..."):
            schlagworte = llm.frage_zu_schlagworten(frage) if ki_schlagworte else frage.split()
            treffer = suche.hybride_suche(frage, schlagworte, anzahl, filter)
    except ConnectionError:
        st.error(OLLAMA_FEHLER)
        st.stop()
    except ollama.ResponseError as fehler:              # z. B. Modell nicht geladen
        st.error(f"Fehler von Ollama: {fehler.error}. Mit „ollama list“ prüfen, "
                 "ob die Modelle aus config.py geladen sind.")
        st.stop()

    st.markdown("**Suchbegriffe:** " + " · ".join(schlagworte))

    if not treffer:
        st.warning("Keine passenden Urteile gefunden.")
        st.stop()

    if ki_antwort:
        st.subheader("Zusammenfassung")
        try:
            st.write_stream(llm.antwort_streamen(frage, treffer[:5]))   # Text erscheint live
            st.caption("KI-generiert auf Grundlage der Treffer [1] bis [5]. "
                       "Jede Aussage am Urteil prüfen.")
        except ConnectionError:
            st.error(OLLAMA_FEHLER)
        except ollama.ResponseError as fehler:
            st.error(f"Fehler von Ollama: {fehler.error}")

    st.subheader("Gefundene Urteile")
    for nr, t in enumerate(treffer, 1):
        titel = (f"[{nr}] {t['gericht'] or 'Gericht unbekannt'} · {t['typ'] or 'Entscheidung'} "
                 f"vom {t['datum']} · {t['aktenzeichen']}")
        with st.expander(titel, expanded=(nr <= 3)):
            if t["kurzfassung"]:
                st.markdown(f"**Kurzfassung:** {normen.verlinken(t['kurzfassung'])}")
            if t["schlagworte"]:
                st.markdown(f"**Schlagworte:** {t['schlagworte']}")
            st.info(normen.verlinken(t["auszug"]))
            st.caption("Gefunden durch: " + " + ".join(t["gefunden_durch"]))
            st.link_button("Volltext bei Open Legal Data",
                           f"https://de.openlegaldata.io/case/{t['slug']}")
