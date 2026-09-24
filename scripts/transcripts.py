#!/usr/bin/env python3
"""Lädt öffentliche Untertitel nach opencastId und erzeugt lesbaren Fließtext.
Rein lokale Arbeitsgrundlage; auch noch nicht kuratierte Aufnahmen werden geladen."""
import json, os, pathlib, re, subprocess, sys, tempfile, concurrent.futures as cf

ROOT = pathlib.Path(__file__).resolve().parent.parent

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

def replace_bytes(dest, content):
    """Auch bei Abbruch bleibt eine vorhandene Datei vollständig erhalten."""
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent, prefix=f".{dest.name}.", delete=False) as f:
            temp = pathlib.Path(f.name)
            f.write(content)
        os.replace(temp, dest)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()

def fetch(job):
    cid, clip, old_url = job
    oid, url = clip["opencastId"], clip.get("caption")
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", oid):
            raise ValueError("ungültige opencastId")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("keine HTTPS-Untertitel-URL")
        dest = ROOT / "transcripts" / cid / f"{oid}.vtt"
        txt = dest.with_suffix(".txt")
        if old_url == url and dest.is_file() and txt.is_file() and txt.stat().st_size:
            content = dest.read_bytes()
            if content.lstrip().startswith(b"WEBVTT") and b"-->" in content:
                return cid, oid, url, None, False
        p = subprocess.run(["curl", "-fsSL", "--proto", "=https", "--proto-redir", "=https",
                            "--connect-timeout", "15", "--max-time", "90", "--retry", "2", url],
                           capture_output=True)
        if p.returncode:
            raise ValueError(f"Abruf fehlgeschlagen (curl {p.returncode})")
        vtt = p.stdout.decode("utf-8-sig")
        if not vtt.lstrip().startswith("WEBVTT") or "-->" not in vtt:
            raise ValueError("keine gültigen VTT-Untertitel")
        text = vtt_to_text(vtt)
        if not text:
            raise ValueError("leerer Untertiteltext")
        dest.parent.mkdir(parents=True, exist_ok=True)
        replace_bytes(dest, p.stdout)  # frisch vom Portal, niemals aus alten NN.vtt kopieren
        replace_bytes(txt, text.encode("utf-8"))
        return cid, oid, url, None, True
    except (OSError, ValueError, TypeError) as err:
        return cid, oid, url, f"FEHLER {cid}/{oid}: {err}", False

def main():
    courses = json.loads((ROOT / "data" / "lessons.json").read_text(encoding="utf-8"))
    raw = {c["id"]: c for c in json.loads((ROOT / "data" / "courses-raw.json").read_text(encoding="utf-8"))}
    manifests, jobs = {}, []
    for cid, meta in courses.items():
        if meta.get("captions", True) is False:
            continue
        manifest = ROOT / "transcripts" / cid / "manifest.json"
        manifests[cid] = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        for clip in raw[cid]["lessons"]:
            jobs.append((cid, clip, manifests[cid].get(clip["opencastId"])))
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch, jobs))
    bad = [err for _, _, _, err, _ in results if err]
    for cid, oid, url, err, _ in results:
        if err is None:
            manifests[cid][oid] = url
        else:
            manifests[cid].pop(oid, None)  # ein fehlgeschlagener Abruf ist niemals ein Cache-Treffer
    for cid, manifest in manifests.items():
        dest = ROOT / "transcripts" / cid / "manifest.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        replace_bytes(dest, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"{len(results)} Transkripte, {len(bad)} Fehler")
    print(f"Frisch geladen: {sum(fresh for _, _, _, _, fresh in results)}")
    for err in bad:
        print(" ", err)
    total = sum(f.stat().st_size for f in (ROOT / "transcripts").rglob("*.txt"))
    print(f"Gesamt {total/1e6:.1f} MB auf der Platte")
    return 1 if bad else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"✗ Untertitel konnten nicht geladen werden: {err}")
        sys.exit(1)
