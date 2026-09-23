#!/usr/bin/env python3
"""Baut und prüft academy.json aus stabiler Kuratierung und Portal-Metadaten."""
import argparse, json, os, pathlib, sys, tempfile

# Auch der Trockenlauf erzeugt keine Dateien neben den Skripten.
sys.dont_write_bytecode = True
from check import check, report

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCALA_WHY = ("Funktionales Denken an der Quelle: Odersky hat Scala erfunden. Unveränderliche Werte, reine "
             "Funktionen, Typen - überträgt sich direkt auf deinen TypeScript-Code.")

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

def scala_course():
    return {
        "id": "scala", "kind": "external",
        "title": "Funktionale Programmierung in Scala",
        "subtitle": "EPFL · Martin Odersky · Coursera",
        "lang": "en", "why": SCALA_WHY,
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
    }

def build_candidate(curated, sources):
    problems, notes, raw = [], [], {}
    for course in sources:
        cid = course["id"]
        if cid in raw:
            problems.append(f"{cid}: Kurs mehrfach in den Rohdaten")
        raw[cid] = course
    out = {"generated": "2026-09-23", "dailyMinutes": 30, "courses": []}
    for cid, meta in curated.items():
        source = raw.get(cid)
        if source is None:
            problems.append(f"{cid}: Kurs fehlt in den Portal-Rohdaten")
            source = {"lessons": []}
        recordings = {}
        for clip in source["lessons"]:
            oid = clip["opencastId"]
            if oid in recordings:
                problems.append(f"{cid}: opencastId mehrfach im Portal: {oid}")
            recordings[oid] = clip
        used = {oid for lesson in meta["lessons"] for oid in lesson["clips"]}
        for oid, clip in recordings.items():
            if oid not in used:
                notes.append(f"neu im Portal, noch nicht aufgenommen: {cid} {clip['created'][:10]} "
                             f"'{clip['title']}' {oid} ({clip['durationMs']/60000:.1f} min)")
        lessons = []
        for lesson in meta["lessons"]:
            clips, creators = [], []
            for oid in lesson["clips"]:
                clip = recordings.get(oid)
                if clip is None:
                    problems.append(f"{cid}/{lesson['nr']}: kuratierte opencastId fehlt im Portal "
                                    f"(entfernt oder gesperrt): {oid}")
                    continue
                clips.append({
                    "opencastId": oid, "title": clip["title"], "video": clip["video"],
                    "captionLocal": f"transcripts/{cid}/{oid}.vtt",
                    "captionLang": clip["captionLang"], "durationMs": clip["durationMs"],
                })
                for creator in clip["creators"]:
                    if creator not in creators:
                        creators.append(creator)
            lessons.append({
                "nr": lesson["nr"], "title": lesson["title"], "topics": lesson["topics"],
                "durationMs": sum(clip["durationMs"] for clip in clips),
                "creators": creators, "clips": clips,
            })
        if lessons:
            out["courses"].append({
                "id": cid, "kind": "stream", "title": meta["title"], "subtitle": meta["subtitle"],
                "lang": meta["lang"], "why": meta["why"],
                "portalUrl": "https://video.ethz.ch" + meta["portal"],
                "running": meta["running"], "lessons": lessons,
            })
    out["courses"].append(scala_course())
    order = {cid: i for i, cid in enumerate(("theoinf", "architektur", "scala", "privacy", "software"))}
    out["courses"].sort(key=lambda c: order.get(c["id"], len(order)))
    return out, problems, notes

def replace_json(dest, data):
    """Ersetzt erst den vollständig geschriebenen, bereits geprüften Kandidaten."""
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dest.parent,
                                         prefix=f".{dest.name}.", delete=False) as f:
            temp = pathlib.Path(f.name)
            json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        temp.chmod(dest.stat().st_mode & 0o777 if dest.exists() else 0o644)
        os.replace(temp, dest)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="prüfen und berichten, ohne zu schreiben")
    args = parser.parse_args()
    curated = json.loads((ROOT / "data" / "lessons.json").read_text(encoding="utf-8"))
    raw = json.loads((ROOT / "data" / "courses-raw.json").read_text(encoding="utf-8"))
    data, problems, notes = build_candidate(curated, raw)
    checked, warn, tot_q = check(data, curated=curated)
    problems.extend(checked)
    report(data, problems, notes + warn, tot_q)
    if problems:
        print("academy.json unverändert")
        return 1
    total = sum(l["durationMs"] for c in data["courses"] for l in c["lessons"])
    print(f"{len(data['courses'])} Kurse, {sum(len(c['lessons']) for c in data['courses'])} Lektionen, {total/3600000:.1f} h")
    if args.dry_run:
        print("Trockenlauf erfolgreich: academy.json unverändert")
    else:
        dest = ROOT / "data" / "academy.json"
        replace_json(dest, data)
        print("geschrieben:", dest)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"✗ Build fehlgeschlagen: {err}")
        print("academy.json unverändert")
        sys.exit(1)
