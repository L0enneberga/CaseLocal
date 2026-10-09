"""Misst die Qualität der Recherche an festen Testfragen (tests/goldfragen.json).

Aufruf:  python bewertung.py --name vorher
         python bewertung.py --name nachher --nur 3      (nur die ersten 3 Fragen)
         python bewertung.py --name denken --denken-pruefung ja   (Denkmodus in den Prüfschritten)
         python bewertung.py --name ohne --ohne-gesetzestexte     (kein Normtext im Material)

Jede Frage läuft durch dieselbe Kette wie in der App (mit gründlicher Analyse,
Rechtsprechungsänderungen und Zitatprüfung). Gemessen wird pro Frage:
  - Rang des erwarteten Urteils unter den Treffern (Top 5?)
  - ob die Antwort das erwartete Urteil zitiert
  - falsche Daten oder Aktenzeichen in der Antwort (Vergleich mit der Datenbank)
  - Ergebnis der Zitatprüfung und Dauer

Die Ergebnisse landen mit den vollständigen Antworten in daten/bewertung/<name>.json,
damit man sie später nachlesen und vergleichen kann. Die erwartete Kernaussage
steht dort zum manuellen Abgleich; sie wird nicht automatisch bewertet.
"""
import argparse
import json
import time
from pathlib import Path

import abweichung
import belege
import config
import ergaenzung
import llm
import normen
import suche

GOLDFRAGEN = Path(__file__).parent / "tests" / "goldfragen.json"
AUSGABE = Path(config.DATEN_ORDNER) / "bewertung"


def frage_bewerten(gold: dict) -> dict:
    """Führt eine Recherche wie in der App aus und misst das Ergebnis."""
    start = time.time()
    frage = gold["frage"]
    treffer = suche.hybride_suche(frage, llm.frage_zu_schlagworten(frage), 10)
    abweichung.alle_pruefen(treffer)
    auswahl = treffer[: config.KI_TREFFER]
    pruefungen = {t["nr"]: llm.urteil_pruefen(frage, t) for t in auswahl}
    roh = "".join(llm.antwort_streamen(frage, auswahl, pruefungen))
    ergaenzt = ergaenzung.antwort_ergaenzen(roh, treffer, pruefungen)
    antwort = ergaenzt["antwort"]
    aussagen = belege.pruefen(antwort, auswahl)

    erwartet = next((t for t in treffer if t["aktenzeichen"] == gold["aktenzeichen"]), None)
    zitiert = {n for a in belege.aussagen_finden(antwort) for n in a["quellen"]}
    return {
        "frage": frage,
        "aktenzeichen": gold["aktenzeichen"],
        "kernaussage": gold["kernaussage"],
        "rang": erwartet["nr"] if erwartet else None,
        "zitiert": bool(erwartet) and erwartet["nr"] in zitiert,
        "metadaten_fehler": [{k: a[k] for k in ("art", "gefunden", "richtig", "nr")}
                             for a in belege.metadaten_abweichungen(antwort, treffer)],
        "metadaten_fehler_roh": len(belege.metadaten_abweichungen(belege.rn_klammern(roh), treffer)),
        "korrekturen": ergaenzt["korrekturen"],
        "rechtsprechungsaenderungen": [
            {"aendernd": [a["aktenzeichen"] for a in g["aendernd"]], "nr": g["aendernd"][0].get("nr"),
             "dort_zitiert": [b["treffer"]["aktenzeichen"] for b in g["betroffen"]]}
            for g in ergaenzt["entwicklung"]],
        "unionsrecht": [z for z in antwort.split("\n") if z.startswith("> - [") and "Unionsrecht" not in z
                        and any(art in z for art, _ in normen.UNIONSRECHT)],
        "zitatpruefung": belege.zusammenfassung(aussagen),
        "dauer": round(time.time() - start),
        "treffer": [f"[{t['nr']}] {t['gericht']} {t['datum']} {t['aktenzeichen']}" for t in treffer],
        "relevant": [n for n, p in pruefungen.items() if p["relevant"]],
        "antwort_roh": roh,
        "antwort": antwort,
        "aussagen": aussagen,
    }


def zusammenfassen(ergebnisse: list[dict]) -> dict:
    """Kennzahlen über alle Fragen."""
    zaehler = {stufe: sum(e["zitatpruefung"].get(stufe, 0) for e in ergebnisse)
               for stufe in ergebnisse[0]["zitatpruefung"]} if ergebnisse else {}
    geprueft = sum(zaehler.get(s, 0) for s in belege.STUFEN)
    return {
        "fragen": len(ergebnisse),
        "top5": sum(1 for e in ergebnisse if e["rang"] and e["rang"] <= 5),
        "zitiert": sum(e["zitiert"] for e in ergebnisse),
        "metadaten_fehler": sum(len(e["metadaten_fehler"]) for e in ergebnisse),
        "zitatpruefung": zaehler,
        "gestuetzt_anteil": round(zaehler.get("ja", 0) / geprueft, 3) if geprueft else None,
        "dauer_mittel": round(sum(e["dauer"] for e in ergebnisse) / len(ergebnisse)) if ergebnisse else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--name", required=True, help="Name des Durchlaufs, z. B. vorher")
    parser.add_argument("--nur", type=int, help="nur die ersten N Fragen")
    parser.add_argument("--denken-pruefung", choices=["ja", "nein"],
                        help="Denkmodus in den Prüfschritten (überschreibt config.DENKEN_PRUEFUNG)")
    parser.add_argument("--ohne-gesetzestexte", action="store_true",
                        help="keine Normtexte im Material (setzt config.NORMEN_MAX = 0)")
    argumente = parser.parse_args()
    if argumente.ohne_gesetzestexte:
        config.NORMEN_MAX = 0
    if argumente.denken_pruefung:
        config.DENKEN_PRUEFUNG = argumente.denken_pruefung == "ja"

    goldfragen = json.loads(GOLDFRAGEN.read_text(encoding="utf-8"))[: argumente.nur]
    ergebnisse = []
    for i, gold in enumerate(goldfragen, 1):
        e = frage_bewerten(gold)
        ergebnisse.append(e)
        print(f"{i:2}/{len(goldfragen)} Rang {e['rang'] or '-':>2} · zitiert {'ja ' if e['zitiert'] else 'nein'}"
              f" · Metadatenfehler {len(e['metadaten_fehler'])} · {e['zitatpruefung']} · {e['dauer']} s"
              f" · {gold['aktenzeichen']}", flush=True)

    gesamt = zusammenfassen(ergebnisse)
    gesamt.update(modell=config.LLM_MODELL, denken_pruefung=config.DENKEN_PRUEFUNG, normen_max=config.NORMEN_MAX)
    AUSGABE.mkdir(parents=True, exist_ok=True)
    datei = AUSGABE / f"{argumente.name}.json"
    datei.write_text(json.dumps({"gesamt": gesamt, "fragen": ergebnisse}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(json.dumps(gesamt, ensure_ascii=False))
    print(f"Gespeichert: {datei}")


if __name__ == "__main__":
    main()
