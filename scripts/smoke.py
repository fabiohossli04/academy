#!/usr/bin/env python3
"""Smoke-Test der Oberfläche: alle Routen hell/dunkel auf Desktop und Handy, Test per Tastatur,
"geschaut" ohne Video-Neuaufbau, kein Download-Menü, zwei Tabs, Einstellungen.
Startet einen eigenen lokalen Server. Standardlauf offline: *.mp4 wird abgebrochen.
Mit --stream zusätzlich echte Wiedergabe im stummen <video>, ohne Speicherung oder Aufzeichnung.
Braucht Playwright:  pip install playwright && python3 -m playwright install chromium
Aufruf: python3 scripts/smoke.py [--stream]   (Exit 0 = alles grün)"""
import argparse, copy, datetime, functools, http.server, json, os, pathlib, shutil, socket, subprocess, sys, tempfile, threading, time
from contextlib import contextmanager
from urllib.request import urlopen
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright fehlt: pip install playwright && python3 -m playwright install chromium")

ROOT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--stream", action="store_true", help="ETH-Videos zusätzlich im Browser streamen")
ARGS = parser.parse_args()

# Die Fixture entsteht nur im Speicher; die parallel bearbeiteten Daten bleiben unberührt.
ACADEMY = json.loads((ROOT / "data/academy.json").read_text())
THEOINF = next(c for c in ACADEMY["courses"] if c["id"] == "theoinf")
CLIPS = []
for l in THEOINF["lessons"]:
    for clip in l.get("clips") or [l]:
        CLIPS.append({
            **{k: clip.get(k) for k in ("video", "captionLocal", "captionLang", "durationMs")},
            "opencastId": clip.get("opencastId") or f"fixture-{len(CLIPS)+1}",
            "title": f"Clip {len(CLIPS)+1} · Übung <Grundlagen> & Anwendung",
        })
        if len(CLIPS) == 3: break
    if len(CLIPS) == 3: break
RAW = json.loads((ROOT / "data/courses-raw.json").read_text())
WITHOUT_CAPTIONS = next((clip for c in RAW if c["id"] == "linalg"
                         for clip in c["lessons"] if not clip.get("caption")), None)
if WITHOUT_CAPTIONS is None:
    sys.exit("Keine linalg-Aufnahme ohne Untertitel in courses-raw.json; zuerst fetch.py ausführen")
MIXED_CLIPS = [CLIPS[0], {
    **{k: WITHOUT_CAPTIONS[k] for k in ("opencastId", "video", "durationMs")},
    "title": "Clip ohne Untertitel",
}, CLIPS[2]]
FIXTURE = {
    "id": "fixture", "kind": "stream", "running": True, "lang": "de",
    "title": "Laufender Clip-Kurs", "subtitle": "Synthetischer Testkurs",
    "why": "Clips, Fortsetzen und Prüfungssperre prüfen.", "portalUrl": THEOINF["portalUrl"],
    "lessons": [
        {"nr": 1, "title": "Woche 1 · Drei Clips", "topics": ["Clips", "Fortsetzen"],
         "durationMs": sum(c["durationMs"] for c in CLIPS), "clips": CLIPS},
        {"nr": 2, "title": "Woche 2 · Ein Clip", "topics": ["Wiederholen"],
         "durationMs": CLIPS[0]["durationMs"], "clips": [CLIPS[0]]},
        {"nr": 3, "title": "Woche 3 · Gemischte Untertitel", "topics": ["Untertitel", "Fortsetzen"],
         "durationMs": sum(c["durationMs"] for c in MIXED_CLIPS), "clips": MIXED_CLIPS},
    ],
}
ACADEMY["courses"].append(FIXTURE)
# Streaming der Clip-Folge an einer echten Clip-Lektion mit Untertiteln, falls vorhanden: Lange Einzelvideos
# als Clips laden ihre Metadaten beim Wechsel mitunter zu langsam für einen stabilen Test.
SEQ_CID, SEQ = next(((c["id"], l) for c in ACADEMY["courses"] if c["id"] != "fixture"
                     for l in c["lessons"] if len(l.get("clips") or []) > 1 and
                     all(clip.get("captionLocal") for clip in l["clips"])), ("fixture", FIXTURE["lessons"][0]))
SEQ_KEY = f"{SEQ_CID}/{SEQ['nr']}"
BARE_CID, BARE_LESSON, BARE_INDEX = next(((c["id"], l, i) for c in ACADEMY["courses"] if c["id"] == "linalg"
                                        for l in c["lessons"] for i, clip in enumerate(l["clips"])
                                        if "captionLocal" not in clip and "captionLang" not in clip),
                                       ("fixture", FIXTURE["lessons"][2], 1))
BARE_KEY = f"{BARE_CID}/{BARE_LESSON['nr']}"
FIXTURE_QUIZ = {str(nr): {"questions": [
    {"q": f"Was ergibt {nr} + {i}?", "options": [str(nr+i+j) for j in range(4)],
     "answer": 0, "why": f"Die Summe ist {nr+i}."} for i in range(1, 6)
]} for nr in (l["nr"] for l in FIXTURE["lessons"])}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}/"
today = datetime.date.today()
d = lambda n: (today - datetime.timedelta(days=n)).isoformat()
SEEDED = {
    "lessons": {"theoinf/1": {"watched": True, "pos": 5000}, "theoinf/3": {"pos": 1900}},
    "quiz": {"theoinf/1": {"best": 1, "passed": True, "attempts": 1}},
    "exam": {}, "days": {d(0): 1140, d(1): 1900}, "last": "theoinf/3", "dailyMinutes": 30, "rate": 1.25,
}
fails, notes = [], []

def check(cond, msg):
    line = ("ok   " if cond else "FAIL ") + msg
    (notes if cond else fails).append(line)
    print(line, flush=True)

def fixture_routes(page, legacy=False):
    data = ACADEMY
    if legacy:
        data = copy.deepcopy(ACADEMY)
        single = data["courses"][-1]["lessons"][1]
        single.update(single.pop("clips")[0])
    page.route("**/data/academy.json", lambda r: r.fulfill(content_type="application/json", body=json.dumps(data)))
    page.route("**/data/quiz/fixture.json", lambda r: r.fulfill(content_type="application/json", body=json.dumps(FIXTURE_QUIZ)))

def new_page(b, state, vp=(1440, 900), scheme="light", stream=False, legacy=False, fixtures=True):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, color_scheme=scheme,
                        locale="de-CH", accept_downloads=False, service_workers="block")
    if state is not None:
        ctx.add_init_script(f"localStorage.setItem('academy.v1', {json.dumps(json.dumps(state))})")
    page = ctx.new_page()
    errs = watch_errors(page, stream)
    if fixtures: fixture_routes(page, legacy)
    # Routing deaktiviert auch den HTTP-Cache. Keine Downloads, HARs, Videos oder Screenshots.
    page.route("**/*.mp4*", lambda r: r.continue_() if stream else r.abort())
    return ctx, page, errs

def watch_errors(page, stream=False):
    errs = []
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}")
            if m.type == "error" and not (
                (not stream and ".mp4" in m.location.get("url", "")) or
                (m.location.get("url", "").endswith("/api/tutor/health") and "404" in m.text)
            ) else None)
    return errs

def open_route(page, hsh):
    page.goto(BASE + hsh)
    page.wait_for_selector("main#view > *", timeout=8000)
    page.wait_for_timeout(150)

def fixture_checks(b):
    state = copy.deepcopy(SEEDED)
    state["quiz"].update({f"fixture/{l['nr']}": {"passed": True, "best": 1, "attempts": 1} for l in FIXTURE["lessons"]})
    ctx, page, errs = new_page(b, state)
    open_route(page, "#/lesson/fixture/1")
    check(page.locator(".clip-row").count() == 3, "Fixture: Clip-Liste mit 3 Einträgen")
    check(page.locator(".clip-row .lnum").all_text_contents() == ["1", "2", "3"], "Fixture: Clips sind nummeriert")
    check(page.locator(".clip-title").first.text_content() == CLIPS[0]["title"] and page.locator(".clip-title > *").count() == 0,
          "Fixture: Clip-Titel werden als Text escaped")
    page.click('[data-clip="1"]')
    check(page.locator('video source').get_attribute("src") == CLIPS[1]["video"], "Fixture: Clip 2 tauscht <source>")
    check(page.locator('video track').get_attribute("src") == CLIPS[1]["captionLocal"] and
          page.locator('video track').get_attribute("srclang") == CLIPS[1]["captionLang"][:2], "Fixture: Clip 2 tauscht <track> und Sprache")
    check(page.locator('[data-clip="1"][aria-current="true"]').count() == 1, "Fixture: Clip 2 ist aktuell")
    check(page.locator('[data-clip="0"] .clip-state').text_content() == "Geschaut" and
          page.locator('[data-clip="2"] .clip-state').text_content() == "Offen", "Fixture: Zustände geschaut / aktuell / offen")
    offset = CLIPS[0]["durationMs"] / 1000
    stored_pos = lambda: page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['fixture/1'].pos")
    check(abs(stored_pos() - offset) < .01, "Fixture: Clip-Wahl sichert die Gesamtposition")
    page.click("#back10")
    check(page.locator('[data-clip="0"][aria-current="true"]').count() == 1 and abs(stored_pos() - (offset-10)) < .01,
          "Fixture: −10 s über die Clip-Grenze")
    page.click("#fwd10")
    check(page.locator('[data-clip="1"][aria-current="true"]').count() == 1 and abs(stored_pos() - offset) < .01,
          "Fixture: +10 s über die Clip-Grenze")
    page.click('[data-clip="2"]')
    page.click('[data-clip="1"]')
    page.wait_for_selector("#playerError:not([hidden])")
    check(page.locator("#playerError a").get_attribute("href") == FIXTURE["portalUrl"], "Fixture: Ladefehler zeigt den ETH-Portallink")
    check(abs(stored_pos() - offset) < .01, "Fixture: schnelle Clip-Wahl und Ladefehler erhalten die Position")
    check(page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).days") == SEEDED["days"],
          "Fixture: Auswahl, Sprünge und Ladefehler zählen keine Lernzeit")
    open_route(page, "#/")
    check(page.locator('.course-card[href="#/course/fixture"] .running').text_content() == "Läuft", "Fixture: Läuft-Tag auf Kurskarte")
    open_route(page, "#/course/fixture")
    check(page.locator(".course-head .running").text_content() == "Läuft", "Fixture: Läuft-Tag auf Kursseite")
    check(page.locator(".exam button").is_disabled() and
          "Die Abschlussprüfung öffnet, wenn der Kurs abgeschlossen ist." in page.locator(".exam").text_content(),
          "Fixture: Prüfung trotz bestandener Tests gesperrt und erklärt")
    open_route(page, "#/exam/fixture")
    page.wait_for_url("**/#/course/fixture")
    check(page.locator(".course-head").count() == 1, "Fixture: Prüfungsroute leitet zur Kursseite um")
    check(not errs, f"Fixture: keine Konsolen-/Seitenfehler {errs[:3]}")
    ctx.close()

    state["lessons"]["fixture/1"] = {"pos": offset + 42}
    ctx, page, errs = new_page(b, state)
    open_route(page, "#/lesson/fixture/1")
    check(page.locator('[data-clip="1"][aria-current="true"]').count() == 1 and
          page.locator("video source").get_attribute("src") == CLIPS[1]["video"], "Fixture: Gesamtposition in Clip 2 setzt dort fort")
    seconds = round(offset + 42)
    check(f"fortsetzen bei {seconds//60}:{seconds%60:02d}" in page.locator(".lede").text_content(),
          "Fixture: Fortsetzen-Hinweis zeigt Gesamtzeit")
    page.click('a.back')
    check(abs(stored_pos() - (offset+42)) < .01, "Fixture: Verlassen vor Metadaten erhält den gespeicherten Stand")
    progress = page.locator('.lrow[href="#/lesson/fixture/1"] [role="progressbar"]').get_attribute("aria-valuenow")
    check(int(progress) == round((offset+42)*1000/FIXTURE["lessons"][0]["durationMs"]*100),
          "Fixture: Fortschrittsbalken nutzt die Gesamtdauer")
    check(not errs, f"Fortsetzen: keine Konsolen-/Seitenfehler {errs[:3]}")
    ctx.close()

    for legacy in (False, True):
        ctx, page, errs = new_page(b, SEEDED, legacy=legacy)
        open_route(page, "#/lesson/fixture/2")
        check(page.locator(".clip-list").count() == 0 and page.locator("video source").get_attribute("src") == CLIPS[0]["video"] and
              page.locator("video track").get_attribute("src") == CLIPS[0]["captionLocal"],
              f"Einzel-Clip: {'altes' if legacy else 'neues'} Format ohne Clip-Liste")
        check(not errs, f"Einzel-Clip ({'alt' if legacy else 'neu'}): keine Fehler {errs[:3]}")
        ctx.close()

    state = copy.deepcopy(SEEDED)
    for c in ACADEMY["courses"]:
        for l in c["lessons"]:
            state["lessons"][f'{c["id"]}/{l["nr"]}'] = {"watched": True}
            state["quiz"][f'{c["id"]}/{l["nr"]}'] = {"passed": True}
        if c["id"] != "fixture": state["exam"][c["id"]] = {"passed": True}
    state["last"] = "fixture/2"
    ctx, page, errs = new_page(b, state)
    open_route(page, "#/")
    check(page.locator('.today a[href="#/exam/fixture"]').count() == 0 and "Alles erledigt" in page.locator(".today").text_content(),
          "Fixture: nextStep schlägt die laufende Prüfung auch zuletzt nicht vor")
    check(not errs, f"Nächster Schritt: keine Fehler {errs[:3]}")
    ctx.close()

    ctx, page, errs = new_page(b, SEEDED)
    open_route(page, "#/lesson/fixture/3")
    check(page.locator(".clip-row").count() == 3, "Gemischte Untertitel: drei Clips in Lektion 3")
    for i in (0, 1, 2, 1, 0):
        page.click(f'[data-clip="{i}"]')
        clip = MIXED_CLIPS[i]
        check(page.locator(f'[data-clip="{i}"][aria-current="true"]').count() == 1 and
              page.locator("video source").get_attribute("src") == clip["video"],
              f"Gemischte Untertitel: Wechsel zu Clip {i+1}")
        track = page.locator("video track")
        if clip.get("captionLocal"):
            check(track.count() == 1 and track.get_attribute("src") == clip["captionLocal"] and
                  track.get_attribute("srclang") == clip["captionLang"][:2],
                  f"Gemischte Untertitel: Clip {i+1} hat seinen Track und seine Sprache")
        else:
            check(track.count() == 0, "Gemischte Untertitel: Clip 2 hat kein track-Element")
    check(not errs, f"Gemischte Untertitel: keine Fehler {errs[:3]}")
    ctx.close()

    state = copy.deepcopy(SEEDED)
    pos = MIXED_CLIPS[0]["durationMs"] / 1000 + 42
    state["lessons"]["fixture/3"] = {"pos": pos}
    ctx, page, errs = new_page(b, state)
    open_route(page, "#/lesson/fixture/3")
    check(page.locator('[data-clip="1"][aria-current="true"]').count() == 1 and
          page.locator("video source").get_attribute("src") == MIXED_CLIPS[1]["video"] and
          page.locator("video track").count() == 0, "Gemischte Untertitel: Fortsetzen im Clip ohne Untertitel")
    seconds = round(pos)
    check(f"fortsetzen bei {seconds//60}:{seconds%60:02d}" in page.locator(".lede").text_content(),
          "Gemischte Untertitel: Fortsetzen-Hinweis zeigt die gespeicherte Gesamtposition")
    page.click("a.back")
    saved = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['fixture/3'].pos")
    check(abs(saved - pos) < .01, "Gemischte Untertitel: Verlassen erhält die Position ohne Metadaten")
    page.click('a[href="#/lesson/fixture/3"]')
    page.wait_for_selector("video")
    check(page.locator('[data-clip="1"][aria-current="true"]').count() == 1 and page.locator("video track").count() == 0,
          "Gemischte Untertitel: Rückkehr setzt erneut ohne track-Element fort")
    check(not errs, f"Fortsetzen ohne Untertitel: keine Fehler {errs[:3]}")
    ctx.close()

def video_ready(page, pos=None):
    page.evaluate("document.querySelector('video').muted = true")
    page.wait_for_function("""pos => { const v = document.querySelector('video');
        return v.readyState >= 3 && !v.seeking && (pos === null || Math.abs(v.currentTime-pos) < 1); }""", arg=pos, timeout=60000)

def play_ms(page, ms, pause=True):
    page.evaluate("""async ([ms, pause]) => {
        const v = document.querySelector('video'); v.muted = true;
        let timer;
        try { await Promise.race([v.play(), new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('Wiedergabe startet nicht')), 30000);
        })]); } finally { clearTimeout(timer); }
        await new Promise(resolve => setTimeout(resolve, ms));
        if (pause) v.pause();
    }""", [ms, pause])

def stream_checks(b):
    for case in ("Fortsetzen", "Clip-Folge", "Lernzeit", "Geschaut", "Ohne Untertitel"):
        print(f"Stream: {case} …", flush=True)
        state = copy.deepcopy(SEEDED)
        state["rate"] = 1.5 if case in ("Clip-Folge", "Lernzeit") else 1.25
        if case == "Ohne Untertitel":
            offset = sum(c["durationMs"] for c in BARE_LESSON["clips"][:BARE_INDEX]) / 1000
            state["lessons"][BARE_KEY] = {"pos": offset + 42}
        ctx, page, errs = new_page(b, state, stream=True)
        try:
            if case == "Fortsetzen":
                open_route(page, "#/lesson/theoinf/3")
                pos = state["lessons"]["theoinf/3"]["pos"]
                video_ready(page, pos)
                page.wait_for_function("document.querySelector('video').textTracks[0]?.cues?.length > 0", timeout=30000)
                check(abs(page.locator("video").evaluate("v => v.currentTime") - pos) < 1, "Stream: theoinf/3 setzt an gespeicherter Position fort")
                check(page.locator("video").evaluate("v => v.textTracks[0].cues.length") > 0, "Stream: Untertitel-Cues sind geladen")
                start = page.locator("video").evaluate("v => v.currentTime")
                play_ms(page, 3000)
                check(page.locator("video").evaluate("v => v.currentTime") > start + 2, "Stream: nach 3 s Wiedergabe läuft die Videozeit")
            elif case == "Clip-Folge":
                open_route(page, f"#/lesson/{SEQ_KEY}")
                video_ready(page, 0)
                page.evaluate("""() => { const v = document.querySelector('video');
                    window.__mediaEvents = [];
                    for (const type of ['seeking', 'seeked', 'ended', 'emptied', 'loadedmetadata', 'playing', 'pause', 'waiting'])
                        v.addEventListener(type, () => window.__mediaEvents.push({ereignis:type,
                            ms:Math.round(performance.now() - window.__clipStart), zeit:v.currentTime,
                            clip:document.querySelector('.clip-row[aria-current]')?.dataset.clip}));
                    window.__clipStart = performance.now(); v.currentTime = v.duration - 2;
                    v.play().catch(() => {}); }""")
                page.wait_for_function("""() => { const v = document.querySelector('video');
                    return document.querySelector('[data-clip="1"][aria-current="true"]') &&
                        v.readyState >= 3 && !v.paused && !v.seeking && v.currentTime > .05; }""", timeout=20000)
                elapsed = page.evaluate("performance.now() - window.__clipStart")
                page.locator("video").evaluate("v => v.pause()")
                check(elapsed <= 20000, "Stream: spätestens nach 20 s läuft automatisch Clip 2")
                check(page.locator("video").evaluate("v => v.playbackRate === 1.5 && v.defaultPlaybackRate === 1.5"),
                      "Stream: Clip-Wechsel erhält Tempo und Standardtempo 1,5")
                check(page.locator("video source").get_attribute("src") == SEQ["clips"][1]["video"] and
                      page.locator("video track").get_attribute("src") == SEQ["clips"][1]["captionLocal"], "Stream: Folgeclip hat eigenes Video und Untertitel")
                check(not page.evaluate(f"!!JSON.parse(localStorage.getItem('academy.v1')).lessons['{SEQ_KEY}'].watched"),
                      "Stream: Ende von Clip 1 markiert nicht die ganze Lektion")
                page.click(f'[data-clip="{len(SEQ["clips"]) - 1}"]')
                video_ready(page, 0)
                page.locator("video").evaluate("v => { v.currentTime = v.duration - .5; v.play().catch(() => {}); }")
                page.wait_for_function("document.querySelector('video').ended", timeout=20000)
                stored = page.evaluate(f"JSON.parse(localStorage.getItem('academy.v1')).lessons['{SEQ_KEY}']")
                check(stored.get("watched") and abs(stored["pos"] - SEQ["durationMs"]/1000) < .01,
                      "Stream: Ende des letzten Clips speichert geschaut und Gesamtposition")
            elif case == "Lernzeit":
                open_route(page, "#/lesson/fixture/2")
                video_ready(page, 0)
                before = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).days[new Date().toLocaleDateString('sv-SE')] || 0")
                play_ms(page, 2000, pause=False)
                page.click("#fwd10")
                page.wait_for_function("""() => { const v = document.querySelector('video');
                    return v.currentTime >= 10 && v.readyState >= 3 && !v.paused && !v.seeking; }""", timeout=60000)
                play_ms(page, 1000)
                after = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).days[new Date().toLocaleDateString('sv-SE')] || 0")
                check(2.5 <= after-before <= 4, f"Stream: Lernzeit bei 1,5× mit +10-s-Sprung: {after-before:.2f} s (höchstens 4 s)")
                check(page.locator("video").evaluate("v => v.currentTime >= 14 && v.playbackRate === 1.5 && v.defaultPlaybackRate === 1.5"),
                      "Stream: +10 s springt und erhält Tempo 1,5")
                page.wait_for_timeout(1100)
                paused = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).days[new Date().toLocaleDateString('sv-SE')] || 0")
                check(abs(paused-after) < .05, "Stream: pausierte Zeit zählt nicht")
            elif case == "Ohne Untertitel":
                open_route(page, f"#/lesson/{BARE_KEY}")
                video_ready(page, 42)
                check(page.locator("video source").get_attribute("src") == BARE_LESSON["clips"][BARE_INDEX]["video"],
                      f"Stream: {BARE_KEY} setzt im Clip ohne Untertitel fort")
                check(page.locator("video track").count() == 0, "Stream: ohne Untertitel kein track-Element")
                start = page.locator("video").evaluate("v => v.currentTime")
                play_ms(page, 3000)
                check(page.locator("video").evaluate("v => v.currentTime") > start + 2,
                      "Stream: Clip ohne Untertitel spielt nach 3 s weiter")
                check(page.locator("#playerError").is_hidden() and
                      page.locator("video").evaluate("v => v.error === null && v.textTracks.length === 0") and
                      page.locator("video track").count() == 0, "Stream: Wiedergabe ohne Fehler und ohne Track")
            else:
                open_route(page, "#/lesson/fixture/2")
                video_ready(page, 0)
                page.locator("video").evaluate("v => { v.currentTime = v.duration * .93; }")
                page.wait_for_function("!document.querySelector('video').seeking", timeout=60000)
                play_ms(page, 2000)
                check(page.locator(".clip-list").count() == 0 and
                      page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['fixture/2'].watched === true"),
                      "Stream: Einzel-Clip bei 93 % nach 2 s als geschaut gespeichert")
                check(page.locator("#markDone").get_attribute("aria-pressed") == "true", "Stream: Geschaut-Knopf aktualisiert sich")
        except Exception as e:
            media = page.locator("video").evaluate("""v => ({bereit:v.readyState, netz:v.networkState,
                zeit:v.currentTime, dauer:v.duration, pausiert:v.paused, sucht:v.seeking, fehler:v.error?.code,
                ereignisse:window.__mediaEvents?.slice(-12)})""") if page.locator("video").count() else {}
            check(False, f"Stream {case}: {str(e).splitlines()[0]} · Medienstatus {media}")
        finally:
            check(not errs, f"Stream {case}: keine Konsolen-/Seitenfehler {errs[:3]}")
            ctx.close()

# Browserseitiger Vertrags-Doppelgänger für Modus A. Kein Claude-Prozess, kein Netz.
# Anders als route.fulfill liefert dieser ReadableStream echte, kontrollierte Chunks.
TUTOR_MOCK = r"""(() => {
    const original = window.fetch.bind(window), encoder = new TextEncoder();
    window.__tutorRequests = []; window.__tutorStreams = []; window.__healthCalls = 0;
    window.__httpStatuses = []; window.__tutorContext = 'no_captions';
    window.__tutorRaw = (text, split = false, index = window.__tutorStreams.length - 1) => {
        const bytes = encoder.encode(text), stream = window.__tutorStreams[index];
        if (split) for (let i = 0; i < bytes.length; i++) stream.enqueue(bytes.slice(i, i+1));
        else stream.enqueue(bytes);
    };
    window.__tutorEvent = (name, data, split = false) =>
        window.__tutorRaw(`event: ${name}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`, split);
    window.fetch = async (url, options = {}) => {
        if (url === '/api/tutor/health') {
            window.__healthCalls++;
            return new Response(JSON.stringify({ok:true, token:window.__healthCalls === 1 ? 'abc123' : 'def456',
                models:[{id:'opus', label:'Gründlich (Opus 5)'}, {id:'sonnet', label:'Schnell (Sonnet 5)'}],
                claude:{found:true, version:'synthetic'}}), {headers:{'Content-Type':'application/json'}});
        }
        if (url !== '/api/tutor/chat') return original(url, options);
        const body = JSON.parse(options.body);
        window.__tutorRequests.push({body, token:options.headers['X-Academy-Tutor'], contentType:options.headers['Content-Type']});
        const status = window.__httpStatuses.shift();
        if (status) return new Response(JSON.stringify({error:{kind:'internal', message:'<img src=x onerror=alert(1)>'}}),
            {status, headers:{'Content-Type':'application/json'}});
        if (window.__wrongContent) return new Response('<html>Kein Stream</html>', {headers:{'Content-Type':'text/html'}});
        const stream = new ReadableStream({start(controller) {
            window.__tutorStreams.push(controller);
            options.signal.addEventListener('abort', () => {
                window.__lastAborted = body.requestId;
                try { controller.error(new DOMException('Abgebrochen', 'AbortError')); } catch {}
            });
        }});
        window.__tutorEvent('start', {requestId:body.requestId, model:body.model,
            context:{kind:window.__tutorContext, position:body.positionSec === null ? null : '10:12'}}, true);
        return new Response(stream, {headers:{'Content-Type':'text/event-stream; charset=utf-8'}});
    };
})();"""

def tutor_emit(page, name, data=None):
    page.evaluate("""([name, data]) => {
        if (name === 'done') data = {requestId:window.__tutorRequests.at(-1).body.requestId};
        window.__tutorEvent(name, data, true);
    }""", [name, data])

def tutor_submit(page, question="Erkläre einen synthetischen Zähler."):
    page.locator("#tutorQuestion").fill(question)
    page.locator("#tutorSend").click()

def tutor_complete(page, text="Eine synthetische Antwort."):
    tutor_emit(page, "delta", {"text": text})
    tutor_emit(page, "done")
    page.wait_for_function("""() => { const last = document.querySelector('.tutor-assistant:last-child');
        return last?.dataset.status === 'done' && last.dataset.messageId === window.__tutorRequests.at(-1).body.requestId; }""")

def tutor_layout(page, width):
    panel = page.locator("#tutor").bounding_box()
    media = page.locator(".lesson-media").bounding_box()
    if width >= 1100:
        return panel["x"] >= media["x"] + media["width"] and 380 <= panel["width"] <= 420
    toolbar = page.locator(".toolbar")
    bottom = toolbar.bounding_box() if toolbar.count() else media
    topics = page.locator(".lesson-more .topics")
    return (panel["y"] >= bottom["y"] + bottom["height"] and
            (not topics.count() or panel["y"] + panel["height"] <= topics.bounding_box()["y"]))

def tutor_contract_checks(b):
    ctx, page, errs = new_page(b, SEEDED)
    page.add_init_script(TUTOR_MOCK)
    open_route(page, "#/lesson/fixture/1")
    page.wait_for_selector("#tutorForm:not([hidden])")
    check(page.locator('[data-model="opus"]').get_attribute("aria-pressed") == "true", "Tutor: Opus ist Standard")
    page.locator("h1").click()
    page.keyboard.press("/")
    check(page.locator("#tutorQuestion").evaluate("el => el === document.activeElement"), "Tutor: / fokussiert die Eingabe")
    page.keyboard.press("/")
    check(page.locator("#tutorQuestion").input_value() == "/", "Tutor: / im Eingabefeld bleibt Text")
    page.locator("#tutorQuestion").fill(" " * 3)
    check(page.locator("#tutorSend").is_disabled(), "Tutor: leere Fragen gesperrt")
    page.locator("#tutorQuestion").fill("x" * 4001)
    check(page.locator("#tutorSend").is_disabled() and page.locator("#tutorCount").is_visible(), "Tutor: Zeichenlimit und Zähler")
    page.locator('[data-model="sonnet"]').click()
    # Ohne geladene Videos einen Clipwechsel mit vorgemerktes Autoplay auslösen.
    page.evaluate("""() => { window.__v = document.querySelector('video'); window.__media = document.querySelector('.lesson-media');
        window.__playCalls = 0; window.__v.play = () => { window.__playCalls++; return Promise.resolve(); };
        window.__v.dispatchEvent(new Event('ended')); }""")
    pos = CLIPS[0]["durationMs"] / 1000
    page.locator("#tutorQuestion").fill("Erkläre **Zähler**")
    page.locator("#tutorQuestion").press("Shift+Enter")
    page.locator("#tutorQuestion").press("End")
    page.locator("#tutorQuestion").press("Enter")
    page.wait_for_selector(".tutor-thinking")
    sent = page.evaluate("window.__tutorRequests[0]")
    check(sent["body"]["model"] == "sonnet" and sent["body"]["positionSec"] == pos and
          sent["body"]["lessonKey"] == "fixture/1" and sent["body"]["history"] == [] and
          sent["token"] == "abc123" and sent["contentType"] == "application/json" and
          "\n" in sent["body"]["question"], "Tutor: Vertrag mit eingefrorener globaler Position, Modell und Headern")
    page.evaluate("""() => { Object.defineProperty(window.__v, 'readyState', {configurable:true, value:1});
        window.__v.dispatchEvent(new Event('loadedmetadata')); }""")
    check(page.evaluate("window.__playCalls === 0 && window.__v.paused"), "Tutor: Pausieren hebt ausstehendes Autoplay auf")
    tutor_emit(page, "status", {"kind": "retry", "message": "Wiederholung <nur Text>"})
    page.wait_for_function("document.querySelector('.tutor-status')?.textContent.includes('Wiederholung')")
    check(page.locator("#tutorSend").text_content() == "Stopp", "Tutor: Status retry ist nicht terminal")
    text = '# Erklärung\n**fett** und *kursiv*, `x < y`\n\n- eins\n* zwei\n\n1. drei\n\n<img src=x onerror=alert(1)> https://example.invalid ![Bild](x)\n```js\n' + 'const wert = "ä🧪"; ' * 80 + '\n```'
    # Kommentar, mehrere Events in einem Chunk und anschließend jedes UTF-8-Byte einzeln.
    page.evaluate(r"""() => window.__tutorRaw(': ping\n\nevent: status\ndata: {"kind":"limit_warning","message":"Hinweis"}\n\nevent: delta\ndata: {"text":"Anfang ä.\\n\\n"}\n\n')""")
    tutor_emit(page, "delta", {"text": text})
    page.wait_for_function("document.querySelector('.tutor-assistant .tutor-text')?.textContent.includes('🧪')")
    check(page.evaluate("window.__v === document.querySelector('video') && window.__media === document.querySelector('.lesson-media')"),
          "Tutor: Deltas erhalten Video und übrigen Lektions-Unterbaum")
    check(page.locator(".tutor-messages img, .tutor-messages a, .tutor-messages script").count() == 0 and
          page.locator(".tutor-assistant strong").count() == 2 and page.locator(".tutor-assistant em").count() == 1 and
          page.locator(".tutor-assistant ul li").count() == 2 and page.locator(".tutor-assistant ol li").count() == 1,
          "Tutor: sicheres kleines Markdown, HTML/Bilder/Links bleiben Text")
    page.click('[data-clip="0"]')
    page.locator(".tutor-position").click()
    saved_pos = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['fixture/1'].pos")
    check(abs(saved_pos-pos) < .01 and page.locator('[data-clip="1"][aria-current]').count() == 1 and
          page.evaluate("window.__playCalls === 0"), "Tutor: Positions-Chip springt clipübergreifend und erhält Pause")
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        for width in (1440, 1100, 1099, 390, 360):
            page.set_viewport_size({"width": width, "height": 900})
            page.evaluate("window.scrollTo(0, 0)")
            check(tutor_layout(page, width) and page.evaluate("document.documentElement.scrollWidth <= innerWidth") and
                  page.locator(".tutor-text pre").evaluate("el => el.scrollWidth > el.clientWidth"),
                  f"Tutor: {scheme} {width}px Layout und horizontaler Codeblock ohne Seitenüberstand")
    page.locator("#tutorToggle").click()
    check(page.locator("#tutorBody").is_hidden(), "Tutor: schmal einklappbar")
    page.locator("h1").click()
    page.keyboard.press("/")
    check(page.locator("#tutorBody").is_visible(), "Tutor: / öffnet auch den eingeklappten Chat")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("document.querySelector('#tutor').getBoundingClientRect().bottom <= innerHeight")
    check(page.locator("#tutor").evaluate("el => el.getBoundingClientRect().bottom <= innerHeight"), "Tutor: Seitenleiste endet an der Bildschirmunterkante")
    page.emulate_media(reduced_motion="reduce")
    check(page.locator(".tutor-thinking").count() == 0, "Tutor: Denken endet mit dem ersten Delta")
    tutor_emit(page, "done")
    page.wait_for_selector('.tutor-assistant[data-status="done"]')
    stored = page.evaluate("JSON.parse(localStorage.getItem('academy.tutor.v1'))")
    check(len(stored["lessons"]["fixture/1"]["messages"]) == 2 and stored["v"] == 1 and
          "Tafelvorlesung ohne Untertitel" in page.locator(".tutor-context").text_content(), "Tutor: Abschluss speichert Verlauf und Kontext")
    page.reload()
    page.wait_for_selector('.tutor-assistant[data-status="done"]')
    check(page.locator(".tutor-assistant").count() == 1 and page.locator('[data-model="sonnet"]').get_attribute("aria-pressed") == "true",
          "Tutor: Verlauf und Modellwahl überleben Neuladen")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.click("#tutorNew")
    check(page.locator(".tutor-message").count() == 2, "Tutor: Neues Gespräch verlangt bei vorhandenem Verlauf Bestätigung")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#tutorNew")
    check(page.locator(".tutor-message").count() == 0, "Tutor: Neues Gespräch leert die Lektion")

    # HTTP-Wiederholung ausschließlich einmal bei 403 vor Streambeginn.
    page.evaluate("window.__httpStatuses = [403]")
    tutor_submit(page)
    page.wait_for_function("window.__tutorRequests.length === 2 && window.__tutorStreams.length === 1")
    requests = page.evaluate("window.__tutorRequests")
    check(requests[0]["body"] == requests[1]["body"] and requests[1]["token"] == "def456", "Tutor: 403 erneuert Token und wiederholt exakt einmal")
    tutor_complete(page)
    for status in (400, 403, 404, 409, 429, 413):
        if page.locator("#tutorForm").is_hidden():
            page.reload(); page.wait_for_selector("#tutorForm:not([hidden])")
        before = page.evaluate("window.__tutorRequests.length")
        page.evaluate("status => window.__httpStatuses = status === 403 ? [403, 403] : [status]", status)
        tutor_submit(page, f"Synthetischer HTTP-Fall {status}")
        page.wait_for_function("document.querySelector('#tutorSend').textContent === 'Senden'")
        check(page.evaluate("window.__tutorRequests.length") - before == (2 if status == 403 else 1),
              f"Tutor: HTTP {status} ohne unzulässige automatische Wiederholung")
    for kind, label in (("rate_limit", "Dein Claude-Limit ist erreicht"), ("auth", "/login"),
                        ("timeout", "zu lange"), ("claude_missing", "nicht gefunden"),
                        ("internal", "nicht abgeschlossen"), ("cancelled", "abgebrochen")):
        tutor_submit(page, f"Synthetischer Fehlerfall {kind}")
        page.wait_for_selector(".tutor-thinking")
        tutor_emit(page, "error", {"kind": kind, "message": "<script>unerlaubt()</script>", "resetsAt": "2030-01-01T12:34:00Z"})
        page.wait_for_function("document.querySelector('.tutor-assistant:last-child').dataset.status !== 'streaming'")
        check(label in page.locator(".tutor-assistant").last.text_content() and page.locator(".tutor-messages script").count() == 0,
              f"Tutor: verständlicher sicherer Fehler {kind}")
    tutor_submit(page, "Abbruchtest")
    page.wait_for_selector(".tutor-thinking")
    check(page.locator(".tutor-thinking span").evaluate("el => getComputedStyle(el).animationName") == "none", "Tutor: Tipp-Animation respektiert reduzierte Bewegung")
    page.click("#tutorSend")
    page.wait_for_function("document.querySelector('.tutor-assistant:last-child').dataset.status === 'cancelled'")
    check(page.evaluate("!!window.__lastAborted"), "Tutor: Stopp bricht fetch über AbortController ab")
    page.locator("[data-retry]").last.click()
    page.wait_for_selector(".tutor-thinking")
    check(page.evaluate("window.__tutorRequests.at(-1).body.question") == "Abbruchtest", "Tutor: Nochmal fragen sendet nur auf bewussten Klick")
    tutor_complete(page)
    tutor_submit(page, "Unvollständiger Stream")
    page.wait_for_selector(".tutor-thinking")
    page.evaluate("window.__tutorStreams.at(-1).close()")
    page.wait_for_function("document.querySelector('.tutor-assistant:last-child').dataset.status === 'error'")
    check("nicht abgeschlossen" in page.locator(".tutor-assistant").last.text_content(), "Tutor: EOF ohne Terminalereignis bleibt Fehler")
    page.evaluate("window.__wrongContent = true")
    tutor_submit(page, "Falscher Content-Type")
    page.wait_for_function("document.querySelector('#tutorSend').textContent === 'Senden'")
    check(page.locator(".tutor-assistant").last.get_attribute("data-status") == "error", "Tutor: Content-Type wird vor dem Lesen geprüft")
    page.evaluate("window.__wrongContent = false")
    tutor_submit(page, "Lektion verlassen")
    page.wait_for_selector(".tutor-thinking")
    page.click("a.back")
    page.wait_for_selector(".course-head")
    check(page.locator("#tutor").count() == 0 and page.evaluate("!!window.__lastAborted"), "Tutor: Verlassen bricht Anfrage ab und entfernt Panel")
    page.keyboard.press("/")
    check(page.locator("#tutor").count() == 0, "Tutor: Tastatur-Listener nach Verlassen entfernt")

    open_route(page, "#/lesson/scala/2")
    page.evaluate("window.__tutorContext = 'external'")
    tutor_submit(page, "Synthetische externe Frage")
    page.wait_for_selector(".tutor-thinking")
    check(page.evaluate("window.__tutorRequests.at(-1).body.positionSec === null && window.__tutorRequests.at(-1).body.history.length === 0") and
          page.locator(".tutor-position").count() == 0, "Tutor: externer Kurs ohne Position und ohne fremde Historie")
    tutor_complete(page)
    check(page.locator(".tutor-context").last.text_content() == "externer Kurs", "Tutor: externer Kontext erklärt")
    check(not errs, f"Tutor-Vertrag: keine Konsolen-/Seitenfehler {errs[:3]}")
    ctx.close()

    ctx, page, errs = new_page(b, SEEDED)
    page.add_init_script(TUTOR_MOCK)
    open_route(page, "#/lesson/fixture/1")
    page.locator("#tutorPause").uncheck()
    page.evaluate("""() => { window.__v = document.querySelector('video'); window.__playCalls = 0;
        window.__v.play = () => { window.__playCalls++; return Promise.resolve(); };
        window.__v.dispatchEvent(new Event('ended')); }""")
    tutor_submit(page, "Mit vorgemerkter Wiedergabe weiterlernen")
    page.wait_for_selector(".tutor-thinking")
    page.click('[data-clip="0"]')
    page.locator(".tutor-position").click()
    page.evaluate("""() => { Object.defineProperty(window.__v, 'readyState', {configurable:true, value:1});
        window.__v.dispatchEvent(new Event('loadedmetadata')); }""")
    check(page.evaluate("window.__playCalls === 1"), "Tutor: ausgeschaltete Pause und Positions-Chip erhalten vorgemerkte Wiedergabe")
    tutor_emit(page, "delta", {"text": "x" * 22000})
    tutor_emit(page, "error", {"kind": "auth", "message": "synthetisch"})
    page.wait_for_function("document.querySelector('.tutor-assistant:last-child').dataset.status === 'error'")
    page.reload(); page.wait_for_selector('.tutor-assistant[data-status="error"]')
    check("/login" in page.locator(".tutor-assistant").text_content() and not errs, "Tutor: Fehlermeldung bleibt auch nach Kürzung und Neuladen erhalten")
    ctx.close()

    tutor_storage_checks(b)

def tutor_storage_checks(b):
    ctx, page, errs = new_page(b, None)
    page.add_init_script(TUTOR_MOCK)
    open_route(page, "#/lesson/fixture/1")
    # Große synthetische Historien; kein Unterrichtsmaterial und keine Personendaten.
    page.evaluate("""() => {
        const messages = Array.from({length:44}, (_, i) => ({id:`seed-${i}`, role:i%2 ? 'assistant' : 'user',
            text:'x'.repeat(21000), status:i === 43 ? 'cancelled' : 'done', at:i}));
        localStorage.setItem('academy.tutor.v1', JSON.stringify({v:1, lessons:{
            'fixture/1':{updated:3, messages}, 'fixture/2':{updated:1, messages:messages.slice(0, 20)},
            'fixture/3':{updated:2, messages:messages.slice(0, 20)} }}));
    }""")
    page.reload(); page.wait_for_selector("#tutorForm:not([hidden])")
    tutor_submit(page, "Begrenzte Historie")
    page.wait_for_selector(".tutor-thinking")
    history = page.evaluate("window.__tutorRequests.at(-1).body.history")
    check(len(history) <= 12 and sum(len(m["text"]) for m in history) <= 40000 and
          all(len(m["text"]) <= 8000 for m in history) and len(history) % 2 == 0,
          "Tutor: nur abgeschlossene Paare, höchstens 12 Einträge / 8000 Zeichen / 40 000 Zeichen im API-Verlauf")
    # Ein zweiter Tab schreibt eine andere Lektion zwischen Start und Abschluss.
    tab = ctx.new_page(); fixture_routes(tab); tab.route("**/*.mp4*", lambda r: r.abort()); other_errs = watch_errors(tab)
    open_route(tab, "#/")
    tab.evaluate("""() => { const data = JSON.parse(localStorage.getItem('academy.tutor.v1'));
        data.lessons['scala/1'] = {updated:Date.now(), messages:[{id:'other', role:'user', text:'Anderer Tab', at:1, status:'done'}]};
        localStorage.setItem('academy.tutor.v1', JSON.stringify(data)); }""")
    tutor_complete(page)
    stored = page.evaluate("JSON.parse(localStorage.getItem('academy.tutor.v1'))")
    check(stored["lessons"]["scala/1"]["messages"][0]["text"] == "Anderer Tab", "Tutor: frisches Lesen beim Schreiben erhält andere Tabs")
    check(page.evaluate("localStorage.getItem('academy.tutor.v1').length * 2 <= 1500000") and
          all(len(e["messages"]) <= 40 and all(len(m["text"]) <= 20000 for m in e["messages"]) for e in stored["lessons"].values()) and
          "fixture/2" not in stored["lessons"], "Tutor: Speichergrenzen und Verdrängung ältester Lektionen")
    open_route(page, "#/settings")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#rst")
    check(page.evaluate("!!JSON.parse(localStorage.getItem('academy.tutor.v1')).lessons['scala/1']"), "Tutor: Fortschritt zurücksetzen erhält Claude-Verläufe")
    open_route(page, "#/settings")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#tutorClear")
    check(page.evaluate("localStorage.getItem('academy.tutor.v1') === null && !!localStorage.getItem('academy.v1')"), "Tutor: eigener Löschknopf lässt Fortschritt bestehen")
    check(not errs and not other_errs, f"Tutor-Speicher: keine Konsolen-/Seitenfehler {(errs + other_errs)[:3]}")
    ctx.close()

    ctx, page, errs = new_page(b, None)
    page.add_init_script(TUTOR_MOCK)
    page.add_init_script("Storage.prototype.setItem = function(){ throw new DOMException('synthetisch', 'QuotaExceededError'); }")
    open_route(page, "#/lesson/fixture/1")
    tutor_submit(page)
    page.wait_for_selector(".tutor-thinking")
    tutor_complete(page)
    check(page.locator("#storageNotice").is_visible() and page.locator("#tutorStorage").is_visible() and
          page.locator(".tutor-assistant").last.get_attribute("data-status") == "done", "Tutor: Speicherfehler sichtbar, Fortschritt und Chat laufen weiter")
    page.click("#markDone")
    check(page.locator("#storageNotice").count() == 1 and not errs, "Tutor: Fortschritts-Schreibfehler nur einmal melden, keine unbehandelte Exception")
    ctx.close()


@contextmanager
def fake_tutor_server(mode, directory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    hold = pathlib.Path(directory) / f"{mode}.hold"
    # Unveränderter Servercode in temporärem Repo mit ausschließlich synthetischen Kursdaten.
    # Der Fake bekommt dadurch niemals echte Namen oder Vorlesungsinhalte als Prompt.
    test_root = pathlib.Path(directory) / mode
    (test_root / "scripts").mkdir(parents=True)
    (test_root / "data/quiz").mkdir(parents=True)
    for name in ("app.js", "styles.css", "index.html", "scripts/serve.py", "scripts/tutor_prompt.md"):
        shutil.copyfile(ROOT / name, test_root / name)
    (test_root / "scripts/fake_claude.py").symlink_to(ROOT / "scripts/fake_claude.py")
    courses = [
        {"id":"synthetic", "kind":"stream", "title":"Synthetischer Testkurs", "subtitle":"Übungsdaten", "lang":"de",
         "captions":False, "portalUrl":"https://example.invalid/course", "lessons":[
             {"nr":1, "title":"Synthetische Zähler", "topics":["Zähler"], "durationMs":240000, "clips":[
                 {"opencastId":f"synthetic-{i}", "title":f"Clip {i}", "video":f"https://example.invalid/{i}.mp4", "durationMs":120000}
                 for i in (1, 2)]}]},
        {"id":"synthetic-external", "kind":"external", "title":"Externer Testkurs", "subtitle":"Übungsdaten", "note":"Synthetischer Kurs",
         "lessons":[{"nr":1, "title":"Externes Beispiel", "topics":["Beispiele"], "estMinutes":10, "externalUrl":"https://example.invalid/course"}]},
    ]
    (test_root / "data/academy.json").write_text(json.dumps({"courses":courses}), encoding="utf-8")
    for course in courses: (test_root / f"data/quiz/{course['id']}.json").write_text("{}", encoding="utf-8")
    env = os.environ.copy()
    env.update(ACADEMY_CLAUDE_BIN=str(ROOT / "scripts/fake_claude.py"), FAKE_CLAUDE_MODE=mode,
               FAKE_CLAUDE_HOLD_FILE=str(hold), PORT=str(port), PYTHONDONTWRITEBYTECODE="1")
    # Der Prozess erhält ausschließlich den expliziten Fake als CLI; niemals das echte claude.
    with tempfile.TemporaryFile(mode="w+") as output:
        process = subprocess.Popen([sys.executable, str(test_root / "scripts/serve.py"), "--port", str(port)],
                                   cwd=test_root, env=env, stdout=output, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}/"
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError(f"Testserver beendet (Exit {process.returncode})")
                try:
                    with urlopen(base + "api/tutor/health", timeout=.5) as response:
                        if response.status == 200: break
                except OSError: time.sleep(.1)
            else: raise RuntimeError("Testserver wurde nicht bereit")
            yield process, base, hold
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)

def child_pids(process):
    result = subprocess.run(["pgrep", "-P", str(process.pid)], capture_output=True, text=True)
    return [int(pid) for pid in result.stdout.split()]

def pid_alive(pid):
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False

def tutor_server_checks(b):
    if not all((ROOT / f"scripts/{name}.py").is_file() for name in ("serve", "fake_claude")):
        print("Modus B: übersprungen – scripts/serve.py und/oder scripts/fake_claude.py fehlen.", flush=True)
        return
    first_notes, first_fails = len(notes), len(fails)
    with tempfile.TemporaryDirectory(prefix="academy-tutor-smoke-") as directory:
        for mode in ("ok", "hang", "rate_limit", "auth", "eof", "stderr_flood", "api_key"):
            ctx = None
            try:
                with fake_tutor_server(mode, directory) as (process, base, hold):
                    ctx, page, errs = new_page(b, None, fixtures=False)
                    page.goto(base + "#/lesson/synthetic/1")
                    page.wait_for_selector("#tutorForm:not([hidden])")
                    page.click("#fwd10")
                    page.evaluate("window.__v = document.querySelector('video')")
                    question = f"Synthetische Frage für {mode}: Was macht ein Zähler?"
                    tutor_submit(page, question)
                    if mode == "ok":
                        page.wait_for_function("document.querySelector('.tutor-assistant .tutor-text')?.textContent.trim() && !document.querySelector('.tutor-thinking')", timeout=15000)
                        check(not hold.exists() and page.locator("#tutorSend").text_content() == "Stopp", "Modus B: erstes Delta sichtbar, während HOLD-Datei noch fehlt")
                        check(page.evaluate("window.__v === document.querySelector('video')"), "Modus B: Videoknoten bleibt während Streaming identisch")
                        page.click("#fwd10")
                        page.locator(".tutor-position").click()
                        check(page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['synthetic/1'].pos") == 10,
                              "Modus B: Positions-Chip springt zur eingefrorenen Position")
                        second = ctx.new_page(); second.route("**/*.mp4*", lambda r: r.abort()); second_errs = watch_errors(second)
                        second.goto(base + "#/lesson/synthetic-external/1")
                        second.wait_for_selector("#tutorForm:not([hidden])")
                        tutor_submit(second, "Synthetische Frage im zweiten Tab.")
                        second.wait_for_function("document.querySelector('.tutor-assistant .tutor-text')?.textContent.trim() && !document.querySelector('.tutor-thinking')")
                        check(not hold.exists() and page.locator("#tutorSend").text_content() == "Stopp" and
                              second.locator("#tutorSend").text_content() == "Stopp", "Modus B: zwei Tabs streamen unabhängig gleichzeitig")
                        hold.touch()
                        page.wait_for_selector('.tutor-assistant[data-status="done"]', timeout=15000)
                        second.wait_for_selector('.tutor-assistant[data-status="done"]', timeout=15000)
                        check(question in page.locator(".tutor-assistant").text_content(), "Modus B: vollständige Fake-Antwort zitiert die Frage")
                        check(page.evaluate("!!JSON.parse(localStorage.getItem('academy.tutor.v1')).lessons['synthetic-external/1']") and not second_errs,
                              "Modus B: zweiter Tab stört weder Streaming noch Speicherung")
                        page.reload(); page.wait_for_selector('.tutor-assistant[data-status="done"]')
                        check(question in page.locator(".tutor-assistant").text_content(), "Modus B: Neuladen erhält Verlauf")
                        page.once("dialog", lambda dialog: dialog.accept()); page.click("#tutorNew")
                        check(page.locator(".tutor-message").count() == 0, "Modus B: Neues Gespräch leert Verlauf")
                    elif mode == "hang":
                        deadline = time.monotonic() + 10
                        while not (children := child_pids(process)) and time.monotonic() < deadline: page.wait_for_timeout(100)
                        check(bool(children), "Modus B: hang hat einen laufenden Fake-Prozess")
                        page.click("#tutorSend")
                        page.wait_for_selector('.tutor-assistant[data-status="cancelled"]')
                        deadline = time.monotonic() + 25  # Zwei 10-s-Heartbeats; deutlich vor dem Server-Timeout.
                        while any(pid_alive(pid) for pid in children) and time.monotonic() < deadline: page.wait_for_timeout(100)
                        check(bool(children) and not any(pid_alive(pid) for pid in children) and "abgebrochen" in page.locator(".tutor-assistant").text_content(),
                              "Modus B: Stopp zeigt abgebrochen und Server beendet den Fake-Prozess")
                    else:
                        hold.touch()
                        expected = "done" if mode == "stderr_flood" else "error"
                        page.wait_for_selector(f'.tutor-assistant[data-status="{expected}"]', timeout=20000)
                        label = "Dein Claude-Limit ist erreicht" if mode == "rate_limit" else "/login" if mode in ("auth", "api_key") else "nicht abgeschlossen" if mode == "eof" else ""
                        check(label in page.locator(".tutor-assistant").text_content(), f"Modus B: {mode} endet verständlich mit {expected}")
                    check(not errs, f"Modus B {mode}: keine Konsolen-/Seitenfehler {errs[:3]}")
                    ctx.close(); ctx = None
            except Exception as error:
                check(False, f"Modus B {mode}: {str(error).splitlines()[0]}")
            finally:
                if ctx: ctx.close()
    print(f"Modus B: {len(notes)-first_notes} ok, {len(fails)-first_fails} fehlgeschlagen", flush=True)


with sync_playwright() as p:
    b = p.chromium.launch()

    # 1) Alle Routen rendern ohne Fehler, hell und dunkel, Desktop und Handy
    routes = ["#/", "#/course/theoinf", "#/course/architektur", "#/course/scala", "#/lesson/theoinf/3",
              "#/lesson/architektur/1", "#/lesson/scala/2", "#/quiz/theoinf/4", "#/settings",
              "#/course/fixture", "#/lesson/fixture/1", "#/lesson/fixture/2", "#/lesson/fixture/3"]
    for cid in ("linalg", "analysis"):
        if any(c["id"] == cid for c in ACADEMY["courses"]):
            routes.extend((f"#/course/{cid}", f"#/lesson/{cid}/1", f"#/quiz/{cid}/1"))
    for scheme in ("light", "dark"):
        for vp in ((1440, 900), (390, 844), (360, 740)):
            ctx, page, errs = new_page(b, SEEDED, vp, scheme)
            for r in routes:
                open_route(page, r)
                over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                check(over <= 0, f"{scheme} {vp[0]}px {r}: kein horizontales Scrollen (Überstand {over}px)")
                check(page.locator("h1").count() >= 1, f"{scheme} {vp[0]}px {r}: h1 vorhanden")
                if r.startswith("#/lesson/"):
                    page.wait_for_function("document.querySelector('#tutorService')?.textContent.includes('nicht verfügbar')")
                    check(page.locator("#tutorService").text_content() == "Claude-Tutor nicht verfügbar – starte die Academy mit ./start.sh" and
                          page.locator("#tutorForm").is_hidden(), f"{scheme} {vp[0]}px {r}: Tutor nicht verfügbar am statischen Server")
                    check(tutor_layout(page, vp[0]), f"{scheme} {vp[0]}px {r}: Tutor rechts neben oder unter dem Player")
            check(not errs, f"{scheme} {vp[0]}px: keine Konsolen-/Seitenfehler {errs[:3]}")
            ctx.close()

    # 2) Test per Tastatur: Taste 1 wählt, Enter geht weiter, Auswertung erscheint
    ctx, page, errs = new_page(b, SEEDED)
    open_route(page, "#/quiz/theoinf/4")
    for i in range(5):
        page.keyboard.press("1")
        page.wait_for_timeout(80)
        check(page.locator(".opt.right").count() == 1, f"Quiz Frage {i+1}: Auflösung nach Taste 1 sichtbar")
        page.keyboard.press("Enter")
        page.wait_for_timeout(120)
    check(page.locator("#again").count() == 1, "Quiz: Auswertung nach 5 Fragen mit 'Nochmal'")
    stored = page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).quiz['theoinf/4']")
    check(stored and stored.get("attempts") == 1, f"Quiz: Ergebnis gespeichert {stored}")
    check(not errs, f"Quiz: keine Fehler {errs[:3]}")
    ctx.close()

    # 3) Lektion: 'geschaut' umschalten baut das Video nicht neu auf; Download-Menü ist aus
    ctx, page, errs = new_page(b, SEEDED)
    open_route(page, "#/lesson/theoinf/3")
    page.evaluate("window.__v = document.querySelector('video')")
    page.click("#markDone")
    page.wait_for_timeout(100)
    check(page.evaluate("window.__v === document.querySelector('video')"), "Lektion: Video-Element bleibt beim Umschalten erhalten")
    check(page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).lessons['theoinf/3'].watched === true"), "Lektion: 'geschaut' gespeichert")
    cl = page.evaluate("document.querySelector('video').getAttribute('controlslist') || ''")
    check("nodownload" in cl, f"Lektion: controlslist enthält nodownload ('{cl}')")
    src = page.evaluate("document.querySelector('video source, video').getAttribute('src') || document.querySelector('video source').getAttribute('src')")
    check(src.startswith("https://") and "ethz.ch" in src, f"Lektion: Video wird von ETH gestreamt ({src[:40]}…)")
    check(not errs, f"Lektion: keine Fehler {errs[:3]}")
    ctx.close()

    # 4) Zwei Tabs: ein veralteter Tab überschreibt den Fortschritt des anderen nicht
    ctx = b.new_context(viewport={"width": 1200, "height": 800}, locale="de-CH")
    ctx.add_init_script(f"if (!localStorage.getItem('academy.v1')) localStorage.setItem('academy.v1', {json.dumps(json.dumps(SEEDED))})")
    a, c = ctx.new_page(), ctx.new_page()
    for pg in (a, c):
        pg.route("**/*.mp4*", lambda r: r.abort())
    open_route(a, "#/")
    open_route(c, "#/course/theoinf")
    a.evaluate("""() => { const s = JSON.parse(localStorage.getItem('academy.v1'));
                          s.quiz['theoinf/9'] = {best: 1, passed: true, attempts: 1};
                          localStorage.setItem('academy.v1', JSON.stringify(s));
                          window.dispatchEvent(new Event('noop')); }""")
    a.wait_for_timeout(200)
    open_route(c, "#/lesson/theoinf/5")          # Tab c speichert (S.last) - darf theoinf/9 nicht verlieren
    c.wait_for_timeout(200)
    kept = c.evaluate("!!JSON.parse(localStorage.getItem('academy.v1')).quiz['theoinf/9']")
    check(kept, "Zwei Tabs: Speichern im zweiten Tab behält den Fortschritt aus dem ersten")
    ctx.close()

    # 5) Einstellungen: Tagesziel und Darstellung wirken
    ctx, page, errs = new_page(b, SEEDED)
    open_route(page, "#/settings")
    page.click("[data-goal='45']")
    page.wait_for_timeout(100)
    check(page.evaluate("JSON.parse(localStorage.getItem('academy.v1')).dailyMinutes") == 45, "Einstellungen: Tagesziel 45 gespeichert")
    page.click("[data-theme-set='dark']")
    page.wait_for_timeout(100)
    check(page.evaluate("document.documentElement.dataset.theme") == "dark", "Einstellungen: Darstellung dunkel gesetzt")
    check(not errs, f"Einstellungen: keine Fehler {errs[:3]}")
    ctx.close()
    fixture_checks(b)
    tutor_contract_checks(b)
    if ARGS.stream: stream_checks(b)
    print(f"Modus A: {len(notes)} ok, {len(fails)} fehlgeschlagen", flush=True)
    tutor_server_checks(b)
    b.close()

print(f"\n{len(notes)} ok, {len(fails)} fehlgeschlagen")
server.shutdown()
sys.exit(1 if fails else 0)
