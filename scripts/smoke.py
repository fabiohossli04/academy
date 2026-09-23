#!/usr/bin/env python3
"""Smoke-Test der Oberfläche: alle Routen hell/dunkel auf Desktop und Handy, Test per Tastatur,
"geschaut" ohne Video-Neuaufbau, kein Download-Menü, zwei Tabs, Einstellungen.
Startet einen eigenen lokalen Server. Lädt KEINE Videos (Anfragen auf *.mp4 werden abgebrochen).
Braucht Playwright:  pip install playwright && python3 -m playwright install chromium
Aufruf: python3 scripts/smoke.py   (Exit 0 = alles grün)"""
import datetime, functools, http.server, json, pathlib, sys, threading
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright fehlt: pip install playwright && python3 -m playwright install chromium")

ROOT = pathlib.Path(__file__).resolve().parent.parent
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
    (notes if cond else fails).append(("ok   " if cond else "FAIL ") + msg)

def new_page(b, state, vp=(1440, 900), scheme="light"):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, color_scheme=scheme, locale="de-CH")
    if state is not None:
        ctx.add_init_script(f"localStorage.setItem('academy.v1', {json.dumps(json.dumps(state))})")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}") if m.type == "error" and ".mp4" not in m.text and "ERR_FAILED" not in m.text else None)
    page.route("**/*.mp4", lambda r: r.abort())
    return ctx, page, errs

def open_route(page, hsh):
    page.goto(BASE + hsh)
    page.wait_for_selector("main#view > *", timeout=8000)
    page.wait_for_timeout(150)

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1) Alle Routen rendern ohne Fehler, hell und dunkel, Desktop und Handy
    routes = ["#/", "#/course/theoinf", "#/course/architektur", "#/course/scala", "#/lesson/theoinf/3",
              "#/lesson/architektur/1", "#/lesson/scala/2", "#/quiz/theoinf/4", "#/settings"]
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
        pg.route("**/*.mp4", lambda r: r.abort())
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
    b.close()

for n in notes: print(n)
for f in fails: print(f)
print(f"\n{len(notes)} ok, {len(fails)} fehlgeschlagen")
server.shutdown()
sys.exit(1 if fails else 0)
