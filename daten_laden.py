"""Schritt 1: Urteile von Hugging Face laden und in SQLite speichern.

Aufruf:  python daten_laden.py

Welche Urteile geladen werden, steht in config.py (DATENAUSWAHL):
  "bedeutend"  - die bedeutendsten Urteile aus dem Vollbestand (siehe auswahl.py)
  "stichprobe" - eine fertige Zufallsstichprobe

Ergebnis: eine SQLite-Datenbank (Pfad siehe config.py) mit drei Tabellen
  - urteile      : eine Zeile pro Urteil (Gericht, Datum, Aktenzeichen, Text, Bedeutung ...)
  - urteile_fts  : Volltextindex für die Schlagwortsuche (SQLite FTS5)
  - zitierungen  : welches Urteil der Datenbank zitiert welches andere
"""
import sqlite3

import config

# Spalten, die nach der ersten Version dazugekommen sind (werden bei alten Datenbanken ergänzt)
NEUE_SPALTEN = {
    "instanz": "TEXT DEFAULT ''",          # Oberstes Gericht / Obergericht / Eingangsgericht
    "zitiert_von": "INTEGER DEFAULT 0",    # von so vielen Urteilen im Vollbestand zitiert
    "bedeutung": "REAL DEFAULT 0",         # 0 bis 1: Rang nach Bedeutungs-Score in dieser Datenbank
    "auswahl_grund": "TEXT DEFAULT ''",    # über welches Kontingent das Urteil ausgewählt wurde
}


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

        -- Zitierungen zwischen Urteilen dieser Datenbank (für den Hinweis auf Rechtsprechungsänderungen)
        CREATE TABLE IF NOT EXISTS zitierungen (
            von_id   INTEGER,
            nach_id  INTEGER,
            PRIMARY KEY (von_id, nach_id)
        );
        CREATE INDEX IF NOT EXISTS zitierungen_nach ON zitierungen (nach_id);

        -- Welche Normen zitiert ein Urteil? (Zitationsgraph, Kanten Urteil -> Norm; gesetze_laden.py)
        CREATE TABLE IF NOT EXISTS norm_zitierungen (
            urteil_id  INTEGER,
            gesetz     TEXT,                -- Abkürzung, z. B. "AGG"
            kurzform   TEXT,                -- Adresse bei gesetze-im-internet.de, z. B. "agg"
            paragraph  TEXT,                -- z. B. "§ 6" oder "Art. 3"
            anzahl     INTEGER,             -- wie oft das Urteil die Norm zitiert
            PRIMARY KEY (urteil_id, kurzform, paragraph)
        );

        -- Gesetzestexte von gesetze-im-internet.de (gesetze_laden.py)
        CREATE TABLE IF NOT EXISTS gesetze (
            kurzform   TEXT PRIMARY KEY,
            gesetz     TEXT,                -- amtliche Abkürzung, z. B. "AGG"
            titel      TEXT,
            stand      TEXT,                -- z. B. "Zuletzt geändert durch Art. 15 G v. 22.12.2023 I Nr. 414"
            geaendert  TEXT,                -- "Last-Modified" der Datei, für die Aktualisierung
            geladen_am TEXT
        );
        -- Alle Schreibweisen eines Gesetzes ("SGB II", "SGB 2") -> kurzform
        CREATE TABLE IF NOT EXISTS gesetz_namen (
            name      TEXT PRIMARY KEY,
            kurzform  TEXT
        );
        CREATE TABLE IF NOT EXISTS normen (
            id         INTEGER PRIMARY KEY,
            kurzform   TEXT,
            gesetz     TEXT,
            art        TEXT,                -- "§" oder "Art."
            nr         TEXT,                -- "6", "573a"
            titel      TEXT,
            text       TEXT,                -- Absätze und Aufzählungen je auf eigener Zeile
            url        TEXT
        );
        CREATE INDEX IF NOT EXISTS normen_nr ON normen (kurzform, nr);
        CREATE VIRTUAL TABLE IF NOT EXISTS normen_fts USING fts5(
            gesetz, nr, titel, text,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    vorhanden = {zeile[1] for zeile in db.execute("PRAGMA table_info(urteile)")}
    for spalte, typ in NEUE_SPALTEN.items():
        if spalte not in vorhanden:
            db.execute(f"ALTER TABLE urteile ADD COLUMN {spalte} {typ}")


def urteile_speichern(db: sqlite3.Connection, urteile) -> int:
    """Schreibt Urteile (Liste von Dictionaries) in die Datenbank.

    Gibt zurück, wie viele Urteile neu hinzugekommen sind.
    """
    from auswahl import gerichtsbarkeit, instanz

    neu = 0
    for u in urteile:
        text = u.get("markdown_content") or ""
        if len(text) < 200:          # leere oder kaputte Einträge überspringen
            continue
        gericht = u.get("court") or {}
        name = gericht.get("name", "")
        werte = (
            u["id"],
            u.get("slug", ""),
            name,
            gerichtsbarkeit(gericht.get("jurisdiction"), name),
            str(u.get("date", ""))[:10],
            u.get("file_number", ""),
            u.get("type", ""),
            u.get("ecli", ""),
            text,
            u.get("instanz") or instanz(gericht.get("level_of_appeal"), name),
            u.get("zitiert_von", 0),
            u.get("bedeutung", 0.0),
            u.get("auswahl_grund", ""),
        )
        cursor = db.execute(
            "INSERT OR IGNORE INTO urteile "
            "(id, slug, gericht, gerichtsbarkeit, datum, aktenzeichen, typ, ecli, text, "
            " instanz, zitiert_von, bedeutung, auswahl_grund) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


def zitierungen_speichern(db: sqlite3.Connection, zitierungen) -> None:
    db.executemany("INSERT OR IGNORE INTO zitierungen (von_id, nach_id) VALUES (?, ?)",
                   zitierungen[["von_id", "nach_id"]].itertuples(index=False, name=None))
    db.commit()


def main() -> None:
    config.DATEN_ORDNER.mkdir(exist_ok=True)
    db = sqlite3.connect(config.SQLITE_PFAD)
    tabellen_anlegen(db)

    if config.DATENAUSWAHL == "bedeutend":
        import auswahl
        print(f"Wähle die {config.AUSWAHL_GESAMT:,} bedeutendsten Urteile aus dem Vollbestand "
              f"({config.VOLLBESTAND}) ...".replace(",", "."))
        urteile, zitierungen = auswahl.laden()
        print(f"Schreibe in {config.SQLITE_PFAD} ...")
        neu = urteile_speichern(db, urteile)
        zitierungen_speichern(db, zitierungen)
        print(f"  {len(zitierungen):,} Zitierungen zwischen den ausgewählten Urteilen".replace(",", "."))
    else:
        # Erst hier importieren: die Bibliothek ist groß und wird nur in diesem Schritt gebraucht.
        from datasets import load_dataset
        print(f"Lade {config.DATENSATZ} ({config.DATENSATZ_VERSION}) ...")
        daten = load_dataset(config.DATENSATZ, name=config.DATENSATZ_VERSION)
        teil = daten[list(daten.keys())[0]]      # der Datensatz hat nur einen Teil ("train")
        print(f"{len(teil)} Urteile heruntergeladen. Schreibe in {config.SQLITE_PFAD} ...")
        neu = urteile_speichern(db, teil)

    gesamt = db.execute("SELECT COUNT(*) FROM urteile").fetchone()[0]
    print(f"Fertig: {neu} neue Urteile, {gesamt} insgesamt in der Datenbank.")


if __name__ == "__main__":
    main()
