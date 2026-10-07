"""Die Weboberfläche.

Aufruf:  streamlit run app.py
Danach öffnet sich der Browser mit http://localhost:8501
"""
import streamlit as st

import config
import llm
import suche

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
    st.divider()
    st.caption("Daten: Open Legal Data (ODbL 1.0). Keine Rechtsberatung.")

# --- Suchfeld --------------------------------------------------------------
frage = st.text_input("Frage oder Schlagworte",
                      placeholder="z. B. Eigenbedarfskündigung wegen Wohnbedarf der Tochter")

if st.button("Suchen", type="primary") and frage.strip():
    try:
        with st.spinner("Suche läuft ..."):
            schlagworte = llm.frage_zu_schlagworten(frage) if ki_schlagworte else frage.split()
            treffer = suche.hybride_suche(frage, schlagworte, anzahl)
    except ConnectionError:
        st.error("Ollama ist nicht erreichbar. Bitte die Ollama-App starten und neu suchen.")
        st.stop()

    st.markdown("**Suchbegriffe:** " + " · ".join(schlagworte))

    if not treffer:
        st.warning("Keine passenden Urteile gefunden.")
        st.stop()

    if ki_antwort:
        st.subheader("Zusammenfassung")
        st.write_stream(llm.antwort_streamen(frage, treffer[:5]))   # Text erscheint live
        st.caption("KI-generiert auf Grundlage der Treffer [1] bis [5]. Jede Aussage am Urteil prüfen.")

    st.subheader("Gefundene Urteile")
    for nr, t in enumerate(treffer, 1):
        titel = f"[{nr}] {t['gericht']} · {t['typ']} vom {t['datum']} · {t['aktenzeichen']}"
        with st.expander(titel, expanded=(nr <= 3)):
            if t["kurzfassung"]:
                st.markdown(f"**Kurzfassung:** {t['kurzfassung']}")
            if t["schlagworte"]:
                st.markdown(f"**Schlagworte:** {t['schlagworte']}")
            st.info(t["auszug"])
            st.caption("Gefunden durch: " + " + ".join(t["gefunden_durch"]))
            st.link_button("Volltext bei Open Legal Data",
                           f"https://de.openlegaldata.io/case/{t['slug']}")
