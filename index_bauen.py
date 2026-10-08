"""Schritt 2: Urteile in Abschnitte teilen, Embeddings berechnen, in ChromaDB speichern.

Zerlegt wird entlang der Gliederung des Urteils (Leitsatz, Tenor, Tatbestand,
Gründe). Jeder Abschnitt merkt sich, aus welchem Teil er stammt und welche
Randnummern er enthält. So kann die Suche Gründe höher gewichten und die
Antwort mit Randnummern zitieren.

Aufruf:  python index_bauen.py

Voraussetzung: Ollama läuft und das Embedding-Modell ist geladen
               (ollama pull bge-m3).
Das Skript kann jederzeit abgebrochen und neu gestartet werden:
bereits verarbeitete Urteile werden übersprungen.
"""
import sqlite3
import time

import chromadb
import ollama

import config
import gliederung


def in_abschnitte_teilen(text: str) -> list[str]:
    """Teilt einen langen Text in Abschnitte von ca. CHUNK_ZEICHEN Zeichen.

    Geschnitten wird bevorzugt an Absatzgrenzen. Zwischen zwei Abschnitten
    wiederholen sich CHUNK_UEBERLAPPUNG Zeichen, damit kein Gedanke genau
    an der Schnittkante verloren geht.
    """
    groesse, ueberlappung = config.CHUNK_ZEICHEN, config.CHUNK_UEBERLAPPUNG
    absaetze = [a.strip() for a in text.split("\n\n") if a.strip()]
    abschnitte: list[str] = []
    aktuell = ""
    for absatz in absaetze:
        if aktuell and len(aktuell) + len(absatz) > groesse:
            abschnitte.append(aktuell)
            aktuell = aktuell[-ueberlappung:]          # Überlappung mitnehmen
        aktuell = (aktuell + "\n\n" + absatz).strip()
        while len(aktuell) > groesse * 1.5:            # einzelner Riesen-Absatz: hart schneiden
            abschnitte.append(aktuell[:groesse])
            aktuell = aktuell[groesse - ueberlappung:]
    if aktuell:
        abschnitte.append(aktuell)
    return abschnitte[: config.MAX_CHUNKS_PRO_URTEIL]


# Reihenfolge beim Kürzen sehr langer Urteile: zuerst fallen Teile mit hoher Zahl weg.
VORRANG = {"Leitsatz": 0, "Tenor": 0, "Gründe": 1, "Tatbestand": 2,
           "Verfahrensgang": 3, "Sonstiges": 3}


def abschnitte_bilden(text: str) -> list[dict]:
    """Zerlegt ein Urteil Teil für Teil in Abschnitte, jeweils mit Teil und Randnummern.

    Ergebnis z. B.: [{"text": "...", "teil": "Gründe", "rn_von": 15, "rn_bis": 17}, ...]
    Bei sehr langen Urteilen werden zuerst Tatbestand und Sonstiges gekürzt,
    damit Tenor und Gründe vollständig im Index landen.
    """
    abschnitte = []
    for teil, inhalt in gliederung.teile_erkennen(text):
        letzte_rn = 0
        for stueck in in_abschnitte_teilen(inhalt):
            rn = gliederung.randnummern(stueck)
            # Beginnt der Abschnitt mitten in einem Absatz, gehört sein Anfang
            # noch zur Randnummer, mit der der vorige Abschnitt endete.
            if letzte_rn and not gliederung.RANDNUMMER.match(stueck):
                rn = [letzte_rn] + rn
            if rn:
                letzte_rn = rn[-1]
            abschnitte.append({"text": stueck, "teil": teil,
                               "rn_von": rn[0] if rn else 0, "rn_bis": rn[-1] if rn else 0})
    if len(abschnitte) > config.MAX_CHUNKS_PRO_URTEIL:
        wichtigste = sorted(range(len(abschnitte)),
                            key=lambda i: (VORRANG[abschnitte[i]["teil"]], i))
        behalten = sorted(wichtigste[: config.MAX_CHUNKS_PRO_URTEIL])   # Reihenfolge wie im Urteil
        abschnitte = [abschnitte[i] for i in behalten]
    return abschnitte


def sammlung_oeffnen():
    """Öffnet (oder erstellt) die Vektor-Datenbank im Ordner daten/chroma."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_PFAD))
    # "cosine": Ähnlichkeit wird über den Winkel zwischen den Zahlenreihen gemessen
    return client.get_or_create_collection(name=config.CHROMA_SAMMLUNG,
                                           metadata={"hnsw:space": "cosine"})


def embeddings_berechnen(texte: list[str]) -> list[list[float]]:
    """Schickt Texte an das Embedding-Modell und bekommt Zahlenreihen zurück."""
    antwort = ollama.embed(model=config.EMBED_MODELL, input=texte)
    return antwort["embeddings"]


def main() -> None:
    db = sqlite3.connect(config.SQLITE_PFAD)
    urteile = db.execute(
        "SELECT id, gericht, datum, aktenzeichen, text FROM urteile ORDER BY id"
    ).fetchall()
    sammlung = sammlung_oeffnen()
    print(f"{len(urteile)} Urteile in der Datenbank, {sammlung.count()} Abschnitte schon im Index.")

    start = time.time()
    for nr, (urteil_id, gericht, datum, aktenzeichen, text) in enumerate(urteile, 1):
        abschnitte = abschnitte_bilden(text)
        # Geprüft wird der LETZTE Abschnitt: Wurde mitten in einem Urteil abgebrochen,
        # fehlt er noch, und das Urteil wird beim nächsten Start vervollständigt.
        if sammlung.get(ids=[f"{urteil_id}-{len(abschnitte) - 1}"])["ids"]:
            continue                                   # schon vollständig verarbeitet

        for i in range(0, len(abschnitte), config.EMBED_BATCH):
            paket = abschnitte[i : i + config.EMBED_BATCH]
            sammlung.upsert(                           # upsert: vorhandene Abschnitte überschreiben
                ids=[f"{urteil_id}-{i + k}" for k in range(len(paket))],
                embeddings=embeddings_berechnen([a["text"] for a in paket]),
                documents=[a["text"] for a in paket],
                metadatas=[
                    {"urteil_id": urteil_id, "gericht": gericht or "", "datum": datum or "",
                     "aktenzeichen": aktenzeichen or "", "teil": a["teil"],
                     "rn_von": a["rn_von"], "rn_bis": a["rn_bis"]}
                    for a in paket
                ],
            )

        if nr % 25 == 0 or nr == len(urteile):
            minuten = (time.time() - start) / 60
            print(f"  {nr}/{len(urteile)} Urteile verarbeitet ({minuten:.1f} min)")

    print(f"Fertig. Der Index enthält jetzt {sammlung.count()} Abschnitte.")


if __name__ == "__main__":
    try:
        main()
    except ConnectionError:
        print("Ollama ist nicht erreichbar. Läuft die Ollama-App? (Symbol unten rechts in der Taskleiste)")
        raise SystemExit(1)                            # Fehlercode, damit setup.bat abbricht
