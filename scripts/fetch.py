#!/usr/bin/env python3
"""Zieht Metadaten aus dem öffentlichen ETH-Videoportal, niemals Videos.
Die Kursliste und Portal-Pfade stehen ausschließlich in data/lessons.json."""
import argparse, itertools, json, subprocess, sys, pathlib

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
    p = subprocess.run(["curl", "-fsS", "--connect-timeout", "15", "--max-time", "90",
                        "--retry", "2", "-X", "POST", GQL, "-H", "Content-Type: application/json",
                        "-d",json.dumps({"query":query})], capture_output=True, text=True)
    if p.returncode:
        raise ValueError(f"GraphQL-Abruf fehlgeschlagen (curl {p.returncode})")
    data = json.loads(p.stdout)
    if data.get("errors") or not data.get("data"):
        raise ValueError("GraphQL-Abfrage fehlgeschlagen")
    return data

def best_track(tracks):
    """Höchste Auflösung bis 720p, sonst kleinste darüber."""
    vids = [t for t in tracks if t.get("mimetype") == "video/mp4" and t.get("resolution")]
    if not vids:
        return tracks[0]["uri"] if tracks else None
    def key(t):
        w, h = t["resolution"]
        return (0, -h) if h <= 720 else (1, h)
    return sorted(vids, key=key)[0]["uri"]

def selftest():
    for heights, expected in (([360, 720, 1080], 720), ([360, 480], 480), ([1080], 1080), ([2160, 1080], 1080)):
        tracks = [{"uri": f"https://example.invalid/{h}.mp4", "mimetype": "video/mp4",
                   "resolution": [h * 16 // 9, h]} for h in heights]
        for order in itertools.permutations(tracks):
            assert best_track(order) == f"https://example.invalid/{expected}.mp4", heights
        print(f"✓ {heights} → {expected}p (jede Reihenfolge)")
    tracks = [{"uri": "https://example.invalid/audio", "mimetype": "audio/mp4", "resolution": [1280, 720]},
              {"uri": "https://example.invalid/video", "mimetype": "video/mp4", "resolution": None}]
    for order in itertools.permutations(tracks):
        assert best_track(order) == order[0]["uri"]
    assert best_track([]) is None
    print("✓ Ohne MP4-Auflösung: erste Spur; ohne Spuren: keine URL")
    print("✅ Alle Selbsttests bestanden (ohne Netz)")

def pull(path, course_id, title, lang):
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
            continue  # nicht öffentlich abspielbar; kuratierte IDs fehlen dann beim Bauen
        caps = ad.get("captions") or []
        lessons.append({
            "opencastId": e["opencastId"],
            "title": e["title"],
            "created": e["created"],
            "durationMs": (e.get("syncedData") or {}).get("duration") or 0,
            "creators": e.get("creators") or [],
            "video": best_track(ad["tracks"]),
            "caption": caps[0]["uri"] if caps else None,
            "captionLang": caps[0]["lang"] if caps else None,
        })
    lessons.sort(key=lambda x: x["created"])
    return {
        "id": course_id,
        "title": title,
        "sourceTitle": s["title"],
        "lang": lang,
        "portalUrl": f"https://video.ethz.ch{path}",
        "lessons": lessons,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="Spurauswahl ohne Netz prüfen")
    if parser.parse_args().selftest:
        selftest()
        return
    courses = json.loads((ROOT / "data" / "lessons.json").read_text(encoding="utf-8"))
    out = []
    for cid, meta in courses.items():
        c = pull(meta["portal"], cid, meta["title"], meta["lang"])
        hrs = sum(l["durationMs"] for l in c["lessons"]) / 3600000
        caps = sum(1 for l in c["lessons"] if l["caption"])
        print(f"{c['title']}: {len(c['lessons'])} Aufnahmen, {hrs:.1f} h, {caps} mit Untertitel")
        out.append(c)
    dest = ROOT / "data" / "courses-raw.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("geschrieben:", dest)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"✗ Metadaten konnten nicht abgerufen werden: {err}")
        sys.exit(1)
