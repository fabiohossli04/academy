#!/usr/bin/env python3
"""Prüft Kuratierung, academy.json und Testfragen; auch für den Build verwendbar."""
import json, pathlib, collections, math, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

def check_curation(curated, root):
    problems, warn, seen = [], [], set()
    for cid, meta in curated.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", cid):
            problems.append("Ungültige Kurs-ID in lessons.json")
        if not isinstance(meta.get("running"), bool):
            problems.append(f"{cid}: running muss ein bool sein")
        for field in ("portal", "title", "subtitle", "lang", "why"):
            if not isinstance(meta.get(field), str):
                problems.append(f"{cid}: ungültiges Kursfeld {field}")
        if not isinstance(meta.get("portal"), str) or not meta["portal"].startswith("/"):
            problems.append(f"{cid}: ungültiger Portal-Pfad")
        nrs = [l["nr"] for l in meta["lessons"]]
        if any(type(nr) is not int for nr in nrs) or nrs != list(range(1, len(nrs) + 1)):
            problems.append(f"{cid}: kuratierte Lektionsnummern nicht lückenlos: {nrs}")
        for lesson in meta["lessons"]:
            tag = f"{cid}/{lesson['nr']}"
            if not isinstance(lesson.get("title"), str) or not lesson["title"]:
                problems.append(f"{tag}: kein kuratierter Titel")
            topics = lesson.get("topics")
            if not isinstance(topics, list) or any(not isinstance(t, str) for t in topics):
                problems.append(f"{tag}: ungültige Themen")
            clips = lesson.get("clips")
            if not isinstance(clips, list) or not clips:
                problems.append(f"{tag}: keine kuratierten Clips")
                continue
            for oid in clips:
                if not isinstance(oid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", oid):
                    problems.append(f"{tag}: ungültige kuratierte opencastId")
                elif oid in seen:
                    problems.append(f"{tag}: opencastId mehrfach kuratiert: {oid}")
                else:
                    seen.add(oid)
    # HEAD ist die letzte veröffentlichte Zuordnung. Titel und Themen bleiben editierbar.
    try:
        head = subprocess.run(["git", "show", "HEAD:data/lessons.json"], cwd=root,
                              capture_output=True, text=True)
    except OSError:
        head = None
    if head is None or head.returncode:
        warn.append("Prüfung veröffentlichter Lektionen übersprungen: Git oder HEAD:data/lessons.json nicht verfügbar")
    else:
        published = json.loads(head.stdout)
        current = {(cid, l["nr"]): l.get("clips") for cid, c in curated.items() for l in c["lessons"]}
        for cid, course in published.items():
            for lesson in course["lessons"]:
                nr = lesson["nr"]
                if current.get((cid, nr)) != lesson["clips"]:
                    problems.append(f"veröffentlichte Lektion {cid}/{nr} geändert – Nachträge bekommen eine neue Nummer")
    return problems, warn

def check(data, curated=None, root=ROOT):
    """Prüft einen vollständigen Kandidaten, ohne academy.json zu schreiben."""
    if curated is None:
        curated = json.loads((root / "data" / "lessons.json").read_text(encoding="utf-8"))
    problems, warn = check_curation(curated, root)
    tot_q, seen = 0, set()
    ids = [c["id"] for c in data["courses"]]
    if len(set(ids)) != len(ids):
        problems.append("Kurs-ID mehrfach verwendet")
    expected = {cid for cid, c in curated.items() if c["lessons"]}
    actual = {c["id"] for c in data["courses"] if c["kind"] == "stream"}
    if actual != expected:
        problems.append("Stream-Kurse entsprechen nicht den nichtleeren Kursen in lessons.json")
    for c in data["courses"]:
        qf = root/"data"/"quiz"/f"{c['id']}.json"
        quiz = json.loads(qf.read_text()) if qf.exists() else {}
        tot_q += sum(len(b["questions"]) for b in quiz.values())
        if c["kind"] == "stream":
            meta = curated.get(c["id"])
            if meta is None:
                problems.append(f"{c['id']}: Kurs fehlt in lessons.json")
            else:
                for field in ("title", "subtitle", "lang", "why", "running"):
                    if c.get(field) != meta[field]:
                        problems.append(f"{c['id']}: {field} weicht von lessons.json ab")
                if c.get("portalUrl") != "https://video.ethz.ch" + meta["portal"]:
                    problems.append(f"{c['id']}: Portal-URL weicht von lessons.json ab")
                actual = [{"nr": l["nr"], "title": l["title"], "topics": l["topics"],
                           "clips": [clip["opencastId"] for clip in l.get("clips", [])]}
                          for l in c["lessons"]]
                if actual != meta["lessons"]:
                    problems.append(f"{c['id']}: Lektionen weichen von lessons.json ab")
        nrs = [l["nr"] for l in c["lessons"]]
        if any(type(nr) is not int for nr in nrs) or nrs != list(range(1, len(nrs)+1)):
            problems.append(f"{c['id']}: Lektionsnummern nicht lückenlos: {nrs}")
        for l in c["lessons"]:
            if not l.get("title"):
                problems.append(f"{c['id']}/{l['nr']}: kein Titel")
            if c["kind"] == "stream":
                clips = l.get("clips") or []
                if not clips:
                    problems.append(f"{c['id']}/{l['nr']}: keine Clips")
                if any(field in l for field in ("video", "captionLocal", "captionLang")):
                    problems.append(f"{c['id']}/{l['nr']}: alte Einzelfelder statt Clip-Format")
                for clip in clips:
                    oid = clip.get("opencastId")
                    tag = f"{c['id']}/{l['nr']} Clip {oid}"
                    if not isinstance(oid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", oid):
                        problems.append(f"{tag}: ungültige opencastId")
                    elif oid in seen:
                        problems.append(f"{tag}: opencastId mehrfach verwendet")
                    else:
                        seen.add(oid)
                    if not isinstance(clip.get("video"), str) or not clip["video"].startswith("https://"):
                        problems.append(f"{tag}: keine HTTPS-Video-URL")
                    cap = clip.get("captionLocal")
                    if not isinstance(cap, str) or not (root / cap).is_file():
                        problems.append(f"{tag}: Untertitel fehlt: {cap}")
                    if cap != f"transcripts/{c['id']}/{oid}.vtt":
                        problems.append(f"{tag}: Untertitelpfad entspricht nicht der opencastId")
                    if not clip.get("title"):
                        problems.append(f"{tag}: kein Portal-Titel")
                    if not clip.get("captionLang"):
                        problems.append(f"{tag}: keine Untertitelsprache")
                    duration = clip.get("durationMs")
                    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
                        problems.append(f"{tag}: keine gültige Dauer")
                if not l.get("durationMs"):
                    problems.append(f"{c['id']}/{l['nr']}: keine Dauer")
                elif l["durationMs"] != sum(clip.get("durationMs") or 0 for clip in clips):
                    problems.append(f"{c['id']}/{l['nr']}: Dauer entspricht nicht der Summe der Clips")
            else:
                if not l.get("externalUrl"): problems.append(f"{c['id']}/{l['nr']}: kein externer Link")
            block = quiz.get(str(l["nr"]))
            if not block or not block.get("questions"):
                problems.append(f"{c['id']}/{l['nr']}: keine Testfragen")
                continue
            for i, q in enumerate(block["questions"], 1):
                tag = f"{c['id']}/{l['nr']} Frage {i}"
                if len(q["options"]) < 3: problems.append(f"{tag}: weniger als 3 Antworten")
                if not isinstance(q["answer"], int) or not (0 <= q["answer"] < len(q["options"])):
                    problems.append(f"{tag}: Antwortindex ungültig ({q['answer']})")
                if len(set(q["options"])) != len(q["options"]):
                    problems.append(f"{tag}: doppelte Antwortmöglichkeit")
                if not q.get("why"): problems.append(f"{tag}: keine Erklärung")
                if len(q["q"]) < 15: warn.append(f"{tag}: sehr kurze Frage")
        # Verteilung der richtigen Antworten - steht sie fast immer an derselben Stelle,
        # testet der Quiz das Erraten des Musters statt das Verständnis.
        pos = collections.Counter(q["answer"] for b in quiz.values() for q in b["questions"])
        tot = sum(pos.values())
        if tot:
            top = max(pos.values()) / tot
            line = f"{c['id']}: {tot} Fragen, häufigste Antwortposition {top*100:.0f} %"
            if top > 0.45:
                problems.append(line + " - zu einseitig, bitte mischen")
            else:
                warn.append(line)
            # Auch die Zeichenlänge darf die richtige Antwort nicht verraten.
            longest = 0
            for b in quiz.values():
                for q in b["questions"]:
                    a, lengths = q["answer"], [len(o) for o in q["options"]]
                    if isinstance(a, int) and 0 <= a < len(lengths):
                        m = max(lengths)
                        if lengths[a] == m and lengths.count(m) == 1: longest += 1
            share = longest / tot
            line = f"{c['id']}: richtige Antwort bei {share*100:.0f} % der Fragen die längste Option"
            if share > 0.40:
                problems.append(line + " - zu leicht zu erraten, bitte angleichen")
            else:
                warn.append(line)
    return problems, warn, tot_q

def report(data, problems, warn, tot_q):
    print(f"{len(data['courses'])} Kurse, {sum(len(c['lessons']) for c in data['courses'])} Lektionen, {tot_q} Fragen")
    for w in warn:
        print("  HINWEIS:", w)
    if problems:
        print(f"\n{len(problems)} PROBLEME:")
        for problem in problems[:30]:
            print("  ✗", problem)
    else:
        print("✅ Alle Prüfungen bestanden")

if __name__ == "__main__":
    try:
        data = json.loads((ROOT / "data" / "academy.json").read_text(encoding="utf-8"))
        problems, warn, tot_q = check(data)
        report(data, problems, warn, tot_q)
        sys.exit(1 if problems else 0)
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"✗ Daten konnten nicht geprüft werden: {err}")
        sys.exit(1)
