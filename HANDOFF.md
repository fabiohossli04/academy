# Handoff

Stand: 23.09.2026. Alles läuft, nichts ist halbfertig.

## Was das ist

Eine persönliche Lernoberfläche für 30 Minuten am Tag. Drei Kurse,
53 Lektionen, 265 selbst geschriebene Testfragen. Start mit `./start.sh`.

| Kurs | id | Lektionen | Umfang | Tests |
|---|---|---|---|---|
| Theoretische Informatik (ETH, Komm, HS23, deutsch) | `theoinf` | 24 | 34,9 h | 120 |
| Digital Design und Rechnerarchitektur (ETH, Mutlu, FS25, englisch) | `architektur` | 22 | 33,7 h | 110 |
| Funktionale Programmierung in Scala (EPFL, Odersky) | `scala` | 7 | extern | 35 |

## Vier Regeln, die nicht gebrochen werden dürfen

1. **Videos werden gestreamt, nie heruntergeladen.** Die App ist ein Abspieler,
   kein Archiv; der Player blendet das Download-Menü aus
   (`controlslist="nodownload"`). Auf dem Rechner waren zuletzt rund 30 GB frei –
   68 h Video passen da ohnehin nicht hin.
2. **`transcripts/` bleibt gitignored.** Das Repo ist öffentlich. Der Ordner
   enthält die Untertitel der ETH-Vorlesungen, also fremdes Material. Er liegt
   lokal, weil der ETH-Server keine CORS-Kopfzeile schickt und der Browser die
   Dateien sonst nicht einbinden darf.
3. **Testfragen bleiben eigene Formulierungen.** Sie prüfen Verständnis des
   Themas und geben keine Vorlesungsinhalte wieder.
4. **`python3 scripts/check.py` muss grün sein**, bevor etwas committet wird.
   Die Routine schlägt unter anderem fehl, wenn die richtige Antwort bei mehr
   als 45 % der Fragen an derselben Position steht oder bei mehr als 40 % die
   längste Option ist. Beides war schon einmal der Fall: zuerst 94–100 % auf
   Position 2 (durch Mischen behoben), dann war bei 254 von 265 Fragen die
   richtige Antwort die längste – wer immer die längste wählte, bestand 52 von
   53 Lektionstests. Am 23.09. wurden dafür die falschen Optionen aller Fragen
   neu geschrieben und
   weitere Rate-Muster abgebaut. Seitdem ist die längste Option nur noch bei
   14–24 % der Fragen die richtige, und keine gemessene Faustregel trifft mehr
   als 32 % (Zufall: 25 %).

## Aufbau

```
index.html  app.js  styles.css     Oberfläche, kein Build-Schritt
data/academy.json                  Kurse, Lektionen, Video- und Untertitel-URLs
data/quiz/<kurs>.json              Testfragen, Schlüssel = Lektionsnummer
scripts/fetch.py                   zieht Metadaten aus dem ETH-Videoportal
scripts/transcripts.py             lädt Untertitel (.vtt für den Player, .txt zum Lesen)
scripts/build.py                   Titel + Rohdaten -> data/academy.json
scripts/check.py                   Vollständigkeits- und Plausibilitätsprüfung der Daten
scripts/muster.py                  misst Rate-Muster in einer Quizdatei (Länge, Wortwahl, Satzzeichen)
scripts/smoke.py                   Oberflächentest mit Playwright (optional)
transcripts/                       lokal, gitignored
```

Komplett neu aufbauen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py \
  && python3 scripts/build.py && python3 scripts/check.py
```

Format einer Frage:

```json
{ "q": "Frage?", "options": ["a","b","c","d"], "answer": 2, "why": "Begründung." }
```

`answer` ist der Index der richtigen Antwort. Nach jedem Hinzufügen `check.py`
laufen lassen: bei einseitiger Position mischen, bei auffälliger Länge die
falschen Optionen angleichen. Zusätzlich `python3 scripts/muster.py data/quiz/<kurs>.json`:
es misst, wie oft simple Faustregeln (längste Option, absolute Wörter wie „immer“,
Satzzeichen, Wortüberlappung …) die richtige Antwort treffen; `--strict` schlägt fehl,
wenn eine davon deutlich über Zufall liegt. Die Fragen sind in Schweizer Schreibung
(ss statt ß).

## Oberfläche

- Hell und dunkel nach Systemeinstellung, unter *Einstellungen* fest wählbar.
- Startseite zeigt den nächsten Schritt: angefangene Lektion, offenen Test dazu,
  nächste Lektion oder Abschlussprüfung – dazu Tagesziel und die letzten sieben Tage.
- Tests per Tastatur: A–D oder 1–4 wählt, Enter geht weiter. Nach dem Test
  stehen die falsch beantworteten Fragen mit Begründung zum Nachlesen da.
- Lernzeit zählt echte Zeit beim Abspielen (bei 1,5× zählt eine Videominute 40 s).
- Fortschritt in `localStorage` unter `academy.v1`; mehrere offene Tabs gleichen
  sich über das `storage`-Ereignis ab, statt sich gegenseitig zu überschreiben.
- `python3 scripts/smoke.py` prüft alle Routen hell und dunkel bei 1440, 390 und
  360 px Breite, den Test per Tastatur, „geschaut“ ohne Video-Neuaufbau,
  `nodownload`, zwei Tabs und die Einstellungen. Startet einen eigenen Server und
  lädt keine Videos. Braucht `pip install playwright` und
  `python3 -m playwright install chromium`.

## Wie das Material geprüft wurde

Das ETH-Videoportal ist fast vollständig login-gesperrt. Ob eine Lektion
wirklich öffentlich ist, erkennt man **nicht** am Typ `AuthorizedEvent` – der
erscheint auch bei gesperrten Videos. Entscheidend ist, ob
`authorizedData.tracks` befüllt ist. Gegengeprüft wird zusätzlich mit einem
Bereichsabruf auf die Videodatei (Antwort 206, `video/mp4`). Der Server leitet
dabei zuerst mit 302 von `dist.tobira.ethz.ch` auf `dist01`/`dist02` um – der
Abruf muss der Weiterleitung folgen.

Abfrage gegen `https://video.ethz.ch/graphql`, anonym:

```graphql
{ realmByPath(path: "/lectures/d-infk/2023/autumn/252-0057-00L") {
    blocks { ... on SeriesBlock { series { entries {
      ... on AuthorizedEvent { authorizedData { tracks { uri } } } } } } } } }
```

## Was offen ist

- **Scala-Videos sind nicht eingebettet**, weil sie hinter dem Coursera-Login
  liegen. Verlinkt sind der Kurs und die frei abrufbaren EPFL-Folien. Die
  Fragen dort stammen aus dem veröffentlichten Kursplan, nicht aus den Videos –
  das steht auch so in der App.
- **Laufende Kurse als Nachschub:** ETH veröffentlicht gerade wöchentlich
  *Privacy Enhancing Technologies* (HS26, Tramèr,
  `/lectures/d-infk/2026/autumn/263-4658-00L`) und *Software Engineering*
  (HS26, Lüthi, `/lectures/d-infk/2026/autumn/252-0232-00L`). Am 23.09. waren
  beide nach beiden Kriterien öffentlich: 3 Vorlesungen (3,1 h) bzw. 6 Clips à
  2–7 min (28,5 min). Mit `fetch.py` allein ist es nicht getan:
  - `build.py` braucht handgeschriebene Titel pro Lektion und bricht ab, sobald
    eine neue Aufnahme dazukommt – bei laufenden Kursen also jede Woche.
  - Titel, Fragen, Untertitel und Fortschritt hängen an der Lektionsnummer, und
    die entsteht aus der Aufnahmereihenfolge. Schiebt ETH eine Aufnahme
    nachträglich dazwischen, verrutscht alles still; `check.py` merkt das nicht.
    Vorher Titel an die `opencastId` binden.
  - Die SE-Clips sind für je 5 Fragen zu kurz; besser wochenweise bündeln (die
    App kennt dafür noch keine Lektion mit mehreren Videos).
  - Einfachster Weg: beide Kurse zum Semesterende aufnehmen.
- **Fortschritt liegt nur im Browser** (localStorage). Vor einem Rechnerwechsel
  unter *Einstellungen* als Datei sichern.
