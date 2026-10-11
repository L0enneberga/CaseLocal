"""Die Weboberfläche.

Aufruf:  streamlit run app.py   (oder Doppelklick auf start.bat)
Danach öffnet sich der Browser mit http://localhost:8501

Ablauf einer Recherche:
  1. Suche          - die Frage wird in Suchbegriffe übersetzt, die hybride Suche findet Urteile
  2. Einzelprüfung  - das LLM prüft jedes Urteil einzeln: relevant? was entschieden? (abschaltbar)
  3. Antwort        - das LLM schreibt eine gegliederte Antwort mit Fundstellen
  4. Zitatprüfung   - das LLM prüft, ob die zitierten Urteile die Aussagen stützen (abschaltbar)

Aufbau der Seite (siehe DESIGN.md): Frage mit eingeklappten Einstellungen, eine Statuszeile,
dann der Befund (Kurzantwort neben der Zitatprüfung) und die ausführliche Antwort neben den
Fundstellen. Farben und Schriften stehen in .streamlit/config.toml und static/caselocal.css.
"""
import html
import re
import time
from pathlib import Path

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
ORDNER = Path(__file__).parent

def zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def datum_de(datum: str) -> str:
    """"2013-11-14" -> "14.11.2013"; alles andere bleibt, wie es ist."""
    teile = (datum or "").split("-")
    return ".".join(reversed(teile)) if len(teile) == 3 else (datum or "")


st.set_page_config(page_title="CaseLocal", page_icon="⚖️", layout="wide")
st.html(f"<style>{(ORDNER / 'static' / 'caselocal.css').read_text(encoding='utf-8')}</style>")

ANZAHL_URTEILE = suche.anzahl_urteile()
BESTAND = {"bedeutend": f"{zahl(ANZAHL_URTEILE)} von rund 424.000 Entscheidungen",
           "stichprobe": f"{zahl(ANZAHL_URTEILE)} Entscheidungen (Zufallsstichprobe)"}[config.DATENAUSWAHL]
st.html(f'<header class="cl-top"><span class="cl-mark"><i></i>CaseLocal</span>'
        f'<span class="cl-status"><span class="cl-live" title="Läuft lokal, kein Text verlässt den Rechner">'
        f'Lokal</span><span class="cl-opt">{config.LLM_MODELL} · {BESTAND} · Bundesrecht</span></span></header>')

# --- Suchfeld --------------------------------------------------------------
# Ein Formular sorgt dafür, dass auch die Enter-Taste die Suche startet.
with st.container(key="frage"):
    with st.form("suchformular", border=False):
        spalte_frage, spalte_knopf = st.columns([5, 1.1], vertical_alignment="bottom")
        frage = spalte_frage.text_input("Rechtsfrage oder Schlagworte",
                                        placeholder="z. B. Eigenbedarfskündigung wegen Wohnbedarf der Tochter")
        gesendet = spalte_knopf.form_submit_button("Recherchieren", type="primary",
                                                   icon=":material/search:", width="stretch")

# --- Einstellungen, eingeklappt unter dem Suchfeld --------------------------
erstes, letztes = suche.jahresspanne()


def einstellungen_kurz() -> str:
    """Die aktuellen Einstellungen in einer Zeile, damit sie auch eingeklappt sichtbar sind."""
    s = st.session_state
    teile = [f"{s.get('anzahl', 8)} Treffer",
             ", ".join(s.get("gerichte") or []) or "alle Gerichtsbarkeiten"]
    jahre = tuple(s.get("jahre") or (erstes, letztes))
    if jahre != (erstes, letztes):
        teile.append(f"{jahre[0]}–{jahre[1]}")
    schalter = ["ki_schlagworte", "ki_antwort", "abweichungen"]
    if s.get("ki_antwort", True):
        schalter += ["gruendlich", "zitatpruefung"]
    an = sum(s.get(k, True) for k in schalter)
    teile.append("alle Prüfungen an" if an == len(schalter) else f"{an} von {len(schalter)} Optionen an")
    return " · ".join(teile)


with st.expander(f"**Einstellungen** :gray[{einstellungen_kurz()}]", key="einstellungen",
                 icon=":material/tune:"):
    spalte_suche, spalte_pruefung, spalte_filter = st.columns(3, gap="large")
    with spalte_suche:
        st.html('<p class="cl-gruppe">Suche</p>')
        anzahl = st.slider("Anzahl Treffer", 3, 20, 8, key="anzahl")
        ki_schlagworte = st.toggle("Frage per KI in Schlagworte übersetzen", value=True, key="ki_schlagworte")
    with spalte_pruefung:
        st.html('<p class="cl-gruppe">Prüfungen</p>')
        ki_antwort = st.toggle("KI-Antwort erzeugen", value=True, key="ki_antwort")
        gruendlich = st.toggle(
            "Gründliche Analyse", value=True, disabled=not ki_antwort, key="gruendlich",
            help="Das Sprachmodell prüft zuerst jedes Urteil einzeln und sortiert unpassende aus. "
                 "Erst danach schreibt es die Antwort. Dauert länger, ist aber genauer.")
        zitatpruefung = st.toggle(
            "Zitatprüfung", value=True, disabled=not ki_antwort, key="zitatpruefung",
            help="Ein zweiter Durchgang prüft jeden Satz der Antwort: Stützt das zitierte Urteil "
                 "die Aussage wirklich? Nicht belegte Sätze werden markiert.")
        abweichungen_pruefen = st.toggle(
            "Auf Rechtsprechungsänderungen prüfen", value=True, key="abweichungen",
            help="Sucht neuere Urteile gleicher oder höherer Instanz, die einen Treffer zitieren und dabei "
                 "eine Änderung der Rechtsprechung erörtern (z. B. „hält an seiner Rechtsprechung nicht mehr "
                 "fest“). Ob der Treffer die alte oder neue Linie vertritt, zeigt die Originalstelle.")
    with spalte_filter:
        st.html('<p class="cl-gruppe">Filter</p>')
        auswahl = st.multiselect("Gerichtsbarkeit", suche.gerichtsbarkeiten(), placeholder="alle",
                                 key="gerichte")
        von, bis = st.slider("Entscheidungsjahr", erstes, letztes, (erstes, letztes), key="jahre")
    filter = suche.Filter(
        gerichtsbarkeiten=auswahl,
        von_jahr=von if von > erstes else None,         # volle Spanne = nicht filtern
        bis_jahr=bis if bis < letztes else None,
    )


def pruefung_zeile(t: dict, p: dict) -> str:
    """Eine Zeile für das Ergebnis der Einzelprüfung eines Urteils."""
    kopf = f"**[{t['nr']}]** {t['gericht'] or 'Gericht unbekannt'} · {t['aktenzeichen']} — "
    if not p["relevant"]:
        return kopf + f":gray-badge[aussortiert] {p['begruendung']}"
    rn = ", ".join(str(r) for r in sorted(set(p["randnummern"])))
    return kopf + f":green-badge[relevant] {p['entscheidung']}" + (f" (Rn. {rn})" if rn else "")


def badges(t: dict) -> str:
    """Kennzeichnung eines Treffers: Instanz, Zitierhäufigkeit, Jahr, ggf. Warnung."""
    teile = [f":gray-badge[{t['instanz']}]"] if t.get("instanz") else []
    if t.get("zitiert_von"):
        teile.append(f":gray-badge[zitiert von {t['zitiert_von']}]")
    if t.get("datum"):
        teile.append(f":gray-badge[{t['datum'][:4]}]")
    if t.get("abweichungen"):
        teile.append(":orange-badge[:material/history: Rechtsprechungsänderung prüfen]")
    return " ".join(teile)


def ueberschriften(antwort: str) -> str:
    """Macht aus den fetten Abschnittsköpfen ("**2. Einschlägige Normen**") echte Überschriften
    ohne Nummer. Den Kopf "Kurzantwort" setzt die Seite selbst, er fällt hier weg."""
    def ersetzen(m: re.Match) -> str:
        return "" if m[1] == "1" else f"\n#### {m[2].strip()}\n"
    return re.sub(r"(?m)^\s*(?:#{1,6}\s*\**|\*\*)\s*(\d)\.\s*([^*\n]+?)\**\s*$", ersetzen, antwort)


def recherchieren(frage: str) -> dict:
    """Führt die ganze Recherche aus und zeigt dabei den Fortschritt an.

    Das Ergebnis wird in st.session_state gespeichert, damit es beim nächsten
    Neuzeichnen der Seite (z. B. nach einem Klick in den Einstellungen) erhalten bleibt.
    """
    e = {"frage": frage, "treffer": [], "auswahl": [], "pruefungen": None,
         "antwort": None, "aussagen": None, "korrekturen": [], "entwicklung": [], "normen": [],
         "normvorschlaege": [], "dauer": {}}
    start = time.perf_counter()

    def gestoppt(stufe: str) -> None:                  # Laufzeit je Stufe für die Statuszeile
        nonlocal start
        e["dauer"][stufe] = time.perf_counter() - start
        start = time.perf_counter()

    with st.status("Suche passende Urteile …", type="step") as status:
        e["schlagworte"] = llm.frage_zu_schlagworten(frage) if ki_schlagworte else frage.split()
        e["treffer"] = suche.hybride_suche(frage, e["schlagworte"], anzahl, filter)
        status.update(label=f"Suche: {len(e['treffer'])} Urteile gefunden", state="complete")
    gestoppt("Suche")

    if e["treffer"] and abweichungen_pruefen:
        with st.status("Prüfe auf neuere, abweichende Rechtsprechung …", type="step") as status:
            gefunden = abweichung.alle_pruefen(e["treffer"])   # landet auch im Material für das LLM
            status.update(label=f"Rechtsprechungsänderungen: bei {gefunden} Urteil(en) zu prüfen"
                          if gefunden else "Rechtsprechungsänderungen: keine Hinweise gefunden",
                          state="complete")
        gestoppt("Rechtsprechungsänderungen")
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
        gestoppt("Einzelprüfung")
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
    gestoppt("Antwort")

    # Zitatprüfung
    if zitatpruefung:
        with st.status("Prüfe die Belege der Antwort …", type="step") as status:
            def fortschritt(schritt: int, gesamt: int) -> None:
                status.update(label=f"Zitatprüfung: Urteil {schritt} von {gesamt} …")
            e["aussagen"] = belege.pruefen(e["antwort"], e["auswahl"], fortschritt)
            status.update(label="Zitatprüfung abgeschlossen", state="complete")
        gestoppt("Zitatprüfung")
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


def ablauf_anzeigen(e: dict) -> None:
    """Eine Statuszeile für die fertige Recherche; Stufen, Suchbegriffe und Einzelprüfung eingeklappt."""
    teile = [f"{len(e['treffer'])} Treffer"]
    if e["pruefungen"]:
        teile[0] += f", {sum(p['relevant'] for p in e['pruefungen'].values())} relevant"
    if e["aussagen"] is not None:
        teile.append(f"{len(e['aussagen']) - belege.zusammenfassung(e['aussagen'])['hinweis']} Aussagen geprüft")
    dauer = e.get("dauer") or {}
    if dauer:
        teile.append(f"{sum(dauer.values()):.1f} s auf diesem Rechner".replace(".", ","))
    st.html(f'<div class="cl-run"><span class="cl-ok">Recherche abgeschlossen</span>'
            + "".join(f"<span>{html.escape(t)}</span>" for t in teile) + "</div>")
    with st.expander("Ablauf und Suchbegriffe", key="ablauf", icon=":material/timeline:"):
        if dauer:
            st.html('<div class="cl-stufen">' + "".join(
                f"<div><b>{html.escape(stufe)}</b><span>{s:.1f} s</span></div>".replace(".", ",")
                for stufe, s in dauer.items()) + "</div>")
        st.markdown("**Suchbegriffe:** " + " · ".join(e["schlagworte"]))
        if e["pruefungen"]:
            st.markdown("**Einzelprüfung**")
            for t in e["auswahl"]:
                st.markdown(pruefung_zeile(t, e["pruefungen"][t["nr"]]))


def bilanz_anzeigen(e: dict, key: str = "bilanz") -> None:
    """Die Zitatprüfung auf einen Blick: gestützte Aussagen, eine Marke je Aussage, die Zählung."""
    if not e["aussagen"]:
        return
    z = belege.zusammenfassung(e["aussagen"])
    geprueft = len(e["aussagen"]) - z["hinweis"]
    # eine Marke je Aussage; der Füllgrad zeigt das Ergebnis (voll, halb, leer, gestrichelt)
    marken = "".join(f'<i class="cl-m-{a["urteil"]}"></i>' for a in e["aussagen"] if a["urteil"] != "hinweis")
    with st.container(border=True, key=key):
        st.html(f'<div class="cl-bilanz-h"><span class="cl-label">Zitatprüfung</span><span>{geprueft} Aussagen</span></div>'
                f'<div class="cl-score"><b>{z["ja"]}</b><span>von {geprueft} gestützt</span></div>'
                f'<div class="cl-marks" aria-hidden="true">{marken}</div>')
        zeilen = [(":green[:material/check_circle:]", z["ja"], "gestützt"),
                  (":orange[:material/contrast:]", z["teilweise"], "teilweise gestützt"),
                  (":red[:material/cancel:]", z["nein"], "nicht gestützt")]
        if z["unklar"]:
            zeilen.append((":gray[:material/help:]", z["unklar"], "unklar"))
        if z["hinweis"]:
            zeilen.append((":gray[:material/info:]", z["hinweis"], "Hinweise, nicht geprüft"))
        st.markdown("  \n".join(f"{zeichen} **{n}** {text}" for zeichen, n, text in zeilen))
        st.caption("Gesetze in heutiger Fassung · keine Rechtsberatung")


def quelle_html(t: dict, p: dict | None, extra: bool = False) -> str:
    """Eine Fundstelle in der Liste rechts: Nummer, Gericht und Az., Datum, Zitierhäufigkeit, Rn."""
    gericht = [t["gericht"] or "Gericht unbekannt", datum_de(t.get("datum", ""))]
    meta = []
    if t.get("zitiert_von"):
        meta.append(f"zitiert von {t['zitiert_von']}")
    warum = ""
    if p and p["relevant"] and p["randnummern"]:
        meta.append("Rn. " + ", ".join(str(r) for r in sorted(set(p["randnummern"]))))
    if p and not p["relevant"]:
        warum = f'<div class="why"><span class="cl-tag">aussortiert</span>{html.escape(p["begruendung"])}</div>'
    elif extra:
        warum = '<div class="why">relevant, in der Antwort nicht zitiert</div>'
    klasse = "cl-src" + (" out" if p and not p["relevant"] else " extra" if extra else "")
    return (f'<li class="{klasse}"><span class="no">{t["nr"]}</span><div>'
            f'<div class="az">{html.escape(t["aktenzeichen"])}</div>'
            f'<div class="meta">{" · ".join(html.escape(m) for m in gericht if m)}</div>'
            + (f'<div class="meta">{" · ".join(html.escape(m) for m in meta)}</div>' if meta else "")
            + f'{warum}</div></li>')


def fundstellen_anzeigen(e: dict) -> None:
    """Die zitierten Urteile; geprüfte, aber nicht zitierte Urteile eingeklappt darunter."""
    pruefungen = e["pruefungen"] or {}
    liste = e["auswahl"] or e["treffer"]
    zitiert = set(belege.quellen(e["antwort"] or ""))
    haupt = [t for t in liste if t["nr"] in zitiert] if zitiert else liste
    weitere = [t for t in liste if t not in haupt]
    titel = "Fundstellen" if zitiert else "Treffer"
    st.html(f'<div class="cl-h">{titel}<span>{len(haupt)} {"zitiert" if zitiert else "gefunden"}</span></div>'
            f'<ol class="cl-srcs">{"".join(quelle_html(t, pruefungen.get(t["nr"])) for t in haupt)}</ol>')
    if weitere:
        aussortiert = sum(1 for t in weitere if t["nr"] in pruefungen and not pruefungen[t["nr"]]["relevant"])
        teile = [f"{len(weitere) - aussortiert} weitere relevant"] if len(weitere) > aussortiert else []
        if aussortiert:
            teile.append(f"{aussortiert} aussortiert")
        with st.expander(" · ".join(teile), key="weitere"):
            st.html('<ol class="cl-srcs">' + "".join(quelle_html(t, pruefungen.get(t["nr"]), extra=True)
                                                    for t in weitere) + "</ol>")


def antwort_anzeigen(e: dict) -> None:
    """Befund (Kurzantwort) und die ausführliche Antwort darunter."""
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
    kurz, _ = teilen(text, 1)
    bis_normen, rest = teilen(text, 2)

    with st.container(border=True, key="befund"):
        pruefung = "Zitate geprüft" if e["aussagen"] is not None else "Zitate nicht geprüft"
        st.html(f'<div class="cl-befund-h"><span class="cl-label">Kurzantwort</span>'
                f'<span class="cl-prov">vom Modell formuliert · {pruefung}</span></div>')
        st.markdown(ueberschriften(kurz))
    bilanz_anzeigen(e, key="bilanz_schmal")             # nur auf schmalen Bildschirmen sichtbar (CSS)

    with st.container(key="akte"):
        st.markdown(ueberschriften(bis_normen[len(kurz):]))
        im_wortlaut = {}                               # Normen aus Abschnitt 2, jede einmal
        for n in normen_liste:
            if 2 in n["abschnitte"] and n["wortlaut"]:
                im_wortlaut.setdefault(n["wortlaut"]["norm"], n["wortlaut"])
        for norm in im_wortlaut.values():
            wortlaut_anzeigen(norm, f"Wortlaut: {norm['norm']} – {norm['titel']}".rstrip(" –"))
        nicht_geladen = sorted({n["gesetz"] for n in normen_liste if n["status"] == "nicht im Bestand"})
        if nicht_geladen:
            st.caption(":gray[:material/info:] Nicht im Bestand der Gesetzestexte (nur die meistzitierten "
                       f"Bundesgesetze): {', '.join(nicht_geladen)}")
        if rest.strip():
            st.markdown(ueberschriften(rest))
        if e.get("entwicklung"):
            with st.expander("Originalstellen zur Rechtsprechungsänderung · per Code ergänzt, Heuristik",
                             icon=":material/history:"):
                for g in e["entwicklung"]:
                    for b in g["betroffen"]:
                        u = b["von"]
                        st.markdown(f"**{u['aktenzeichen']}** zitiert **[{b['treffer']['nr']}] "
                                    f"{b['treffer']['aktenzeichen']}** – [Volltext]"
                                    f"(https://de.openlegaldata.io/case/{u['slug']})\n\n> „…{b['stelle']}…“")
                st.caption("CaseLocal zeigt die Originalstelle, entscheidet aber nicht, welche Linie heute gilt.")
        offen = [a for a in e["aussagen"] or [] if a["urteil"] not in ("ja", "hinweis")]
        korrekturen = e.get("korrekturen") or []
        erfunden = [n for n in normen_liste if n["status"] == "fehlt"]
        if offen or korrekturen or erfunden:
            anzahl_hinweise = len(offen) + len(korrekturen) + len(erfunden)
            with st.expander(f"Hinweise der Zitatprüfung ({anzahl_hinweise})", icon=":material/rule:"):
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


def urteile_anzeigen(e: dict) -> None:
    """Alle Treffer zum Aufklappen, mit Kurzfassung, Leitsatz, Tenor und Auszug."""
    st.subheader("Urteile im Detail")
    for t in e["treffer"]:
        titel = (f"[{t['nr']}] {t['gericht'] or 'Gericht unbekannt'} · {t['typ'] or 'Entscheidung'} "
                 f"vom {t['datum']} · {t['aktenzeichen']}  {badges(t)}")
        with st.expander(titel):
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


def anzeigen(e: dict) -> None:
    """Zeigt ein gespeichertes Rechercheergebnis an."""
    if not e["treffer"]:
        st.markdown("**Suchbegriffe:** " + " · ".join(e["schlagworte"]))
        st.warning("Keine passenden Urteile gefunden.")
        return
    ablauf_anzeigen(e)
    if e["antwort"] is not None:
        links, rechts = st.columns([2.7, 1], gap="large")
        with links:
            antwort_anzeigen(e)
        with rechts:
            bilanz_anzeigen(e)
            fundstellen_anzeigen(e)
    urteile_anzeigen(e)


def fusszeile() -> None:
    """Bestand, Datenquelle und Hinweise an einer Stelle."""
    gesetze = getattr(config, "GESETZE_ANZAHL", None)
    gesetze = f"die {gesetze} meistzitierten" if gesetze else "die meistzitierten"
    st.html(
        '<footer class="cl-foot">'
        f'<div><h2>Bestand</h2><p>{BESTAND}, ausgewählt über den Zitationsgraphen. Gesetze: {gesetze} '
        'Bundesgesetze von gesetze-im-internet.de in heutiger Fassung, kein Landes- oder EU-Recht.</p></div>'
        '<div><h2>Daten</h2><p><a href="https://openlegaldata.io" target="_blank" rel="noopener">Open Legal Data</a>'
        ' – vielen Dank an die Ersteller (Ostendorff, Blume &amp; Ostendorff, '
        '<a href="https://doi.org/10.1145/3383583.3398616" target="_blank" rel="noopener">JCDL 2020</a>). '
        f'Lizenz: ODbL 1.0. Läuft vollständig lokal mit {config.LLM_MODELL} und {config.EMBED_MODELL}.</p></div>'
        '<div><h2>Hinweis</h2><p>Keine Rechtsberatung. KI-Antwort und Zitatprüfung können irren; '
        'maßgeblich ist immer der Urteilstext.</p></div>'
        '</footer>')


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
fusszeile()
