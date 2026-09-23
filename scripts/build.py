#!/usr/bin/env python3
"""Baut data/academy.json: Rohdaten aus dem ETH-Portal + Lektionstitel + Scala-Modul."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
raw = {c["id"]: c for c in json.loads((ROOT/"data"/"courses-raw.json").read_text())}

TITLES = {
"theoinf": [
 ("Alphabete, Wörter und Sprachen", ["Alphabet", "Wort", "Sprache", "Abzählen"]),
 ("Kolmogorov-Komplexität: Wie viel Information steckt drin?", ["Informationsgehalt", "Kodierung"]),
 ("Komprimierbarkeit und der Weg zu endlichen Automaten", ["Zufälligkeit", "untere Schranken"]),
 ("Endliche Automaten: Definition und Berechnung", ["Zustand", "Übergangsfunktion", "Konfiguration"]),
 ("Untere Schranken beweisen", ["Widerspruchsbeweis", "Abzählargument"]),
 ("Nichtexistenzbeweise für endliche Automaten", ["Beweismethoden", "Grenzen"]),
 ("Warum Automaten sich erinnern müssen", ["Zustandswiederholung", "Schubfachprinzip", "Pumping"]),
 ("Nichtdeterminismus und Potenzmengenkonstruktion", ["NEA", "DEA", "Äquivalenz"]),
 ("Die Turingmaschine", ["Church-Turing-These", "Band", "Berechenbarkeit"]),
 ("Varianten der Turingmaschine", ["Mehrband", "Robustheit", "Simulation"]),
 ("Abzählbar und überabzählbar", ["Hilberts Hotel", "Kardinalität", "Diagonalisierung"]),
 ("Die Diagonalsprache und erste Reduktionen", ["Diagonalargument", "Reduktion"]),
 ("Universelle Sprache und Postsches Korrespondenzproblem", ["universelle TM", "PKP"]),
 ("Unentscheidbarkeit von Programmeigenschaften", ["Satz von Rice", "Halteproblem"]),
 ("Reduktionen zwischen unentscheidbaren Sprachen", ["Reduktion", "rekursiv aufzählbar"]),
 ("Überblick: die Landkarte der Unentscheidbarkeit", ["Klassifikation", "Beweismuster"]),
 ("Komplexitätsmaße: Zeit und Platz", ["Laufzeit", "Speicherbedarf", "Speedup"]),
 ("Die Klassen P und NP", ["Verifikation", "Zertifikat", "Nichtdeterminismus"]),
 ("Beziehungen zwischen Zeit und Platz", ["Konfigurationsgraph", "Hierarchie"]),
 ("NP-Vollständigkeit", ["Reduktion", "härteste Probleme"]),
 ("Polynomielle Reduktionen in der Praxis", ["SAT", "Clique", "Problemtransfer"]),
 ("Der Satz von Cook", ["SAT", "Formel aus Berechnung"]),
 ("Optimierungsprobleme und Ableitungen", ["Optimierung", "Verifikation", "Grammatik"]),
 ("Reguläre und kontextfreie Grammatiken", ["Grammatik", "Ableitungsbaum", "Pumping-Lemma"]),
],
"architektur": [
 ("Warum Rechnerarchitektur zählt", ["Motivation", "Zielkonflikte", "Leistung"]),
 ("Kombinatorische Logik", ["Boolesche Algebra", "Wahrheitstabelle", "Komparator"]),
 ("Sequenzielle Logik und Taktflanken", ["Flipflop", "Takt", "Zustandsautomat"]),
 ("Hardware beschreiben mit Verilog", ["HDL", "Bitvektoren", "Modul"]),
 ("Zeitverhalten: Verzögerung, Setup und Hold", ["Laufzeit", "Glitch", "Taktgrenze"]),
 ("Rechenmodell und Befehlssatz", ["ISA", "ALU", "Ausführungseinheit"]),
 ("Befehle, Sprünge und der Datenpfad", ["Sprung", "Registerfile", "Programmzähler"]),
 ("Vom Zustandsautomaten zum Prozessor", ["Zustandsmaschine", "Abstraktion"]),
 ("Mikroarchitektur: den Datenpfad bauen", ["Single-Cycle", "Datenpfad", "Steuersignale"]),
 ("Steuerwerk und der Einstieg ins Pipelining", ["Steuerwerk", "Taktzyklus", "Parallelität"]),
 ("Pipelining: Register, Konflikte, Forwarding", ["Pipeline", "Hazard", "Stall"]),
 ("Ausführung ausser der Reihe", ["Out-of-Order", "Reservation Station", "Tomasulo"]),
 ("Sprungvorhersage", ["Branch Prediction", "Trefferquote", "Strafzyklen"]),
 ("VLIW und Befehlsparallelität", ["VLIW", "ILP", "Compiler"]),
 ("Systolische Arrays und Spezialhardware", ["Beschleuniger", "Datenfluss"]),
 ("Array- und Vektorprozessoren", ["Vektor", "Datenparallelität"]),
 ("SIMD, SIMT und GPUs", ["SIMD", "GPU", "Threads"]),
 ("DRAM von innen", ["Bank", "Zeile", "Zugriffszeit"]),
 ("Caches: das Grundprinzip", ["Lokalität", "Trefferquote", "Cache-Zeile"]),
 ("Assoziativität und Fehlzugriffe", ["Assoziativität", "Verdrängung", "Miss-Rate"]),
 ("Virtueller Speicher", ["Seitentabelle", "Adressübersetzung", "TLB"]),
 ("Vorausladen: Prefetching", ["Prefetch", "Zugriffsmuster", "Vorhersage"]),
],
}

WHY = {
 "theoinf": "Die Denkwerkzeuge dahinter: Was ist überhaupt berechenbar, warum sind manche Probleme hart, "
            "und wann hört Optimieren auf zu helfen. Auf Deutsch.",
 "architektur": "Caches, Speicher und Parallelität von unten. Danach verstehst du, was eine Trefferquote "
                "wirklich bedeutet - und warum Reihenfolge und Lokalität über Tempo entscheiden.",
 "scala": "Funktionales Denken an der Quelle: Odersky hat Scala erfunden. Unveränderliche Werte, reine "
          "Funktionen, Typen - überträgt sich direkt auf deinen TypeScript-Code.",
}

SCALA_SLIDE = "https://www.epfl.ch/labs/lamp/wp-content/uploads/2019/01/{}-no-annot.pdf"
SCALA = [
 ("Funktionen und Auswertung", ["Programmierparadigmen", "Auswertungsstrategie", "Rekursion"], "week1-1", 95),
 ("Funktionen höherer Ordnung", ["Currying", "Endrekursion", "Fixpunkt"], "week2-1", 90),
 ("Daten und Abstraktion", ["Klassenhierarchie", "Abstraktion"], "week3-1", 85),
 ("Typen und Mustererkennung", ["Polymorphie", "Subtyping", "Pattern Matching"], "week4-1", 95),
 ("Listen", ["Listenoperationen", "Tupel", "Beweise durch Umformen"], "week5-1", 90),
 ("Sammlungen und For-Ausdrücke", ["Collections", "for-Ausdruck", "Maps"], "week6-1", 90),
 ("Verzögerte Auswertung", ["Lazy Evaluation", "Streams", "unendliche Folgen"], "week7-1", 85),
]

out = {"generated": "2026-09-23", "dailyMinutes": 30, "courses": []}

for cid, meta in [("theoinf", ("Theoretische Informatik", "ETH Zürich · Dennis Komm · HS 2023", "de")),
                  ("architektur", ("Digital Design und Rechnerarchitektur", "ETH Zürich · Onur Mutlu · FS 2025", "en"))]:
    src = raw[cid]
    titles = TITLES[cid]
    if len(titles) != len(src["lessons"]):
        raise SystemExit(f"{cid}: {len(titles)} Titel, aber {len(src['lessons'])} Lektionen")
    lessons = []
    for l, (t, topics) in zip(src["lessons"], titles):
        lessons.append({
            "nr": l["nr"], "title": t, "topics": topics,
            "durationMs": l["durationMs"], "creators": l["creators"],
            "video": l["video"],
            "captionLocal": f"transcripts/{cid}/{l['nr']:02d}.vtt",
            "captionLang": l["captionLang"],
        })
    out["courses"].append({
        "id": cid, "kind": "stream",
        "title": meta[0], "subtitle": meta[1], "lang": meta[2],
        "why": WHY[cid], "portalUrl": src["portalUrl"], "lessons": lessons,
    })

out["courses"].append({
    "id": "scala", "kind": "external",
    "title": "Funktionale Programmierung in Scala",
    "subtitle": "EPFL · Martin Odersky · Coursera",
    "lang": "en", "why": WHY["scala"],
    "portalUrl": "https://www.coursera.org/learn/scala-functional-programming",
    "note": "Dieser Kurs liegt hinter dem Coursera-Login (Anmeldung nötig, Anschauen kostenlos ohne "
            "Zertifikat). Die Videos lassen sich nicht wie bei der ETH einbetten. Die Folien der EPFL sind "
            "dagegen frei abrufbar und hier direkt verlinkt. Die Tests hier prüfen die Konzepte der Woche - "
            "sie sind aus dem veröffentlichten Kursplan gebaut, nicht aus den Videoinhalten.",
    "lessons": [{
        "nr": i, "title": t, "topics": topics,
        "estMinutes": mins, "durationMs": mins*60000,
        "externalUrl": "https://www.coursera.org/learn/scala-functional-programming",
        "slidesUrl": SCALA_SLIDE.format(slug),
    } for i, (t, topics, slug, mins) in enumerate(SCALA, 1)],
})

dest = ROOT/"data"/"academy.json"
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))
tot = sum(sum(l["durationMs"] for l in c["lessons"]) for c in out["courses"])
print(f"{len(out['courses'])} Kurse, {sum(len(c['lessons']) for c in out['courses'])} Lektionen, {tot/3600000:.1f} h")
print("geschrieben:", dest)
