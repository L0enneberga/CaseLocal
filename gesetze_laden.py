"""Lädt die Wortlaute der meistzitierten Bundesgesetze von gesetze-im-internet.de.

Aufruf:  python gesetze_laden.py                  (erneuter Aufruf lädt nur geänderte Gesetze)
         python gesetze_laden.py --ohne-normsuche  (ohne Embeddings für die Normsuche)

Ablauf:
  1. Welche Normen zitieren die Urteile der Datenbank? Das steht im Zitationsgraphen von
     Open Legal Data (Kanten Urteil -> Norm). Weil der Graph manche Schreibweisen kaum erkennt
     (z. B. "§ 31a SGB II"), werden die Normzitate zusätzlich mit dem Muster aus normen.py in
     den Urteilstexten gezählt. Beides wird einmalig in die Tabelle norm_zitierungen geladen.
  2. Die GESETZE_ANZAHL meistzitierten Gesetze bestimmen.
  3. Je Gesetz die XML-Datei von gesetze-im-internet.de laden - aber nur, wenn sie sich seit
     dem letzten Lauf geändert hat ("Last-Modified") - und jeden Paragraphen mit Stand speichern.
  4. Normsuche: je Paragraph ein Embedding (ChromaDB-Sammlung config.CHROMA_NORMEN). Damit findet
     die App mögliche Normen, wenn keine Rechtsprechung zur Frage passt.

Das XML-Format (gii-norm.dtd), vereinfacht:
    <dokumente>
      <norm><metadaten><jurabk>AGG</jurabk> ... <standangabe>...</standangabe></metadaten></norm>
      <norm><metadaten><jurabk>AGG</jurabk><enbez>§ 6</enbez><titel>Persönlicher ...</titel></metadaten>
            <textdaten><text><Content><P>(1) Beschäftigte ... <DL><DT>1.</DT><DD>...</DD></DL></P>
    </dokumente>

Gesetze sind nach § 5 UrhG gemeinfrei. Die Texte landen wie die Urteile nur in daten/,
nicht im GitHub-Repository.
"""
import argparse
import io
import re
import sqlite3
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from contextlib import closing
from datetime import date

import config
import daten_laden
import normen

GII = "https://www.gesetze-im-internet.de"
ENBEZ = re.compile(r"^(§|Art)\.?\s*(\d+[a-z]*)\b")
ROEMISCH = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
            "XI": 11, "XII": 12, "XIII": 13, "XIV": 14}


def _arabisch(name: str) -> str:
    """"SGB II" -> "SGB 2" """
    teile = name.split()
    if len(teile) == 2 and teile[1] in ROEMISCH:
        return f"{teile[0]} {ROEMISCH[teile[1]]}"
    return name


def kurzform_finden(name: str, vorhanden: set[str]) -> str | None:
    """Kurzform bei gesetze-im-internet.de zu einer Abkürzung oder einem Open-Legal-Data-Slug.

    "SGB II" -> "sgb_2", "AÜG" -> "a_g" (Umlaute werden dort zu "_"), "ao-1977" -> "ao_1977",
    "AufenthG" -> "aufenthg_2004" (Fassung mit Jahreszahl). Ohne Treffer: None.
    """
    basis = re.sub(r"[äöüß]", "_", _arabisch(name.strip()).lower())
    basis = re.sub(r"[\s\-]+", "_", basis)
    if basis in vorhanden:
        return basis
    fassungen = [k for k in vorhanden if re.fullmatch(re.escape(basis) + r"_\d{4}", k)]
    return max(fassungen) if fassungen else None


def vergleichsform(name: str) -> str:
    """Zum Abgleich von Abkürzungen: "AO 1977" ~ "AO", "SGB II" ~ "SGB 2"."""
    name = re.sub(r"\s+\d{4}$", "", _arabisch(" ".join(name.split())))
    return re.sub(r"[\s\-_]", "", name.lower())


# --- 1. und 2. Welche Gesetze? ------------------------------------------------

def norm_zitierungen_laden(db: sqlite3.Connection, vorhanden: set[str]) -> int:
    """Ermittelt, welche Normen die Urteile der Datenbank zitieren.

    1. Zitationsgraph: Gelesen werden nur sechs kleine Spalten; Kanten zu Urteilen außerhalb
       der Datenbank werden sofort verworfen.
    2. Eigene Zählung mit normen.MUSTER in den Urteilstexten - für Schreibweisen, die der
       Graph nicht erkennt ("SGB II", "AufenthG").
    vorhanden: Kurzformen von gesetze-im-internet.de. Ergebnis: Anzahl gespeicherter Zeilen.
    """
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    import auswahl
    ids = dict(db.execute("SELECT slug, id FROM urteile"))
    gemerkt: dict[str, str | None] = {}                # jede Schreibweise nur einmal nachschlagen

    def finden(name: str) -> str | None:
        if name not in gemerkt:
            gemerkt[name] = kurzform_finden(name, vorhanden)
        return gemerkt[name]

    zaehler: dict[tuple, int] = {}
    fs = HfFileSystem()
    for datei in auswahl._dateien(config.ZITATIONSGRAPH):
        with fs.open(datei) as f:
            kanten = pq.read_table(f, columns=["from_type", "from_slug", "to_type", "to_law_book_code",
                                               "to_law_book_slug", "to_law_section"]).to_pandas()
        kanten = kanten[(kanten.from_type == "Case") & (kanten.to_type == "Law")
                        & kanten.from_slug.isin(ids.keys())]
        for slug, gesetz, buch, paragraph in zip(kanten.from_slug, kanten.to_law_book_code,
                                                 kanten.to_law_book_slug, kanten.to_law_section):
            # Abkürzung vor Slug: Der Slug "aug" meint bei Open Legal Data das AÜG,
            # bei gesetze-im-internet.de aber das Auslandsunterhaltsgesetz
            kurzform = finden(gesetz or "") or finden(buch or "")
            if kurzform and paragraph:
                schluessel = (ids[slug], gesetz, kurzform, paragraph_normieren(paragraph))
                zaehler[schluessel] = zaehler.get(schluessel, 0) + 1

    eigene: dict[tuple, int] = {}
    for urteil_id, text in db.execute("SELECT id, text FROM urteile"):
        for treffer in normen.MUSTER.finditer(text or ""):
            gesetz = " ".join(treffer["gesetz"].split())
            kurzform = finden(gesetz)
            if kurzform:
                schluessel = (urteil_id, gesetz, kurzform, f"{treffer['art']} {treffer['nr']}")
                eigene[schluessel] = eigene.get(schluessel, 0) + 1
    # Was der Graph schon kennt, zählt aus dem Graphen; die eigene Zählung ergänzt nur
    bekannt = {(u, k, p) for u, _, k, p in zaehler}
    for (u, gesetz, k, p), anzahl in eigene.items():
        if (u, k, p) not in bekannt:
            zaehler[(u, gesetz, k, p)] = anzahl
            bekannt.add((u, k, p))
    db.executemany("INSERT OR REPLACE INTO norm_zitierungen VALUES (?, ?, ?, ?, ?)",
                   [(*schluessel, anzahl) for schluessel, anzahl in zaehler.items()])
    db.commit()
    return len(zaehler)


def paragraph_normieren(paragraph: str) -> str:
    """"Art 3" -> "Art. 3", "§  6" -> "§ 6" (einheitlich wie in Urteilen zitiert)."""
    treffer = ENBEZ.match(paragraph.strip())
    if not treffer:
        return paragraph.strip()
    return f"{'Art.' if treffer[1] == 'Art' else '§'} {treffer[2]}"


def meistzitierte_gesetze(db: sqlite3.Connection, anzahl: int, vorhanden: set[str]) -> list[tuple[str, list[str]]]:
    """Die `anzahl` Gesetze, die in den meisten Urteilen zitiert werden.

    Ergebnis: [(kurzform, [alle Schreibweisen aus den Urteilen]), ...], z. B. ("sgb_2", ["SGB 2", "SGB II"]).
    vorhanden: Kurzformen aus dem Inhaltsverzeichnis von gesetze-im-internet.de. Gesetze, die es
    dort nicht gibt (Landesrecht, EU-Recht, aufgehobene Gesetze), werden übersprungen.
    """
    zeilen = db.execute("SELECT kurzform, GROUP_CONCAT(DISTINCT gesetz), COUNT(DISTINCT urteil_id) AS n "
                        "FROM norm_zitierungen GROUP BY kurzform ORDER BY n DESC").fetchall()
    return [(kurzform, namen.split(",")) for kurzform, namen, _ in zeilen if kurzform in vorhanden][:anzahl]


def inhaltsverzeichnis() -> set[str]:
    """Alle Kurzformen aus gii-toc.xml, z. B. {"agg", "bgb", "ao_1977", ...}"""
    with urllib.request.urlopen(f"{GII}/gii-toc.xml", timeout=60) as antwort:
        wurzel = ET.fromstring(antwort.read())
    return {m[1] for link in wurzel.iter("link") if (m := re.search(r"/([^/]+)/xml\.zip$", link.text or ""))}


# --- 3. Gesetz lesen ----------------------------------------------------------

def _text(element: ET.Element) -> str:
    """Wandelt den Inhalt einer Norm in lesbaren Text um.

    Jeder Absatz (<P>) und jeder Aufzählungspunkt (<DT>1.</DT><DD>...</DD>) steht auf
    einer eigenen Zeile: "(1) Beschäftigte ... sind\\n1. Arbeitnehmerinnen ...".
    """
    teile: list[str] = []

    def lauf(e: ET.Element) -> None:
        if e.tag in ("P", "DT", "row", "BR"):
            teile.append("\n")
        if e.tag == "entry":
            teile.append(" | ")
        teile.append(e.text or "")
        for kind in e:
            lauf(kind)
            teile.append(kind.tail or "")
        if e.tag == "DT":
            teile.append(" ")
        if e.tag == "DL":
            teile.append("\n")

    lauf(element)
    zeilen = (" ".join(z.split()) for z in "".join(teile).split("\n"))
    return "\n".join(z for z in zeilen if z)


def gesetz_lesen(xml: bytes) -> dict:
    """Liest ein Gesetz aus dem XML von gesetze-im-internet.de.

    Ergebnis: {"gesetz": "AGG", "namen": {"AGG"}, "titel": "...", "stand": "...",
               "normen": [{"art": "§", "nr": "6", "titel": "...", "text": "(1) ..."}, ...]}
    Gliederungsüberschriften, Fußnoten und Anlagen werden übersprungen.
    """
    wurzel = ET.fromstring(xml)
    gesetz = {"gesetz": "", "namen": set(), "titel": "", "stand": "", "normen": []}
    for norm in wurzel.iter("norm"):
        meta = norm.find("metadaten")
        if meta is None:
            continue
        for feld in ("jurabk", "amtabk"):
            if (wert := (meta.findtext(feld) or "").strip()):
                gesetz["namen"].add(wert)
        if not gesetz["gesetz"]:
            gesetz["gesetz"] = (meta.findtext("amtabk") or meta.findtext("jurabk") or "").strip()
        if meta.findtext("langue") and not gesetz["titel"]:
            gesetz["titel"] = " ".join(meta.findtext("langue").split())
        # Mehrere Standangaben möglich ("Neuf" = Neufassung, "Stand" = letzte Änderung): "Stand" bevorzugen
        staende = [(s.findtext("standtyp"), " ".join((s.findtext("standkommentar") or "").split()))
                   for s in meta.iter("standangabe")]
        if staende and not gesetz["stand"]:
            bevorzugt = [k for typ, k in staende if typ == "Stand" and k] or [k for _, k in staende if k]
            gesetz["stand"] = " · ".join(bevorzugt)
        bezeichnung = ENBEZ.match((meta.findtext("enbez") or "").strip())
        if not bezeichnung:
            continue
        inhalt = norm.find("textdaten/text/Content")
        gesetz["normen"].append({
            "art": "Art." if bezeichnung[1] == "Art" else "§",
            "nr": bezeichnung[2],
            "titel": " ".join((meta.findtext("titel") or "").split()),
            "text": _text(inhalt) if inhalt is not None else "",
        })
    return gesetz


def norm_url(kurzform: str, art: str, nr: str) -> str:
    """Adresse einer Norm, z. B. ("bgb", "§", "573a") -> https://www.gesetze-im-internet.de/bgb/__573a.html"""
    return f"{GII}/{kurzform}/{'art_' if art == 'Art.' else '__'}{nr}.html"


def gesetz_speichern(db: sqlite3.Connection, kurzform: str, gesetz: dict, geaendert: str,
                     weitere_namen: tuple[str, ...] = ()) -> int:
    """Ersetzt alle Normen eines Gesetzes in der Datenbank. Ergebnis: Anzahl Normen."""
    alte = [zeile[0] for zeile in db.execute("SELECT id FROM normen WHERE kurzform = ?", (kurzform,))]
    db.executemany("DELETE FROM normen_fts WHERE rowid = ?", [(i,) for i in alte])
    db.execute("DELETE FROM normen WHERE kurzform = ?", (kurzform,))
    for n in gesetz["normen"]:
        zeiger = db.execute("INSERT INTO normen (kurzform, gesetz, art, nr, titel, text, url) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (kurzform, gesetz["gesetz"], n["art"], n["nr"], n["titel"], n["text"],
                             norm_url(kurzform, n["art"], n["nr"])))
        db.execute("INSERT INTO normen_fts (rowid, gesetz, nr, titel, text) VALUES (?, ?, ?, ?, ?)",
                   (zeiger.lastrowid, gesetz["gesetz"], n["nr"], n["titel"], n["text"]))
    db.execute("INSERT OR REPLACE INTO gesetze VALUES (?, ?, ?, ?, ?, ?)",
               (kurzform, gesetz["gesetz"], gesetz["titel"], gesetz["stand"], geaendert, date.today().isoformat()))
    for name in gesetz["namen"] | set(weitere_namen):
        db.execute("INSERT OR REPLACE INTO gesetz_namen VALUES (?, ?)", (" ".join(name.split()), kurzform))
    db.commit()
    return len(gesetz["normen"])


def herunterladen(kurzform: str, bekannt: str | None) -> tuple[bytes | None, str]:
    """Lädt das XML eines Gesetzes - nur, wenn sich die Datei seit `bekannt` geändert hat.

    Ergebnis: (XML oder None, wenn unverändert; Last-Modified)
    """
    url = f"{GII}/{kurzform}/xml.zip"
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as antwort:
        geaendert = antwort.headers.get("Last-Modified", "")
    if bekannt and geaendert == bekannt:
        return None, geaendert
    with urllib.request.urlopen(url, timeout=120) as antwort:
        archiv = zipfile.ZipFile(io.BytesIO(antwort.read()))
    name = next(n for n in archiv.namelist() if n.lower().endswith(".xml"))
    return archiv.read(name), geaendert


def gesetz_entfernen(db: sqlite3.Connection, kurzform: str) -> None:
    """Entfernt ein Gesetz, das nicht mehr zu den meistzitierten gehört, samt Normsuche."""
    alte = [zeile[0] for zeile in db.execute("SELECT id FROM normen WHERE kurzform = ?", (kurzform,))]
    db.executemany("DELETE FROM normen_fts WHERE rowid = ?", [(i,) for i in alte])
    for tabelle in ("normen", "gesetze", "gesetz_namen"):
        db.execute(f"DELETE FROM {tabelle} WHERE kurzform = ?", (kurzform,))
    db.commit()
    try:
        import chromadb
        chromadb.PersistentClient(path=str(config.CHROMA_PFAD)).get_collection(
            config.CHROMA_NORMEN).delete(where={"kurzform": kurzform})
    except Exception:                                  # Normsuche (noch) nicht aufgebaut
        pass


# --- 4. Normsuche -------------------------------------------------------------

def normsuche_aktualisieren(db: sqlite3.Connection, kurzformen: list[str]) -> int:
    """Berechnet die Embeddings für die Normen der angegebenen Gesetze neu."""
    import chromadb
    import ollama
    sammlung = chromadb.PersistentClient(path=str(config.CHROMA_PFAD)).get_or_create_collection(
        name=config.CHROMA_NORMEN, metadata={"hnsw:space": "cosine"})
    anzahl = 0
    for kurzform in kurzformen:
        sammlung.delete(where={"kurzform": kurzform})
        zeilen = db.execute("SELECT id, gesetz, art, nr, titel, text FROM normen "
                            "WHERE kurzform = ? AND text != ''", (kurzform,)).fetchall()
        for start in range(0, len(zeilen), config.EMBED_BATCH):
            paket = zeilen[start:start + config.EMBED_BATCH]
            texte = [f"{art} {nr} {gesetz} – {titel}\n{text[:1500]}" for _, gesetz, art, nr, titel, text in paket]
            sammlung.add(ids=[str(z[0]) for z in paket], documents=texte,
                         embeddings=ollama.embed(model=config.EMBED_MODELL, input=texte)["embeddings"],
                         metadatas=[{"kurzform": kurzform} for _ in paket])
            anzahl += len(paket)
    return anzahl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ohne-normsuche", action="store_true", help="keine Embeddings für die Normsuche")
    argumente = parser.parse_args()
    start = time.time()

    with closing(sqlite3.connect(config.SQLITE_PFAD)) as db:
        daten_laden.tabellen_anlegen(db)
        print("Lade das Inhaltsverzeichnis von gesetze-im-internet.de ...", flush=True)
        vorhanden = inhaltsverzeichnis()
        if not db.execute("SELECT 1 FROM norm_zitierungen LIMIT 1").fetchone():
            print("Ermittle, welche Normen die Urteile zitieren (Zitationsgraph und Urteilstexte) ...", flush=True)
            print(f"  {norm_zitierungen_laden(db, vorhanden):,} Zitierungen von Normen gespeichert.".replace(",", "."))

        auswahl = meistzitierte_gesetze(db, config.GESETZE_ANZAHL, vorhanden)
        bekannt = dict(db.execute("SELECT kurzform, geaendert FROM gesetze"))
        for kurzform in set(bekannt) - {k for k, _ in auswahl}:
            gesetz_entfernen(db, kurzform)             # nicht mehr unter den meistzitierten

        geaendert_liste, fehler, normen_gesamt = [], [], 0
        for i, (kurzform, schreibweisen) in enumerate(auswahl, 1):
            abkuerzung = schreibweisen[0]
            try:
                xml, geaendert = herunterladen(kurzform, bekannt.get(kurzform))
            except Exception as e:                     # Netzwerk, kaputtes Archiv: Gesetz überspringen
                fehler.append(f"{abkuerzung}: {e}")
                continue
            if xml is None:                            # unverändert: nur neue Schreibweisen ergänzen
                eigene = {vergleichsform(n) for (n,) in db.execute(
                    "SELECT name FROM gesetz_namen WHERE kurzform = ?", (kurzform,))}
                db.executemany("INSERT OR IGNORE INTO gesetz_namen VALUES (?, ?)",
                               [(s, kurzform) for s in schreibweisen if vergleichsform(s) in eigene])
                db.commit()
                continue
            gesetz = gesetz_lesen(xml)
            # Sicherheitsnetz: Passt die Abkürzung im XML zu den Zitaten? Sonst falsches Gesetz erwischt.
            eigene = {vergleichsform(n) for n in gesetz["namen"]}
            passende = tuple(s for s in schreibweisen if vergleichsform(s) in eigene)
            if not passende:
                fehler.append(f"{abkuerzung}: {kurzform} enthält {', '.join(sorted(gesetz['namen']))} - übersprungen")
                continue
            anzahl = gesetz_speichern(db, kurzform, gesetz, geaendert, weitere_namen=passende)
            normen_gesamt += anzahl
            geaendert_liste.append(kurzform)
            print(f"  [{i}/{len(auswahl)}] {gesetz['gesetz']}: {anzahl} Normen · {gesetz['stand'] or 'ohne Standangabe'}",
                  flush=True)

        print(f"{len(auswahl)} Gesetze geprüft, {len(geaendert_liste)} neu oder geändert "
              f"({normen_gesamt:,} Normen), {len(auswahl) - len(geaendert_liste) - len(fehler)} unverändert."
              .replace(",", "."))
        for f in fehler:
            print(f"  [Fehler] {f}")

        if geaendert_liste and not argumente.ohne_normsuche:
            print("Berechne die Embeddings für die Normsuche ...", flush=True)
            print(f"  {normsuche_aktualisieren(db, geaendert_liste):,} Normen indexiert.".replace(",", "."))
    print(f"Fertig nach {time.time() - start:.0f} s.")


if __name__ == "__main__":
    main()
