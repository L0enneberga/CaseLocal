"""Schritt 1: Urteile von Hugging Face laden und in SQLite speichern.

Aufruf:  python daten_laden.py

Ergebnis: daten/urteile.db mit zwei Tabellen
  - urteile      : eine Zeile pro Urteil (Gericht, Datum, Aktenzeichen, Text ...)
  - urteile_fts  : Volltextindex für die Schlagwortsuche (SQLite FTS5)
"""
import sqlite3

import config


def tabellen_anlegen(db: sqlite3.Connection) -> None:
    """Legt die Tabellen an, falls es sie noch nicht gibt."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS urteile (
            id            INTEGER PRIMARY KEY,
            slug          TEXT,
            gericht       TEXT,
            gerichtsbarkeit TEXT,
            datum         TEXT,
            aktenzeichen  TEXT,
            typ           TEXT,
            ecli          TEXT,
            text          TEXT,
            schlagworte   TEXT DEFAULT '',
            kurzfassung   TEXT DEFAULT ''
        );

        -- Volltextindex. rowid = id des Urteils, damit beide Tabellen zusammenpassen.
        -- remove_diacritics: "Kuendigung" und "Kündigung" werden gleich behandelt.
        CREATE VIRTUAL TABLE IF NOT EXISTS urteile_fts USING fts5(
            gericht, aktenzeichen, schlagworte, text,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )


def urteile_speichern(db: sqlite3.Connection, urteile) -> int:
    """Schreibt Urteile (Liste von Dictionaries) in die Datenbank.

    Gibt zurück, wie viele Urteile neu hinzugekommen sind.
    """
    neu = 0
    for u in urteile:
        text = u.get("markdown_content") or ""
        if len(text) < 200:          # leere oder kaputte Einträge überspringen
            continue
        gericht = u.get("court") or {}
        werte = (
            u["id"],
            u.get("slug", ""),
            gericht.get("name", ""),
            gericht.get("jurisdiction", ""),
            str(u.get("date", ""))[:10],
            u.get("file_number", ""),
            u.get("type", ""),
            u.get("ecli", ""),
            text,
        )
        cursor = db.execute(
            "INSERT OR IGNORE INTO urteile "
            "(id, slug, gericht, gerichtsbarkeit, datum, aktenzeichen, typ, ecli, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            werte,
        )
        if cursor.rowcount == 1:     # nur wenn das Urteil wirklich neu war
            db.execute(
                "INSERT INTO urteile_fts (rowid, gericht, aktenzeichen, schlagworte, text) "
                "VALUES (?, ?, ?, '', ?)",
                (u["id"], werte[2], werte[5], text),
            )
            neu += 1
    db.commit()
    return neu


def main() -> None:
    # Erst hier importieren: die Bibliothek ist groß und wird nur in diesem Schritt gebraucht.
    from datasets import load_dataset

    config.DATEN_ORDNER.mkdir(exist_ok=True)
    print(f"Lade {config.DATENSATZ} ({config.DATENSATZ_VERSION}) ...")
    daten = load_dataset(config.DATENSATZ, name=config.DATENSATZ_VERSION)
    teil = daten[list(daten.keys())[0]]      # der Datensatz hat nur einen Teil ("train")
    print(f"{len(teil)} Urteile heruntergeladen. Schreibe in {config.SQLITE_PFAD} ...")

    db = sqlite3.connect(config.SQLITE_PFAD)
    tabellen_anlegen(db)
    neu = urteile_speichern(db, teil)
    gesamt = db.execute("SELECT COUNT(*) FROM urteile").fetchone()[0]
    print(f"Fertig: {neu} neue Urteile, {gesamt} insgesamt in der Datenbank.")


if __name__ == "__main__":
    main()
