"""Seite "Meine Akten": die Einträge einer Akte lesen, Notizen ändern, Einträge löschen.

Gestartet wird über app.py, das die Seiten in der Seitenleiste anzeigt.
"""
import streamlit as st

import belege
import config
import notizen

st.title("Meine Akten")

if not config.NOTIZEN_AKTIV:
    st.info("Die Akte ist ausgeschaltet (NOTIZEN_AKTIV = False in config.py), etwa weil die App "
            "öffentlich gezeigt wird. Sonst würden alle Besucher dieselben Notizen sehen.")
    st.stop()

akten = notizen.akten_auflisten()
if not akten:
    st.info("Noch keine Akte angelegt. Unter jeder Antwort auf der Seite „Recherche“ gibt es den "
            "Bereich „In Akte speichern“ mit dem Knopf „Neue Akte anlegen“.")
    st.stop()


def quellen_anzeigen(quellen: list[dict]) -> None:
    """Die gespeicherten Quellen als Liste, jede mit Link zum Volltext bei Open Legal Data."""
    zeilen = []
    for q in quellen:
        zeile = notizen.quelle_text(q)
        if q.get("slug"):
            zeile += f" · [Volltext](https://de.openlegaldata.io/case/{q['slug']})"
        zeilen.append(f"- {zeile}")
    st.markdown("**Quellen**\n\n" + "\n".join(zeilen) if zeilen else "**Quellen:** keine")


def notiz_bearbeiten(eintrag: dict) -> None:
    """Formular für die Notiz. Der Schlüssel enthält die id, damit jeder Eintrag sein eigenes Formular hat."""
    with st.form(f"notiz_{eintrag['id']}", border=False):
        notiz = st.text_area("Notiz", value=eintrag["notiz"] or "", height=90)
        if st.form_submit_button("Notiz speichern", icon=":material/edit_note:"):
            notizen.notiz_aendern(eintrag["id"], notiz)
            st.success("Notiz gespeichert.", icon=":material/check:")


def loeschen_anbieten(eintrag: dict) -> None:
    """Löschen erst nach einem Häkchen, damit kein Eintrag aus Versehen verschwindet."""
    sicher = st.checkbox("Diesen Eintrag endgültig löschen", key=f"sicher_{eintrag['id']}")
    if st.button("Löschen", key=f"loeschen_{eintrag['id']}", disabled=not sicher, icon=":material/delete:"):
        notizen.eintrag_loeschen(eintrag["id"])
        st.rerun()                                     # Seite neu aufbauen, damit der Eintrag verschwindet


def eintrag_anzeigen(eintrag: dict) -> None:
    """Ein Eintrag zum Aufklappen: Frage, Antwort, Quellen, Notiz."""
    titel = f"{eintrag['frage']} · {notizen.zeitpunkt_deutsch(eintrag['erstellt_am'])}"
    with st.expander(titel, icon=":material/description:"):
        st.markdown(f"**Frage:** {eintrag['frage']}")
        st.markdown(belege.ueberschriften(eintrag["antwort"], kurzantwort_zeigen=True))
        quellen_anzeigen(eintrag["quellen"])
        st.caption(f"Gespeichert am {notizen.zeitpunkt_deutsch(eintrag['erstellt_am'])} · "
                   f"Modell: {eintrag['modell'] or 'unbekannt'} · KI-generiert, maßgeblich ist der Urteilstext")
        st.divider()
        notiz_bearbeiten(eintrag)
        loeschen_anbieten(eintrag)


def akte_gewaehlt() -> None:
    """Callback: Die hier gewählte Akte ist auch auf der Seite "Recherche" die aktive Akte."""
    st.session_state.aktive_akte = st.session_state.akten_auswahl


# Vorauswahl: die Akte, die gerade aktiv ist (z. B. die, in der man zuletzt gespeichert hat).
if st.session_state.get("aktive_akte") not in akten:
    st.session_state.aktive_akte = akten[0]
st.session_state.akten_auswahl = st.session_state.aktive_akte
akte = st.selectbox("Akte", akten, key="akten_auswahl", on_change=akte_gewaehlt, width=480)
eintraege = notizen.eintraege_laden(akte)
if not eintraege:
    st.caption("Diese Akte ist noch leer.")
elif len(eintraege) == 1:
    st.caption("1 Eintrag")
else:
    st.caption(f"{len(eintraege)} Einträge, neueste zuerst")
for eintrag in eintraege:
    eintrag_anzeigen(eintrag)
