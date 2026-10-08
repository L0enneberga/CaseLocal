"""Schritt 2: Urteile in Abschnitte teilen, Embeddings berechnen, in ChromaDB speichern.

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


def sammlung_oeffnen():
    """Öffnet (oder erstellt) die Vektor-Datenbank im Ordner daten/chroma."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_PFAD))
    # "cosine": Ähnlichkeit wird über den Winkel zwischen den Zahlenreihen gemessen
    return client.get_or_create_collection(name="urteile", metadata={"hnsw:space": "cosine"})


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
        abschnitte = in_abschnitte_teilen(text)
        # Geprüft wird der LETZTE Abschnitt: Wurde mitten in einem Urteil abgebrochen,
        # fehlt er noch, und das Urteil wird beim nächsten Start vervollständigt.
        if sammlung.get(ids=[f"{urteil_id}-{len(abschnitte) - 1}"])["ids"]:
            continue                                   # schon vollständig verarbeitet

        for i in range(0, len(abschnitte), config.EMBED_BATCH):
            paket = abschnitte[i : i + config.EMBED_BATCH]
            sammlung.upsert(                           # upsert: vorhandene Abschnitte überschreiben
                ids=[f"{urteil_id}-{i + k}" for k in range(len(paket))],
                embeddings=embeddings_berechnen(paket),
                documents=paket,
                metadatas=[
                    {"urteil_id": urteil_id, "gericht": gericht,
                     "datum": datum, "aktenzeichen": aktenzeichen}
                    for _ in paket
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
