"""Die Akte: gespeicherte Recherchen mit eigener Notiz.

Eine Akte ist ein Name (z. B. "Mandat Müller, Mietminderung"), unter dem man Antworten
aus der App ablegt. Man legt sie vorher an und wählt sie dann für jede Recherche aus. Gespeichert wird alles in einer eigenen SQLite-Datei (config.NOTIZEN_DB),
getrennt von der Urteilsdatenbank: Ein Neuaufbau des Suchindex löscht so keine Notizen.

  tabellen_anlegen   - legt die Tabellen an (einmal beim Start der App)
  akte_anlegen       - legt eine neue, noch leere Akte an
  eintrag_speichern  - legt eine Antwort mit Quellen in einer Akte ab
  eintraege_laden    - alle Einträge, neueste zuerst (optional nur einer Akte)
  akten_auflisten    - die Namen aller Akten, auch der noch leeren
  notiz_aendern      - ändert die Notiz eines Eintrags
  eintrag_loeschen   - löscht einen Eintrag
  quelle_text        - eine Quelle als Zeile, z. B. "[2] Bundesgerichtshof, 18.03.2015, Az. VIII ZR 185/14"

Alle Funktionen nehmen einen optionalen Pfad, damit die Tests mit einer
Wegwerf-Datenbank arbeiten können statt mit der echten.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import config
from llm import datum_deutsch

TABELLEN = """
-- Eigene Tabelle für die Namen: Eine neu angelegte Akte gibt es so schon, bevor etwas darin liegt.
CREATE TABLE IF NOT EXISTS akten (
    name         TEXT PRIMARY KEY,   -- PRIMARY KEY: jeder Name nur einmal
    angelegt_am  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eintraege (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    erstellt_am  TEXT NOT NULL,      -- Zeitpunkt im ISO-Format, z. B. 2026-10-17T14:44:00
    akte         TEXT NOT NULL,      -- Name der Akte
    frage        TEXT NOT NULL,
    antwort      TEXT NOT NULL,
    quellen      TEXT NOT NULL,      -- JSON-Liste, siehe quellen_schnappschuss()
    modell       TEXT,               -- verwendetes Sprachmodell, für spätere Vergleiche
    notiz        TEXT DEFAULT ''
);
"""

# Legt eine Akte an, falls es sie noch nicht gibt (gebraucht beim Anlegen und beim Speichern).
AKTE_EINTRAGEN = "INSERT OR IGNORE INTO akten (name, angelegt_am) VALUES (?, ?)"

# Diese Angaben eines Treffers kommen in die Akte. "nr" braucht man, um [2] in der
# gespeicherten Antwort dem richtigen Urteil zuzuordnen, "slug" für den Link zum Volltext.
QUELLEN_FELDER = ("id", "nr", "gericht", "datum", "aktenzeichen", "slug")


@contextmanager
def _verbindung(pfad: Path):
    """Öffnet die Datenbank, speichert am Ende und schließt sie wieder.

    Warum nicht einfach "with sqlite3.connect(...)": Das speichert zwar (commit) bzw.
    verwirft bei einem Fehler (rollback), schließt die Verbindung aber NICHT. Unter
    Windows bliebe die Datei dann gesperrt und ließe sich z. B. nicht umbenennen.
    """
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)   # falls der Ordner daten/ fehlt
    db = sqlite3.connect(pfad)
    db.row_factory = sqlite3.Row                           # Zeilen wie Dictionaries ansprechen
    try:
        with db:                                           # commit bei Erfolg, rollback bei Fehler
            yield db
    finally:
        db.close()


def tabellen_anlegen(pfad: Path = config.NOTIZEN_DB) -> None:
    """Legt die Tabellen an, falls sie fehlen. Ein zweiter Aufruf schadet nicht (IF NOT EXISTS)."""
    with _verbindung(pfad) as db:
        db.executescript(TABELLEN)


def _jetzt() -> str:
    """Der aktuelle Zeitpunkt im ISO-Format, z. B. "2026-10-17T14:44:00"."""
    return datetime.now().isoformat(timespec="seconds")


def _name_pruefen(akte: str) -> str:
    """Entfernt Leerzeichen am Anfang und Ende und lehnt leere Namen ab."""
    akte = akte.strip()
    if not akte:
        raise ValueError("Die Akte braucht einen Namen.")
    return akte


def akte_anlegen(name: str, pfad: Path = config.NOTIZEN_DB) -> str:
    """Legt eine neue Akte an und gibt ihren bereinigten Namen zurück.

    Gibt es die Akte schon, passiert nichts (INSERT OR IGNORE): Wer denselben Namen
    zweimal eingibt, landet einfach in der bestehenden Akte.
    """
    name = _name_pruefen(name)
    with _verbindung(pfad) as db:
        db.execute(AKTE_EINTRAGEN, (name, _jetzt()))
    return name


def quellen_schnappschuss(treffer: list[dict]) -> list[dict]:
    """Hält die Angaben der Quellen fest, so wie sie gerade in der Datenbank stehen.

    Eine Kopie statt nur der IDs: So bleibt ein Eintrag lesbar, auch wenn der Suchindex
    später mit anderen Urteilen neu gebaut wird.
    """
    return [{feld: t.get(feld) for feld in QUELLEN_FELDER} for t in treffer]


def quelle_text(q: dict) -> str:
    """Eine gespeicherte Quelle als Zeile: "[2] Bundesgerichtshof, 18.03.2015, Az. VIII ZR 185/14"."""
    teile = [q.get("gericht") or "Gericht unbekannt"]
    if q.get("datum"):
        teile.append(datum_deutsch(q["datum"]))
    teile.append(f"Az. {q.get('aktenzeichen') or 'unbekannt'}")
    nummer = f"[{q['nr']}] " if q.get("nr") else ""
    return nummer + ", ".join(teile)


def zeitpunkt_deutsch(iso: str) -> str:
    """"2026-10-17T14:44:00" -> "17.10.2026, 14:44" """
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y, %H:%M")
    except ValueError:                                 # unbekanntes Format: unverändert zeigen
        return iso


def eintrag_speichern(akte: str, frage: str, antwort: str, quellen: list[dict],
                      modell: str | None = None, notiz: str = "",
                      pfad: Path = config.NOTIZEN_DB) -> int:
    """Legt eine Antwort in einer Akte ab und gibt die Nummer (id) des neuen Eintrags zurück.

    Gibt es die Akte noch nicht, wird sie mit angelegt.
    """
    akte = _name_pruefen(akte)
    erstellt_am = _jetzt()
    with _verbindung(pfad) as db:
        db.execute(AKTE_EINTRAGEN, (akte, erstellt_am))
        cursor = db.execute(
            "INSERT INTO eintraege (erstellt_am, akte, frage, antwort, quellen, modell, notiz) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            # ensure_ascii=False: Umlaute bleiben in der Datenbank lesbar ("Gründe" statt "Gründe")
            (erstellt_am, akte, frage, antwort, json.dumps(quellen, ensure_ascii=False), modell, notiz),
        )
        return cursor.lastrowid


def eintraege_laden(akte: str | None = None, pfad: Path = config.NOTIZEN_DB) -> list[dict]:
    """Alle Einträge, neueste zuerst. Mit akte nur die Einträge dieser Akte.

    Jeder Eintrag ist ein Dictionary mit den Spalten der Tabelle; "quellen" ist
    wieder eine Liste (aus dem JSON-Text zurückverwandelt).
    """
    sql = "SELECT * FROM eintraege"
    werte = []
    if akte is not None:
        sql += " WHERE akte = ?"
        werte.append(akte)
    # id als zweites Kriterium: Zwei Einträge aus derselben Sekunde haben denselben Zeitpunkt.
    sql += " ORDER BY erstellt_am DESC, id DESC"
    with _verbindung(pfad) as db:
        zeilen = db.execute(sql, werte).fetchall()
    eintraege = []
    for zeile in zeilen:
        eintrag = dict(zeile)
        eintrag["quellen"] = json.loads(eintrag["quellen"])
        eintraege.append(eintrag)
    return eintraege


def akten_auflisten(pfad: Path = config.NOTIZEN_DB) -> list[str]:
    """Die Namen aller Akten, alphabetisch (COLLATE NOCASE: "arbeitsrecht" nicht hinter "Mietrecht")."""
    with _verbindung(pfad) as db:
        zeilen = db.execute("SELECT name FROM akten ORDER BY name COLLATE NOCASE").fetchall()
    return [z["name"] for z in zeilen]


def notiz_aendern(eintrag_id: int, notiz: str, pfad: Path = config.NOTIZEN_DB) -> None:
    """Ersetzt die Notiz eines Eintrags."""
    with _verbindung(pfad) as db:
        db.execute("UPDATE eintraege SET notiz = ? WHERE id = ?", (notiz, eintrag_id))


def eintrag_loeschen(eintrag_id: int, pfad: Path = config.NOTIZEN_DB) -> None:
    """Löscht einen Eintrag endgültig."""
    with _verbindung(pfad) as db:
        db.execute("DELETE FROM eintraege WHERE id = ?", (eintrag_id,))
