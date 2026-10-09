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

import abweichung
import belege
import config
import ergaenzung
import gliederung
import llm
import normen
import suche

OLLAMA_FEHLER = "Ollama ist nicht erreichbar. Bitte die Ollama-App starten und neu suchen."

st.set_page_config(page_title="CaseLocal", page_icon="⚖️", layout="wide")
st.title("CaseLocal")
BESTAND = {"bedeutend": "bedeutendste Urteile laut Zitationsgraph", "stichprobe": "Zufallsstichprobe"}
st.caption(f"{suche.anzahl_urteile():,} Urteile ({BESTAND[config.DATENAUSWAHL]}) · "
           f"Modell: {config.LLM_MODELL} · Lokale KI-Recherche in deutscher Rechtsprechung".replace(",", "."))

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
    abweichungen_pruefen = st.toggle(
        "Auf Rechtsprechungsänderungen prüfen", value=True,
        help="Sucht neuere Urteile gleicher oder höherer Instanz, die einen Treffer zitieren und dabei "
             "eine Änderung der Rechtsprechung erörtern (z. B. „hält an seiner Rechtsprechung nicht mehr "
             "fest“). Ob der Treffer die alte oder neue Linie vertritt, zeigt die Originalstelle.")

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


def badges(t: dict) -> str:
    """Kennzeichnung eines Treffers: Instanz, Zitierhäufigkeit, Jahr, ggf. Warnung."""
    farbe = {"Oberstes Gericht": "blue", "Obergericht": "violet"}.get(t.get("instanz"), "gray")
    teile = [f":{farbe}-badge[{t['instanz']}]"] if t.get("instanz") else []
    if t.get("zitiert_von"):
        teile.append(f":gray-badge[zitiert von {t['zitiert_von']}]")
    if t.get("datum"):
        teile.append(f":gray-badge[{t['datum'][:4]}]")
    if t.get("abweichungen"):
        teile.append(":orange-badge[:material/history: Rechtsprechungsänderung prüfen]")
    return " ".join(teile)


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
         "antwort": None, "aussagen": None, "korrekturen": [], "entwicklung": [], "normen": [],
         "normvorschlaege": []}

    with st.status("Suche passende Urteile …", type="step") as status:
        e["schlagworte"] = llm.frage_zu_schlagworten(frage) if ki_schlagworte else frage.split()
        e["treffer"] = suche.hybride_suche(frage, e["schlagworte"], anzahl, filter)
        status.update(label=f"Suche: {len(e['treffer'])} Urteile gefunden", state="complete")

    if e["treffer"] and abweichungen_pruefen:
        with st.status("Prüfe auf neuere, abweichende Rechtsprechung …", type="step") as status:
            gefunden = abweichung.alle_pruefen(e["treffer"])   # landet auch im Material für das LLM
            status.update(label=f"Rechtsprechungsänderungen: bei {gefunden} Urteil(en) zu prüfen"
                          if gefunden else "Rechtsprechungsänderungen: keine Hinweise gefunden",
                          state="complete")
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
            e["normvorschlaege"] = suche.normsuche(frage)
            return e

    # Stufe 2: gegliederte Antwort, live angezeigt
    st.subheader("Antwort")
    roh = st.write_stream(llm.antwort_streamen(frage, e["auswahl"], e["pruefungen"]))
    ergaenzt = ergaenzung.antwort_ergaenzen(roh, e["treffer"], e["pruefungen"])
    e["antwort"], e["korrekturen"] = ergaenzt["antwort"], ergaenzt["korrekturen"]
    e["entwicklung"], e["normen"] = ergaenzt["entwicklung"], ergaenzt["normen"]

    # Zitatprüfung
    if zitatpruefung:
        with st.status("Prüfe die Belege der Antwort …", type="step") as status:
            def fortschritt(schritt: int, gesamt: int) -> None:
                status.update(label=f"Zitatprüfung: Urteil {schritt} von {gesamt} …")
            e["aussagen"] = belege.pruefen(e["antwort"], e["auswahl"], fortschritt)
            status.update(label="Zitatprüfung abgeschlossen", state="complete")
    return e


def wortlaut_anzeigen(norm: dict, titel: str | None = None) -> None:
    """Eine Norm zum Aufklappen: Wortlaut, Stand und Link zu gesetze-im-internet.de."""
    with st.expander(titel or f"{norm['norm']} – {norm['titel']}".rstrip(" –"), icon=":material/gavel:"):
        st.markdown("  \n".join(norm["text"].split("\n")))
        st.caption(f"Stand: {norm['stand'] or 'unbekannt'} · heutige Fassung – ältere Urteile können eine "
                   f"frühere Fassung angewendet haben · [gesetze-im-internet.de]({norm['url']})")


def teilen(text: str, abschnitt: int) -> tuple[str, str]:
    """Teilt die Antwort nach einem Abschnitt: (bis einschließlich Abschnitt, Rest)."""
    zeilen = text.split("\n")
    ende = next((i for i, n in enumerate(belege.abschnitte(zeilen)) if n > abschnitt), len(zeilen))
    return "\n".join(zeilen[:ende]), "\n".join(zeilen[ende:])


def normen_markieren(text: str, normen_liste: list[dict], aussagen: list[dict] | None) -> str:
    """Erfundene Paragraphen ("fehlt") bekommen eine rote Markierung direkt im Text.

    Ausnahme: Steht die Norm in einem Satz, den die Zitatprüfung schon farbig hinterlegt hat,
    erscheint der Hinweis nur unter "Hinweise der Zitatprüfung" (verschachtelte Farben
    würden die Darstellung zerstören).
    """
    hinterlegt = [a["satz"] for a in aussagen or [] if a["urteil"] in ("teilweise", "nein")]
    for n in normen_liste:
        if n["status"] == "fehlt" and not any(n["fund"] in satz for satz in hinterlegt):
            text = text.replace(n["fund"], f"{n['fund']} :red-badge[:material/error: Norm im Gesetz nicht gefunden]", 1)
    return text


def antwort_anzeigen(e: dict) -> None:
    st.subheader("Antwort")
    if e["antwort"] == "":
        st.info("Keines der geprüften Urteile beantwortet die Frage. Tipp: anders formulieren, "
                "Filter lockern oder mehr Treffer einstellen.")
        if e.get("normvorschlaege"):
            st.markdown("**Möglicherweise einschlägige Normen** (Normsuche nach sprachlicher Ähnlichkeit zur "
                        "Frage, ohne Rechtsprechung und ohne Prüfung durch das Sprachmodell):")
            for norm in e["normvorschlaege"]:
                wortlaut_anzeigen(norm)
            st.caption("Ob und wie eine Norm auf die Frage anzuwenden ist, sagen nur Urteile und Kommentare. "
                       "Die Auswahl ist keine rechtliche Einschätzung.")
        return
    normen_liste = e.get("normen") or []
    text = e["antwort"] if e["aussagen"] is None else belege.markieren(e["antwort"], e["aussagen"])
    text = normen_markieren(text, normen_liste, e["aussagen"])
    bis_normen, rest = teilen(text, 2)
    st.markdown(absaetze(bis_normen))
    im_wortlaut = {}                                   # Normen aus Abschnitt 2, jede einmal
    for n in normen_liste:
        if n["abschnitt"] == 2 and n["wortlaut"]:
            im_wortlaut.setdefault(n["wortlaut"]["norm"], n["wortlaut"])
    for norm in im_wortlaut.values():
        wortlaut_anzeigen(norm, f"Wortlaut: {norm['norm']} – {norm['titel']}".rstrip(" –"))
    nicht_geladen = sorted({n["gesetz"] for n in normen_liste if n["status"] == "nicht im Bestand"})
    if nicht_geladen:
        st.caption(":gray[:material/info:] Nicht im Bestand der Gesetzestexte (nur die meistzitierten "
                   f"Bundesgesetze): {', '.join(nicht_geladen)}")
    if rest.strip():
        st.markdown(absaetze(rest))
    if e["aussagen"] is not None:
        z = belege.zusammenfassung(e["aussagen"])
        st.caption(f"Zitatprüfung von {len(e['aussagen']) - z['hinweis']} belegten Aussagen: "
                   f":green[:material/check:] {z['ja']} gestützt · "
                   f":orange[:material/help:] {z['teilweise']} teilweise gestützt · "
                   f":red[:material/close:] {z['nein']} nicht gestützt"
                   + (f" · :gray[:material/question_mark:] {z['unklar']} unklar" if z["unklar"] else "")
                   + (f" · :gray[:material/info:] {z['hinweis']} Hinweise nicht geprüft" if z["hinweis"] else ""))
    if e.get("entwicklung"):
        with st.expander("Originalstellen zur Rechtsprechungsänderung", icon=":material/history:"):
            for g in e["entwicklung"]:
                for b in g["betroffen"]:
                    u = b["von"]
                    st.markdown(f"**{u['aktenzeichen']}** zitiert **[{b['treffer']['nr']}] "
                                f"{b['treffer']['aktenzeichen']}** – [Volltext]"
                                f"(https://de.openlegaldata.io/case/{u['slug']})\n\n> „…{b['stelle']}…“")
    offen = [a for a in e["aussagen"] or [] if a["urteil"] not in ("ja", "hinweis")]
    korrekturen = e.get("korrekturen") or []
    erfunden = [n for n in normen_liste if n["status"] == "fehlt"]
    if offen or korrekturen or erfunden:
        anzahl = len(offen) + len(korrekturen) + len(erfunden)
        with st.expander(f"Hinweise der Zitatprüfung ({anzahl})", icon=":material/rule:"):
            for n in erfunden:
                st.markdown(f"- :red[:material/error:] **{n['fund']}**: Norm im Gesetz nicht gefunden – "
                            f"das {n['gesetz']} ist geladen, enthält diesen Paragraphen aber nicht.")
            for k in korrekturen:
                st.markdown(f"- :blue[:material/edit:] *{k['satz']}*  \n  {k['hinweis']}")
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
                 f"vom {t['datum']} · {t['aktenzeichen']}  {badges(t)}")
        with st.expander(titel, expanded=(t["nr"] <= 3)):
            for a in t.get("abweichungen") or []:
                st.warning(f"**Rechtsprechungsänderung prüfen:** {a['gericht']}, {a['typ'] or 'Entscheidung'} "
                           f"vom {a['datum']}, Az. {a['aktenzeichen']} erörtert im Zusammenhang mit diesem "
                           f"Urteil eine Änderung der Rechtsprechung. {a['erklaerung']} Ob dieses Urteil die "
                           "alte oder die neue Linie vertritt, bitte im Volltext prüfen: "
                           f"[{a['aktenzeichen']}](https://de.openlegaldata.io/case/{a['slug']})\n\n"
                           f"> „…{a['stelle']}…“", icon=":material/history:")
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
            zitiert = normen.zitierte_normen(t["id"])
            if zitiert:
                st.markdown("**Zitierte Normen:** " + " · ".join(
                    f"[{n['norm']}]({n['url']})" if n["url"] else n["norm"] for n in zitiert))
            st.markdown(f"**Fundstelle:** {t['fundstelle']}")
            auszug = gliederung.ab_randnummer(t["auszug"])
            vorinstanz = set(t.get("vorinstanz_rn") or [])
            st.info(normen.verlinken(gliederung.lesbar(auszug, markdown=True, vorinstanz=vorinstanz)))
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
