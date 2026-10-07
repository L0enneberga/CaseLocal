"""Schritt 3 (optional): Das LLM vergibt Schlagworte und eine Kurzfassung pro Urteil.

Aufruf:  python schlagworte.py            (verarbeitet 100 Urteile)
         python schlagworte.py --anzahl 500

Dauert pro Urteil einige Sekunden. Kann abgebrochen und neu gestartet
werden: bereits verschlagwortete Urteile werden übersprungen.
"""
import argparse
import sqlite3

import config
import llm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anzahl", type=int, default=100, help="wie viele Urteile verarbeiten")
    anzahl = parser.parse_args().anzahl

    db = sqlite3.connect(config.SQLITE_PFAD)
    offen = db.execute(
        "SELECT id, aktenzeichen, text FROM urteile WHERE schlagworte = '' LIMIT ?", (anzahl,)
    ).fetchall()
    print(f"Verschlagworte {len(offen)} Urteile mit {config.LLM_MODELL} ...")

    for nr, (urteil_id, aktenzeichen, text) in enumerate(offen, 1):
        worte, kurz = llm.urteil_verschlagworten(text)
        liste = ", ".join(worte)
        db.execute("UPDATE urteile SET schlagworte = ?, kurzfassung = ? WHERE id = ?",
                   (liste, kurz, urteil_id))
        db.execute("UPDATE urteile_fts SET schlagworte = ? WHERE rowid = ?", (liste, urteil_id))
        db.commit()                                     # nach jedem Urteil speichern
        print(f"  [{nr}/{len(offen)}] {aktenzeichen}: {liste}")

    print("Fertig.")


if __name__ == "__main__":
    main()
