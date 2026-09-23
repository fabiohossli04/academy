#!/usr/bin/env python3
"""Zieht Kurs-Metadaten (Video- und Untertitel-URLs) aus dem oeffentlichen ETH-Videoportal.
Laedt KEINE Videos herunter - die werden spaeter direkt vom ETH-Server gestreamt."""
import json, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GQL = "https://video.ethz.ch/graphql"

Q = '''{ r: realmByPath(path: "%s") { blocks { ... on SeriesBlock { series {
  title description
  entries { ... on AuthorizedEvent {
    opencastId title created creators
    syncedData { duration }
    authorizedData { captions { uri lang } tracks { uri mimetype resolution } }
  } } } } } } }'''

def gql(query):
    p = subprocess.run(["curl","-s","-X","POST",GQL,"-H","Content-Type: application/json",
                        "-d",json.dumps({"query":query})], capture_output=True, text=True)
    if not p.stdout.strip().startswith("{"):
        raise SystemExit(f"GraphQL-Fehler: {p.stdout[:300]}")
    return json.loads(p.stdout)

def best_track(tracks):
    """Hoechste Aufloesung, die nicht groesser als 1280x720 ist - spart Bandbreite,
    bleibt aber lesbar fuer Folien."""
    vids = [t for t in tracks if t.get("mimetype") == "video/mp4" and t.get("resolution")]
    if not vids:
        return tracks[0]["uri"] if tracks else None
    def key(t):
        w, h = t["resolution"]
        return (0, -abs(h - 720)) if h <= 720 else (1, h)
    return sorted(vids, key=key)[0]["uri"]

def pull(path, course_id, title_de, lang):
    d = gql(Q % path)["data"]["r"]
    if not d:
        raise SystemExit(f"Realm nicht gefunden: {path}")
    series = [b["series"] for b in d["blocks"] if b.get("series")]
    if not series:
        raise SystemExit(f"Keine Serie unter {path}")
    s = series[0]
    lessons = []
    for e in s["entries"]:
        ad = e.get("authorizedData")
        if not ad or not ad.get("tracks"):
            continue  # nicht oeffentlich abspielbar
        caps = ad.get("captions") or []
        lessons.append({
            "opencastId": e["opencastId"],
            "created": e["created"],
            "durationMs": (e.get("syncedData") or {}).get("duration") or 0,
            "creators": e.get("creators") or [],
            "video": best_track(ad["tracks"]),
            "caption": caps[0]["uri"] if caps else None,
            "captionLang": caps[0]["lang"] if caps else None,
        })
    lessons.sort(key=lambda x: x["created"])
    for i, l in enumerate(lessons, 1):
        l["nr"] = i
    return {
        "id": course_id,
        "title": title_de,
        "sourceTitle": s["title"],
        "lang": lang,
        "portalUrl": f"https://video.ethz.ch{path}",
        "lessons": lessons,
    }

COURSES = [
    ("/lectures/d-infk/2023/autumn/252-0057-00L", "theoinf",
     "Theoretische Informatik", "de"),
    ("/lectures/d-itet/2025/spring/227-0003-10L", "architektur",
     "Digital Design und Rechnerarchitektur", "en"),
]

if __name__ == "__main__":
    out = []
    for path, cid, title, lang in COURSES:
        c = pull(path, cid, title, lang)
        hrs = sum(l["durationMs"] for l in c["lessons"]) / 3600000
        caps = sum(1 for l in c["lessons"] if l["caption"])
        print(f"{c['title']}: {len(c['lessons'])} Lektionen, {hrs:.1f} h, {caps} mit Untertitel")
        out.append(c)
    dest = ROOT / "data" / "courses-raw.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("geschrieben:", dest)
