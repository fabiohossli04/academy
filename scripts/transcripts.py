#!/usr/bin/env python3
"""Laedt die oeffentlichen Untertitel und macht daraus lesbaren Fliesstext.
Rein lokal als Arbeitsgrundlage fuer die Testfragen - wird nicht weitergegeben."""
import json, pathlib, re, subprocess, concurrent.futures as cf

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = json.loads((ROOT / "data" / "courses-raw.json").read_text())

def vtt_to_text(vtt):
    out, seen = [], None
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line != seen:          # Doppelzeilen aus rollenden Untertiteln raus
            out.append(line)
            seen = line
    return " ".join(out)

def fetch(job):
    course, lesson = job
    dest = ROOT / "transcripts" / course["id"] / f"{lesson['nr']:02d}.txt"
    if dest.exists() and dest.with_suffix(".vtt").exists() and dest.stat().st_size > 1000:
        return f"vorhanden {dest.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["curl", "-sL", lesson["caption"]], capture_output=True, text=True)
    if p.returncode != 0 or "-->" not in p.stdout:
        return f"FEHLER {course['id']}/{lesson['nr']}"
    dest.with_suffix(".vtt").write_text(p.stdout)   # Original fuer den Player (CORS!)
    text = vtt_to_text(p.stdout)
    dest.write_text(text)
    return f"ok {course['id']}/{lesson['nr']:02d} {len(text)} Zeichen"

jobs = [(c, l) for c in RAW for l in c["lessons"] if l.get("caption")]
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(fetch, jobs))
bad = [r for r in res if r.startswith("FEHLER")]
print(f"{len(res)} Transkripte, {len(bad)} Fehler")
for b in bad: print(" ", b)
tot = sum(f.stat().st_size for f in (ROOT/"transcripts").rglob("*.txt"))
print(f"Gesamt {tot/1e6:.1f} MB auf der Platte")
