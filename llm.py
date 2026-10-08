"""Alles, was mit dem Sprachmodell (LLM) zu tun hat.

Fünf Aufgaben:
  1. frage_zu_schlagworten  - macht aus einer Frage eine Liste von Suchbegriffen
  2. urteil_pruefen         - Stufe 1: prüft EIN Urteil einzeln (relevant? was entschieden? Rn.?)
  3. antwort_streamen       - Stufe 2: schreibt die gegliederte Antwort mit Fundstellen
  4. aussagen_pruefen       - Zitatprüfung: stützt das Urteil die Aussagen, die es zitieren?
  5. urteil_verschlagworten - vergibt Schlagworte und eine Kurzfassung für ein Urteil
"""
import json

import ollama

import config
import gliederung

PROMPT_SCHLAGWORTE = """Du bist juristische Rechercheassistenz für deutsches Recht.
Wandle die Frage des Nutzers in 3 bis 8 Suchbegriffe für eine Urteilsdatenbank um.
Nutze juristische Fachbegriffe, Synonyme und relevante Normen (z. B. "§ 573 BGB").
Antworte ausschließlich als JSON: {"schlagworte": ["...", "..."]}"""

PROMPT_PRUEFUNG = """Du bist juristische Rechercheassistenz für deutsches Recht.
Prüfe EIN Urteil darauf, ob es zur Beantwortung der Frage beiträgt. Nutze nur den gegebenen Text.
"relevant" ist nur true, wenn der Text die Frage zumindest teilweise beantwortet –
nicht schon dann, wenn nur das Rechtsgebiet passt.
Antworte ausschließlich als JSON:
{"relevant": true oder false,
 "begruendung": "1 Satz: warum relevant oder nicht",
 "entscheidung": "1 bis 3 Sätze: Was hat das Gericht im konkreten Fall zu dieser Frage entschieden?",
 "rechtssatz": "allgemeiner Grundsatz, den das Gericht selbst formuliert, sonst leer",
 "normen": ["§ ... Gesetz"],
 "randnummern": [Randnummern der Stellen, auf die sich die Entscheidung stützt, als Zahlen]}"""

PROMPT_ANTWORT = """Du bist juristische Rechercheassistenz für deutsches Recht.
Beantworte die Frage AUSSCHLIESSLICH auf Grundlage des nummerierten Materials zu den Urteilen.

Gliedere die Antwort genau so:

**1. Kurzantwort**
2 bis 3 Sätze, mit Vorbehalt (z. B. "Nach den gefundenen Entscheidungen ...").

**2. Einschlägige Normen**
Stichpunkte: Norm – wofür sie hier eine Rolle spielt [n].

**3. Rechtsprechung**
Ein Stichpunkt je Urteil: Gericht, Datum, Aktenzeichen – was das Gericht im konkreten Fall entschieden hat und warum (Rn. x) [n].

**4. Abweichende oder einschränkende Entscheidungen**
Urteile, die anders entscheiden oder die Aussage einschränken. Steht im Material ein
"HINWEIS: ... Rechtsprechungsänderung", nenne ihn hier als zu prüfenden Punkt, ohne zu behaupten,
welches Urteil überholt ist. Gibt es nichts davon: "Keine gefunden."

**5. Was die gefundenen Urteile nicht beantworten**
Teile der Frage, zu denen das Material nichts sagt.

Regeln:
- Belege jede inhaltliche Aussage mit der Nummer des Urteils in eckigen Klammern, z. B. [2]. Verwende nur Nummern aus dem Material.
- Nenne die wichtigsten Randnummern im Format (Rn. 15) oder (Rn. 15, 17), wenn das Material sie enthält. Erfinde keine Randnummern.
- Trenne Einzelfall und Rechtssatz: "Im konkreten Fall entschied das Gericht ..." ist etwas anderes als "Das Gericht stellt den Grundsatz auf, dass ...". Formuliere keine allgemeinen Rechtssätze, die nicht im Material stehen.
- Berücksichtige Instanz, Bedeutung und Datum: Entscheidungen oberster Gerichte (BVerfG, BGH, BAG, BVerwG, BSG, BFH, EuGH) vor denen der Instanzgerichte, häufig zitierte vor selten zitierten, neuere vor älteren.
- Erfinde keine Urteile, Aktenzeichen oder Normen.
- Sachlich, auf Deutsch, höchstens 450 Wörter. Dies ist keine Rechtsberatung."""

PROMPT_ZITATPRUEFUNG = """Du prüfst Aussagen einer KI-Antwort gegen das Urteil, auf das sie sich berufen.
Bewerte jede nummerierte Aussage:
- "ja": Die Aussage steht so oder sinngemäß im Text des Urteils (Gericht, Datum und Aktenzeichen aus dem Kopf zählen mit).
- "teilweise": Ein Teil stimmt, aber etwas ist übertrieben, zu allgemein oder steht nicht im Text.
- "nein": Der Text stützt die Aussage nicht oder sagt etwas anderes.
Bewerte nur, ob das Urteil die Aussage trägt, nicht, ob sie rechtlich richtig ist.
Antworte ausschließlich als JSON:
{"pruefung": [{"aussage": 1, "urteil": "ja", "hinweis": "kurze Begründung"}]}"""

PROMPT_VERSCHLAGWORTUNG = """Du bist juristische Dokumentarin.
Lies den Anfang des Urteils und antworte ausschließlich als JSON:
{"schlagworte": ["5 bis 8 präzise juristische Schlagworte"],
 "kurzfassung": "1 bis 2 Sätze: Worum ging es, wie wurde entschieden?"}"""


def json_chat(system: str, nutzer: str) -> dict:
    """Hilfsfunktion: fragt das LLM und erzwingt eine JSON-Antwort."""
    antwort = ollama.chat(
        model=config.LLM_MODELL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": nutzer}],
        format="json",                                  # Ollama erzwingt gültiges JSON
        options={"temperature": 0, "num_ctx": config.LLM_KONTEXT},
        think=config.LLM_DENKEN,
    )
    try:
        daten = json.loads(antwort["message"]["content"])
    except json.JSONDecodeError:
        return {}
    return daten if isinstance(daten, dict) else {}


def frage_zu_schlagworten(frage: str) -> list[str]:
    daten = json_chat(PROMPT_SCHLAGWORTE, frage)
    worte = [str(w).strip() for w in daten.get("schlagworte", []) if str(w).strip()]
    return worte[:8] or frage.split()                   # Notfall: Wörter der Frage nehmen


# --- Material für das LLM ---------------------------------------------------

def kopf(t: dict) -> str:
    """Kopfzeile eines Treffers, z. B.
    "[2] Bundesgerichtshof, Urteil vom 2023-07-20, Az. III ZR 303/20 (Oberstes Gericht, zitiert von 912 Entscheidungen)"
    """
    zeile = (f"[{t['nr']}] {t['gericht'] or 'Gericht unbekannt'}, {t['typ'] or 'Entscheidung'} "
             f"vom {t['datum']}, Az. {t['aktenzeichen']}")
    angaben = [t.get("instanz") or ""]
    if t.get("zitiert_von"):
        angaben.append(f"zitiert von {t['zitiert_von']} Entscheidungen")
    angaben = [a for a in angaben if a]
    return zeile + (f" ({', '.join(angaben)})" if angaben else "")


def abweichungs_hinweise(t: dict) -> str:
    """Hinweise auf neuere Urteile, die im Zusammenhang mit t eine Rechtsprechungsänderung erörtern."""
    return "\n".join(
        f"HINWEIS zu [{t['nr']}] (Az. {t['aktenzeichen']}): Die spätere Entscheidung {a['gericht']} vom "
        f"{a['datum']}, Az. {a['aktenzeichen']}, zitiert [{t['nr']}] an einer Stelle, an der sie eine "
        f"Rechtsprechungsänderung beschreibt: {a['erklaerung']} Ob [{t['nr']}] von dieser Änderung "
        "betroffen ist, muss am Volltext geprüft werden." for a in t.get("abweichungen") or [])


def urteil_kontext(t: dict) -> str:
    """Alles, was das LLM über EIN Urteil erfährt: Kopf, Leitsatz, Tenor, Auszug mit Randnummern."""
    teile = [kopf(t)]
    if t.get("leitsatz"):
        teile.append(f"Leitsatz:\n{gliederung.lesbar(t['leitsatz'])}")
    if t.get("tenor"):
        teile.append(f"Tenor:\n{gliederung.lesbar(t['tenor'])}")
    teile.append(f"{t['kontext_fundstelle']}:\n{gliederung.lesbar(t['kontext'])}")
    if abweichungs_hinweise(t):
        teile.append(abweichungs_hinweise(t))
    return "\n\n".join(teile)


def kontext_bauen(treffer: list[dict]) -> str:
    """Baut aus den Treffern den Text, den das LLM als 'Akte' bekommt."""
    return "\n\n---\n\n".join(urteil_kontext(t) for t in treffer)


# --- Stufe 1: jedes Urteil einzeln prüfen ----------------------------------

def pruefung_bereinigen(daten: dict) -> dict:
    """Bringt die JSON-Antwort der Einzelprüfung in eine feste Form (das LLM ist nicht immer genau)."""
    relevant = daten.get("relevant", False)
    if isinstance(relevant, str):
        relevant = relevant.strip().lower() in ("true", "ja", "yes")
    randnummern = []
    for rn in daten.get("randnummern") or []:
        ziffern = "".join(z for z in str(rn) if z.isdigit())
        if ziffern:
            randnummern.append(int(ziffern))
    return {
        "relevant": bool(relevant),
        "begruendung": str(daten.get("begruendung") or "").strip(),
        "entscheidung": str(daten.get("entscheidung") or "").strip(),
        "rechtssatz": str(daten.get("rechtssatz") or "").strip(),
        "normen": [str(n).strip() for n in daten.get("normen") or [] if str(n).strip()],
        "randnummern": randnummern,
    }


def urteil_pruefen(frage: str, t: dict) -> dict:
    """Stufe 1: Beantwortet dieses Urteil die Frage? Was genau wurde entschieden?"""
    nachricht = f"Frage: {frage}\n\nUrteil:\n{urteil_kontext(t)}"
    return pruefung_bereinigen(json_chat(PROMPT_PRUEFUNG, nachricht))


def notiz(t: dict, pruefung: dict) -> str:
    """Ergebnis der Einzelprüfung als Material für Stufe 2."""
    zeilen = [kopf(t), f"Entscheidung im konkreten Fall: {pruefung['entscheidung']}"]
    if pruefung["rechtssatz"]:
        zeilen.append(f"Rechtssatz des Gerichts: {pruefung['rechtssatz']}")
    if pruefung["normen"]:
        zeilen.append("Normen: " + ", ".join(pruefung["normen"]))
    if pruefung["randnummern"]:
        zeilen.append("Randnummern: Rn. " + ", ".join(str(rn) for rn in sorted(set(pruefung["randnummern"]))))
    if t.get("tenor"):
        zeilen.append(f"Tenor (Auszug): {gliederung.lesbar(t['tenor'])[:400]}")
    if abweichungs_hinweise(t):
        zeilen.append(abweichungs_hinweise(t))
    return "\n".join(zeilen)


# --- Stufe 2: die gegliederte Antwort --------------------------------------

def antwort_streamen(frage: str, treffer: list[dict], pruefungen: dict[int, dict] | None = None):
    """Liefert die Antwort Stück für Stück (für die Live-Anzeige in Streamlit).

    Mit pruefungen (Ergebnis von Stufe 1, je Treffernummer) bekommt das LLM nur
    die Notizen der relevanten Urteile. Ohne pruefungen arbeitet es direkt mit
    den Auszügen (einstufig, schneller).
    """
    if pruefungen is None:
        material = kontext_bauen(treffer)
    else:
        material = "\n\n---\n\n".join(notiz(t, pruefungen[t["nr"]]) for t in treffer
                                      if pruefungen[t["nr"]]["relevant"])
    nachricht = f"Material zu den Urteilen:\n\n{material}\n\nFrage: {frage}"
    for stueck in ollama.chat(
        model=config.LLM_MODELL,
        messages=[{"role": "system", "content": PROMPT_ANTWORT},
                  {"role": "user", "content": nachricht}],
        options={"temperature": 0.2, "num_ctx": config.LLM_KONTEXT},
        think=config.LLM_DENKEN,
        stream=True,
    ):
        yield stueck["message"]["content"]


# --- Zitatprüfung -----------------------------------------------------------

def aussagen_pruefen(t: dict, aussagen: list[str]) -> list[dict]:
    """Prüft, ob das Urteil t die Aussagen stützt. Ergebnis in derselben Reihenfolge.

    Jedes Ergebnis: {"urteil": "ja" | "teilweise" | "nein" | "unklar", "hinweis": "..."}
    """
    liste = "\n".join(f"{i}. {a}" for i, a in enumerate(aussagen, 1))
    nachricht = f"Urteil:\n{urteil_kontext(t)}\n\nAussagen:\n{liste}"
    daten = json_chat(PROMPT_ZITATPRUEFUNG, nachricht)
    ergebnisse = [{"urteil": "unklar", "hinweis": "Keine Bewertung erhalten."} for _ in aussagen]
    for eintrag in daten.get("pruefung") or []:
        if not isinstance(eintrag, dict):
            continue
        try:
            i = int(eintrag.get("aussage")) - 1
        except (TypeError, ValueError):
            continue
        urteil = str(eintrag.get("urteil", "")).strip().lower()
        if 0 <= i < len(aussagen) and urteil in ("ja", "teilweise", "nein"):
            ergebnisse[i] = {"urteil": urteil, "hinweis": str(eintrag.get("hinweis") or "").strip()}
    return ergebnisse


def urteil_verschlagworten(text: str) -> tuple[list[str], str]:
    daten = json_chat(PROMPT_VERSCHLAGWORTUNG, text[:6000])  # Anfang reicht: Tenor + Leitsätze
    worte = [str(w).strip() for w in daten.get("schlagworte", []) if str(w).strip()]
    return worte[:8], str(daten.get("kurzfassung", "")).strip()
