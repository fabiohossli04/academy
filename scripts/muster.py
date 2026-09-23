#!/usr/bin/env python3
"""Misst Rate-Muster in einer Quizdatei: Wie oft trifft eine simple Faustregel die richtige Antwort?
Erwartete Trefferquote je Regel (Gleichstände zufällig aufgelöst); Zufall wäre 25 %.
Aufruf: python3 scripts/muster.py data/quiz/<kurs>.json [--head] [--strict]
  --head   zusätzlich den Stand aus HEAD messen
  --strict Exit 1, wenn eine Regel über ihrer Grenze liegt"""
import json, re, subprocess, sys

ABSOLUT = r"\b(immer|nie|niemals|nur|stets|alle|aller|allen|alles|jede|jeder|jedes|jedem|jeden|sämtlich\w*|ausschlie(ss|ß)lich|grundsätzlich|zwangsläufig|überhaupt|automatisch\w*|garantier\w*)\b"
VORSICHT = r"\b(kann|können|etwa|wenn|solange|höchstens|tatsächlich|erst|zusätzlich|meist|oft|häufig|typischerweise|wahrscheinlich)\b"
ZEICHEN = r"\s[-–—]\s|[:;]"
EINLEITUNG = r"^(bei|für|wenn|falls|sofern|im schlimmsten fall)\b"

def words(o): return re.findall(r"[^\W_]+", o.lower())
def has(p, o): return 1 if re.search(p, o, re.I) else 0
def nth_len(opts, o, k):                      # 1, wenn o die k-kleinste Zeichenlänge hat (k=1 kürzeste, k=-1 längste)
    L = sorted(len(x) for x in opts)
    return 1 if len(o) == L[k] else 0
def overlap(opts, o):                          # mittlere Anzahl gemeinsamer Wörter mit den anderen Optionen
    w = set(words(o))
    others = [set(words(x)) for x in opts if x is not o]
    return sum(len(w & x) for x in others) / len(others)

# name: (Grenze, score(option, alle_optionen))
RULES = {
    "längste Option (Zeichen)":     (0.35, lambda o, a: len(o)),
    "kürzeste Option (Zeichen)":    (0.35, lambda o, a: -len(o)),
    "zweitkürzeste Option":         (0.35, lambda o, a: nth_len(a, o, 1)),
    "zweitlängste Option":          (0.35, lambda o, a: nth_len(a, o, -2)),
    "meiste Wörter":                (0.35, lambda o, a: len(words(o))),
    "wenigste Wörter":              (0.35, lambda o, a: -len(words(o))),
    "ohne absolute Wörter":         (0.32, lambda o, a: -has(ABSOLUT, o)),
    "mit Einschränkungswörtern":    (0.32, lambda o, a: has(VORSICHT, o)),
    "mit einschränkendem Anfang":   (0.32, lambda o, a: has(EINLEITUNG, o)),
    "mit Sonderzeichen ( - : ;)":   (0.32, lambda o, a: has(ZEICHEN, o)),
    "mit „statt“":                  (0.30, lambda o, a: has(r"\bstatt\b", o)),
    "grösste Wortüberlappung":      (0.32, lambda o, a: overlap(a, o)),
    "Kombination der Faustregeln":  (0.35, lambda o, a: has(VORSICHT, o) + has(ZEICHEN, o) + has(r"\bstatt\b", o)
                                                        + has(EINLEITUNG, o) - has(ABSOLUT, o)),
}

def expected(qs, score):
    """Mittlere Trefferquote der Regel 'wähle die Option mit dem höchsten Score', Gleichstände zufällig."""
    tot = 0.0
    for q in qs:
        s = [score(o, q["options"]) for o in q["options"]]
        m = max(s)
        best = [i for i, x in enumerate(s) if x == m]
        tot += (1 / len(best)) if q["answer"] in best else 0
    return tot / len(qs)

def report(label, d):
    qs = [q for b in d.values() for q in b["questions"]]
    over = []
    print(f"{label}: {len(qs)} Fragen")
    for name, (limit, fn) in RULES.items():
        r = expected(qs, fn)
        flag = "  ✗ über Grenze" if r > limit else ""
        if flag: over.append(name)
        print(f"  {name:<30} {r*100:5.1f} %  (Grenze {limit*100:.0f} %){flag}")
    aw = sum(has(ABSOLUT, o) for q in qs for i, o in enumerate(q["options"]) if i != q["answer"])
    ar = sum(has(ABSOLUT, q["options"][q["answer"]]) for q in qs)
    print(f"  absolute Wörter: in {aw}/{3*len(qs)} falschen ({aw/(3*len(qs))*100:.0f} %) und {ar}/{len(qs)} richtigen Optionen ({ar/len(qs)*100:.0f} %)")
    return over

f = sys.argv[1]
if "--head" in sys.argv:
    report(f"{f} (HEAD)", json.loads(subprocess.run(["git", "show", f"HEAD:{f}"], capture_output=True, text=True, check=True).stdout))
over = report(f"{f} (jetzt)", json.load(open(f, encoding="utf-8")))
if over: print("  über der Grenze:", ", ".join(over))
sys.exit(1 if over and "--strict" in sys.argv else 0)
