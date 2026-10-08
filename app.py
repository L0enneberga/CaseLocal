"""Die Weboberfläche.

Aufruf:  streamlit run app.py   (oder Doppelklick auf start.bat)
Danach öffnet sich der Browser mit http://localhost:8501

Ablauf einer Recherche:
  1. Suche          - die Frage wird in Suchbegriffe übersetzt, die hybride Suche findet Urteile
  2. Einzelprüfung  - das LLM prüft jedes Urteil einzeln: relevant? was entschieden? (abschaltbar)
  3. Antwort        - das LLM schreibt eine gegliederte Antwort mit Fundstellen
  4. Zitatprüfung   - das LLM prüft, ob die zitierten Urteile die Aussagen stützen (abschaltbar)
"""
import re

import ollama
import streamlit as st

import belege
import config
import gliederung
import llm
import normen
import suche

OLLAMA_FEHLER = "Ollama ist nicht erreichbar. Bitte die Ollama-App starten und neu suchen."

st.set_page_config(page_title="CaseLocal", page_icon="⚖️", layout="wide")
st.title("CaseLocal")
st.caption(f"{suche.anzahl_urteile():,} Urteile · Modell: {config.LLM_MODELL} · "
           "Lokale KI-Recherche in deutscher Rechtsprechung".replace(",", "."))

# --- Seitenleiste mit Einstellungen ---------------------------------------
with st.sidebar:
    st.header("Einstellungen")
    anzahl = st.slider("Anzahl Treffer", 3, 20, 8)
    ki_schlagworte = st.toggle("Frage per KI in Schlagworte übersetzen", value=True)
    ki_antwort = st.toggle("KI-Antwort erzeugen", value=True)
    gruendlich = st.toggle(
        "Gründliche Analyse", value=True, disabled=not ki_antwort,
        help="Das Sprachmodell prüft zuerst jedes Urteil einzeln und sortiert unpassende aus. "
             "Erst danach schreibt es die Antwort. Dauert länger, ist aber genauer.")
    zitatpruefung = st.toggle(
        "Zitatprüfung", value=True, disabled=not ki_antwort,
        help="Ein zweiter Durchgang prüft jeden Satz der Antwort: Stützt das zitierte Urteil "
             "die Aussage wirklich? Nicht belegte Sätze werden markiert.")

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


def pruefung_zeile(t: dict, p: dict) -> str:
    """Eine Zeile für das Ergebnis der Einzelprüfung eines Urteils."""
    kopf = f"**[{t['nr']}]** {t['gericht'] or 'Gericht unbekannt'} · {t['aktenzeichen']} — "
    if not p["relevant"]:
        return kopf + f":gray-badge[aussortiert] {p['begruendung']}"
    rn = ", ".join(str(r) for r in sorted(set(p["randnummern"])))
    return kopf + f":green-badge[relevant] {p['entscheidung']}" + (f" (Rn. {rn})" if rn else "")


def absaetze(antwort: str) -> str:
    """Leerzeile nach fetten Zwischenüberschriften ("**1. Kurzantwort**"), sonst klebt Markdown
    die Überschrift und den folgenden Text in eine Zeile."""
    return re.sub(r"(?m)^(\*\*[^*\n]+\*\*)[ \t]*\n(?=\S)", r"\1\n\n", antwort)


def recherchieren(frage: str) -> dict:
    """Führt die ganze Recherche aus und zeigt dabei den Fortschritt an.

    Das Ergebnis wird in st.session_state gespeichert, damit es beim nächsten
    Neuzeichnen der Seite (z. B. nach einem Klick in der Seitenleiste) erhalten bleibt.
    """
    e = {"frage": frage, "treffer": [], "auswahl": [], "pruefungen": None,
         "antwort": None, "aussagen": None}

    with st.status("Suche passende Urteile …", type="step") as status:
        e["schlagworte"] = llm.frage_zu_schlagworten(frage) if ki_schlagworte else frage.split()
        e["treffer"] = suche.hybride_suche(frage, e["schlagworte"], anzahl, filter)
        status.update(label=f"Suche: {len(e['treffer'])} Urteile gefunden", state="complete")
    if not e["treffer"] or not ki_antwort:
        return e
    e["auswahl"] = e["treffer"][: config.KI_TREFFER]   # nur die besten gehen an das LLM

    # Stufe 1: jedes Urteil einzeln prüfen
    if gruendlich:
        with st.status("Prüfe jedes Urteil einzeln …", type="step", expanded=True) as status:
            e["pruefungen"] = {}
            for t in e["auswahl"]:
                status.update(label=f"Prüfe Urteil [{t['nr']}] von {len(e['auswahl'])} …")
                e["pruefungen"][t["nr"]] = llm.urteil_pruefen(frage, t)
                st.markdown(pruefung_zeile(t, e["pruefungen"][t["nr"]]))
            relevant = sum(p["relevant"] for p in e["pruefungen"].values())
            status.update(label=f"Einzelprüfung: {relevant} von {len(e['auswahl'])} Urteilen relevant",
                          state="complete", expanded=False)
        if not relevant:
            e["antwort"] = ""
            return e

    # Stufe 2: gegliederte Antwort, live angezeigt
    st.subheader("Antwort")
    e["antwort"] = st.write_stream(llm.antwort_streamen(frage, e["auswahl"], e["pruefungen"]))

    # Zitatprüfung
    if zitatpruefung:
        with st.status("Prüfe die Belege der Antwort …", type="step") as status:
            def fortschritt(schritt: int, gesamt: int) -> None:
                status.update(label=f"Zitatprüfung: Urteil {schritt} von {gesamt} …")
            e["aussagen"] = belege.pruefen(e["antwort"], e["auswahl"], fortschritt)
            status.update(label="Zitatprüfung abgeschlossen", state="complete")
    return e


def antwort_anzeigen(e: dict) -> None:
    st.subheader("Antwort")
    if e["antwort"] == "":
        st.info("Keines der geprüften Urteile beantwortet die Frage. Tipp: anders formulieren, "
                "Filter lockern oder mehr Treffer einstellen.")
        return
    if e["aussagen"] is None:
        st.markdown(absaetze(e["antwort"]))
    else:
        st.markdown(absaetze(belege.markieren(e["antwort"], e["aussagen"])))
        z = belege.zusammenfassung(e["aussagen"])
        st.caption(f"Zitatprüfung von {len(e['aussagen'])} belegten Aussagen: "
                   f":green[:material/check:] {z['ja']} gestützt · "
                   f":orange[:material/help:] {z['teilweise']} teilweise gestützt · "
                   f":red[:material/close:] {z['nein']} nicht gestützt"
                   + (f" · :gray[:material/question_mark:] {z['unklar']} unklar" if z["unklar"] else ""))
        offen = [a for a in e["aussagen"] if a["urteil"] != "ja"]
        if offen:
            with st.expander(f"Hinweise der Zitatprüfung ({len(offen)})", icon=":material/rule:"):
                for a in offen:
                    st.markdown(f"- *{a['satz']}*  \n  " + " ".join(a["hinweise"]))
    st.caption(f"KI-generiert auf Grundlage der Treffer [1] bis [{len(e['auswahl'])}]. "
               "Auch die Zitatprüfung erfolgt durch das Sprachmodell und kann irren – "
               "maßgeblich ist immer der Urteilstext.")


def anzeigen(e: dict) -> None:
    """Zeigt ein gespeichertes Rechercheergebnis an."""
    st.markdown("**Suchbegriffe:** " + " · ".join(e["schlagworte"]))
    if not e["treffer"]:
        st.warning("Keine passenden Urteile gefunden.")
        return

    if e["pruefungen"]:
        relevant = sum(p["relevant"] for p in e["pruefungen"].values())
        with st.expander(f"Einzelprüfung: {relevant} von {len(e['auswahl'])} Urteilen relevant",
                         icon=":material/fact_check:"):
            for t in e["auswahl"]:
                st.markdown(pruefung_zeile(t, e["pruefungen"][t["nr"]]))

    if e["antwort"] is not None:
        antwort_anzeigen(e)

    st.subheader("Gefundene Urteile")
    for t in e["treffer"]:
        titel = (f"[{t['nr']}] {t['gericht'] or 'Gericht unbekannt'} · {t['typ'] or 'Entscheidung'} "
                 f"vom {t['datum']} · {t['aktenzeichen']}")
        with st.expander(titel, expanded=(t["nr"] <= 3)):
            if e["pruefungen"] and t["nr"] in e["pruefungen"]:
                st.markdown(pruefung_zeile(t, e["pruefungen"][t["nr"]]).split(" — ", 1)[1])
            if t["kurzfassung"]:
                st.markdown(f"**Kurzfassung:** {normen.verlinken(t['kurzfassung'])}")
            if t["schlagworte"]:
                st.markdown(f"**Schlagworte:** {t['schlagworte']}")
            if t["leitsatz"]:
                st.markdown(f"**Leitsatz:** {normen.verlinken(gliederung.lesbar(t['leitsatz']))}")
            if t["tenor"]:
                tenor = gliederung.lesbar(t["tenor"])
                st.markdown(f"**Tenor:** {normen.verlinken(tenor[:500])}" + (" […]" if len(tenor) > 500 else ""))
            st.markdown(f"**Fundstelle:** {t['fundstelle']}")
            auszug = gliederung.ab_randnummer(t["auszug"])
            st.info(normen.verlinken(gliederung.lesbar(auszug, markdown=True)))
            st.caption("Gefunden durch: " + " + ".join(t["gefunden_durch"]))
            st.link_button("Volltext bei Open Legal Data",
                           f"https://de.openlegaldata.io/case/{t['slug']}")


if gesendet and frage.strip():
    try:
        st.session_state.ergebnis = recherchieren(frage)
    except ConnectionError:
        st.error(OLLAMA_FEHLER)
        st.stop()
    except ollama.ResponseError as fehler:              # z. B. Modell nicht geladen
        st.error(f"Fehler von Ollama: {fehler.error}. Mit „ollama list“ prüfen, "
                 "ob die Modelle aus config.py geladen sind.")
        st.stop()
    st.rerun()                                         # Fortschrittsanzeige durch das Ergebnis ersetzen

if "ergebnis" in st.session_state:
    anzeigen(st.session_state.ergebnis)
