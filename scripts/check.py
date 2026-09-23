#!/usr/bin/env python3
"""Prueft academy.json und die Testfragen auf Vollstaendigkeit und Plausibilitaet."""
import json, pathlib, collections, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
data = json.loads((ROOT/"data"/"academy.json").read_text())
problems, warn = [], []

for c in data["courses"]:
    qf = ROOT/"data"/"quiz"/f"{c['id']}.json"
    quiz = json.loads(qf.read_text()) if qf.exists() else {}
    nrs = [l["nr"] for l in c["lessons"]]
    if nrs != list(range(1, len(nrs)+1)):
        problems.append(f"{c['id']}: Lektionsnummern nicht lückenlos: {nrs}")
    for l in c["lessons"]:
        if not l.get("title"):
            problems.append(f"{c['id']}/{l['nr']}: kein Titel")
        if c["kind"] == "stream":
            if not l.get("video", "").startswith("https://"):
                problems.append(f"{c['id']}/{l['nr']}: keine Video-URL")
            cap = ROOT/l.get("captionLocal", "")
            if not cap.exists():
                problems.append(f"{c['id']}/{l['nr']}: Untertitel fehlt: {l.get('captionLocal')}")
            if not l.get("durationMs"):
                problems.append(f"{c['id']}/{l['nr']}: keine Dauer")
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
    # testet der Quiz das Erraten des Musters statt das Verstaendnis.
    pos = collections.Counter(q["answer"] for b in quiz.values() for q in b["questions"])
    tot = sum(pos.values())
    if tot:
        top = max(pos.values()) / tot
        line = f"{c['id']}: {tot} Fragen, haeufigste Antwortposition {top*100:.0f} %"
        if top > 0.45:
            problems.append(line + " - zu einseitig, bitte mischen")
        else:
            warn.append(line)

tot_q = 0
for c in data["courses"]:
    qf = ROOT/"data"/"quiz"/f"{c['id']}.json"
    if qf.exists():
        tot_q += sum(len(v["questions"]) for v in json.loads(qf.read_text()).values())

print(f"{len(data['courses'])} Kurse, {sum(len(c['lessons']) for c in data['courses'])} Lektionen, {tot_q} Fragen")
for w in warn: print("  HINWEIS:", w)
if problems:
    print(f"\n{len(problems)} PROBLEME:")
    for p in problems[:30]: print("  ✗", p)
    sys.exit(1)
print("✅ Alle Prüfungen bestanden")
