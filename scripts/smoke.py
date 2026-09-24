#!/usr/bin/env python3
"""Smoke-Test der Oberfläche: alle Routen hell/dunkel auf Desktop und Handy, Test per Tastatur,
"geschaut" ohne Video-Neuaufbau, kein Download-Menü, zwei Tabs, Einstellungen.
Startet einen eigenen lokalen Server. Standardlauf offline: *.mp4 wird abgebrochen.
Mit --stream zusätzlich echte Wiedergabe im stummen <video>, ohne Speicherung oder Aufzeichnung.
Braucht Playwright:  pip install playwright && python3 -m playwright install chromium
Aufruf: python3 scripts/smoke.py [--stream]   (Exit 0 = alles grün)"""
import argparse, copy, datetime, functools, http.server, json, pathlib, sys, threading
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

def new_page(b, state, vp=(1440, 900), scheme="light", stream=False, legacy=False):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, color_scheme=scheme,
                        locale="de-CH", accept_downloads=False, service_workers="block")
    if state is not None:
        ctx.add_init_script(f"localStorage.setItem('academy.v1', {json.dumps(json.dumps(state))})")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}")
            if m.type == "error" and not (not stream and ".mp4" in m.location.get("url", "")) else None)
    fixture_routes(page, legacy)
    # Routing deaktiviert auch den HTTP-Cache. Keine Downloads, HARs, Videos oder Screenshots.
    page.route("**/*.mp4*", lambda r: r.continue_() if stream else r.abort())
    return ctx, page, errs

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
    if ARGS.stream: stream_checks(b)
    b.close()

print(f"\n{len(notes)} ok, {len(fails)} fehlgeschlagen")
server.shutdown()
sys.exit(1 if fails else 0)
