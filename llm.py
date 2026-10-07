"""Alles, was mit dem Sprachmodell (LLM) zu tun hat.

Drei Aufgaben:
  1. frage_zu_schlagworten  - macht aus einer Frage eine Liste von Suchbegriffen
  2. antwort_streamen       - fasst gefundene Urteile zusammen (mit Fundstellen)
  3. urteil_verschlagworten - vergibt Schlagworte und eine Kurzfassung für ein Urteil
"""
import json

import ollama

import config

PROMPT_SCHLAGWORTE = """Du bist juristische Rechercheassistenz für deutsches Recht.
Wandle die Frage des Nutzers in 3 bis 8 Suchbegriffe für eine Urteilsdatenbank um.
Nutze juristische Fachbegriffe, Synonyme und relevante Normen (z. B. "§ 573 BGB").
Antworte ausschließlich als JSON: {"schlagworte": ["...", "..."]}"""

PROMPT_ANTWORT = """Du bist juristische Rechercheassistenz für deutsches Recht.
Beantworte die Frage AUSSCHLIESSLICH auf Grundlage der nummerierten Urteilsauszüge.
Regeln:
- Belege jede Aussage mit der Nummer des Auszugs in eckigen Klammern, z. B. [2].
- Erfinde keine Urteile, Aktenzeichen oder Normen.
- Wenn die Auszüge die Frage nicht beantworten, sage das deutlich.
- Schreibe sachlich, auf Deutsch, höchstens 200 Wörter.
- Beschreibe, was das Gericht im konkreten Fall entschieden hat. Formuliere keine allgemeinen Rechtsätze, die über den Auszug hinausgehen.
- Dies ist keine Rechtsberatung."""

PROMPT_VERSCHLAGWORTUNG = """Du bist juristische Dokumentarin.
Lies den Anfang des Urteils und antworte ausschließlich als JSON:
{"schlagworte": ["5 bis 8 präzise juristische Schlagworte"],
 "kurzfassung": "1 bis 2 Sätze: Worum ging es, wie wurde entschieden?"}"""


def _json_chat(system: str, nutzer: str) -> dict:
    """Hilfsfunktion: fragt das LLM und erzwingt eine JSON-Antwort."""
    antwort = ollama.chat(
        model=config.LLM_MODELL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": nutzer}],
        format="json",                                  # Ollama erzwingt gültiges JSON
        options={"temperature": 0, "num_ctx": config.LLM_KONTEXT},
    )
    try:
        return json.loads(antwort["message"]["content"])
    except json.JSONDecodeError:
        return {}


def frage_zu_schlagworten(frage: str) -> list[str]:
    daten = _json_chat(PROMPT_SCHLAGWORTE, frage)
    worte = [str(w).strip() for w in daten.get("schlagworte", []) if str(w).strip()]
    return worte[:8] or frage.split()                   # Notfall: Wörter der Frage nehmen


def kontext_bauen(treffer: list[dict]) -> str:
    """Baut aus den Treffern den Text, den das LLM als 'Akte' bekommt."""
    teile = []
    for nr, t in enumerate(treffer, 1):
        kopf = f"[{nr}] {t['gericht']}, {t['typ']} vom {t['datum']}, Az. {t['aktenzeichen']}"
        teile.append(f"{kopf}\n{t['auszug']}")
    return "\n\n---\n\n".join(teile)


def antwort_streamen(frage: str, treffer: list[dict]):
    """Liefert die Antwort Stück für Stück (für die Live-Anzeige in Streamlit)."""
    nachricht = f"Urteilsauszüge:\n\n{kontext_bauen(treffer)}\n\nFrage: {frage}"
    for stueck in ollama.chat(
        model=config.LLM_MODELL,
        messages=[{"role": "system", "content": PROMPT_ANTWORT},
                  {"role": "user", "content": nachricht}],
        options={"temperature": 0.2, "num_ctx": config.LLM_KONTEXT},
        stream=True,
    ):
        yield stueck["message"]["content"]


def urteil_verschlagworten(text: str) -> tuple[list[str], str]:
    daten = _json_chat(PROMPT_VERSCHLAGWORTUNG, text[:6000])  # Anfang reicht: Tenor + Leitsätze
    worte = [str(w).strip() for w in daten.get("schlagworte", []) if str(w).strip()]
    return worte[:8], str(daten.get("kurzfassung", "")).strip()
