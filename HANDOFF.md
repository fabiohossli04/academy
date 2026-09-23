# Handoff

Stand: 23.09.2026. Alles läuft, nichts ist halbfertig.

## Was das ist

Eine persönliche Lernoberfläche für 30 Minuten am Tag. Fünf Kurse,
58 Lektionen, 290 selbst geschriebene Testfragen. Start mit `./start.sh`.

| Kurs | id | Lektionen | Umfang | Tests |
|---|---|---|---|---|
| Theoretische Informatik (ETH, Komm, HS23, deutsch) | `theoinf` | 24 | 34,9 h | 120 |
| Digital Design und Rechnerarchitektur (ETH, Mutlu, FS25, englisch) | `architektur` | 22 | 33,7 h | 110 |
| Funktionale Programmierung in Scala (EPFL, Odersky) | `scala` | 7 | extern | 35 |
| Privacy Enhancing Technologies (ETH, Tramèr, HS26, englisch, **läuft**) | `privacy` | 3 | 3,1 h | 15 |
| Software Engineering (ETH, Lüthi, HS26, englisch, **läuft**, Kurzclips pro Woche) | `software` | 2 | 0,5 h | 10 |

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
   Themas und geben keine Vorlesungsinhalte wieder. Die Untertitel sind nur
   Arbeitsgrundlage.
4. **`python3 scripts/check.py` muss grün sein**, bevor etwas committet wird.
   Die Routine schlägt unter anderem fehl, wenn die richtige Antwort bei mehr
   als 45 % der Fragen an derselben Position steht oder bei mehr als 40 % die
   längste Option ist. Beides war schon einmal der Fall: zuerst 94–100 % auf
   Position 2 (durch Mischen behoben), dann war bei 254 von 265 Fragen die
   richtige Antwort die längste – wer immer die längste wählte, bestand 52 von
   53 Lektionstests. Am 23.09. wurden dafür die falschen Optionen aller Fragen
   neu geschrieben und weitere Rate-Muster abgebaut; keine gemessene Faustregel
   trifft seitdem mehr als 32 % (Zufall: 25 %). Vorsicht beim Schreiben neuer
   Fragen: Präzise richtige Antworten werden von selbst länger – messen.

## Aufbau

```
index.html  app.js  styles.css     Oberfläche, kein Build-Schritt
data/lessons.json                  EINE Autorität für Stream-Kurse: Kursdaten, Lektionen mit fester Nummer und Clip-Liste (opencastIds)
data/academy.json                  gebaut aus lessons.json + Portal-Rohdaten – nie von Hand ändern
data/quiz/<kurs>.json              Testfragen, Schlüssel = Lektionsnummer
scripts/fetch.py                   zieht Metadaten aller Kurse aus lessons.json aus dem ETH-Videoportal
scripts/transcripts.py             lädt Untertitel nach opencastId (.vtt für den Player, .txt zum Lesen)
scripts/build.py                   baut academy.json, prüft den Kandidaten und schreibt nur, wenn alles gültig ist
scripts/check.py                   Vollständigkeits- und Plausibilitätsprüfung, inkl. Schutz veröffentlichter Lektionen
scripts/muster.py                  misst Rate-Muster in einer Quizdatei (Länge, Wortwahl, Satzzeichen …)
scripts/smoke.py                   Oberflächentest mit Playwright (optional, --stream mit echter Wiedergabe)
transcripts/                       lokal, gitignored
```

Komplett neu aufbauen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py \
  && python3 scripts/build.py && python3 scripts/check.py
```

`build.py --dry-run` prüft und berichtet, ohne academy.json anzufassen.

Format einer Frage:

```json
{ "q": "Frage?", "options": ["a","b","c","d"], "answer": 2, "why": "Begründung." }
```

`answer` ist der Index der richtigen Antwort. Nach jedem Hinzufügen `check.py`
und `python3 scripts/muster.py data/quiz/<kurs>.json --strict` laufen lassen:
es misst, wie oft simple Faustregeln (längste Option, absolute Wörter wie „immer“,
Satzzeichen, Wortüberlappung …) die richtige Antwort treffen. Die Fragen sind in
Schweizer Schreibung (ss statt ß).

## Laufende Kurse pflegen

`privacy` und `software` werden wöchentlich ergänzt. Ablauf:

1. `python3 scripts/fetch.py && python3 scripts/transcripts.py`
2. `python3 scripts/build.py --dry-run` – listet „neu im Portal, noch nicht
   aufgenommen: <kurs> <Datum> '<Titel>' <opencastId>“.
3. In `data/lessons.json` eine **neue** Lektion mit der nächsten Nummer anlegen:
   Titel und Themen aus dem Inhalt (die Untertitel liegen unter
   `transcripts/<kurs>/<opencastId>.txt`), `clips` = die opencastIds in
   Aufnahmereihenfolge. `privacy`: eine Lektion pro Vorlesung. `software`: eine
   Lektion pro Woche; kommen zu einer bereits aufgenommenen Woche Clips nach,
   werden sie eine neue Lektion („Woche 3, Nachtrag“).
4. Fünf eigene Fragen unter der neuen Nummer in `data/quiz/<kurs>.json`,
   dann `muster.py --strict`.
5. `python3 scripts/build.py && python3 scripts/check.py`, dann committen.

**Veröffentlichte Lektionen sind unveränderlich:** `check.py` vergleicht mit
`HEAD:data/lessons.json`; Nummer und Clip-Liste einer committeten Lektion dürfen
sich nicht mehr ändern (Titel und Themen schon). So hängen Fortschritt, Tests und
Untertitel nie an der falschen Aufnahme. Verschwindet eine kuratierte Aufnahme aus
dem Portal, bricht `build.py` ab und academy.json bleibt, wie sie ist.

Zum Semesterende `"running": false` setzen – dann öffnet die Abschlussprüfung.

## Oberfläche

- Hell und dunkel nach Systemeinstellung, unter *Einstellungen* fest wählbar.
- Startseite zeigt den nächsten Schritt: angefangene Lektion, offenen Test dazu,
  nächste Lektion oder Abschlussprüfung – dazu Tagesziel und die letzten sieben Tage.
- Lektionen aus mehreren Clips zeigen eine Clip-Liste; am Clip-Ende geht es
  automatisch weiter, ±10 s wirken über Clip-Grenzen, Tempo und Untertitel wechseln mit.
- Tests per Tastatur: A–D oder 1–4 wählt, Enter geht weiter. Nach dem Test
  stehen die falsch beantworteten Fragen mit Begründung zum Nachlesen da.
- Lernzeit zählt echte Zeit beim Abspielen (Uhr, nicht Videoposition): Sprünge,
  Pausen und Puffern zählen nicht, bei 1,5× zählt eine Videominute 40 s.
- Laufende Kurse tragen „Läuft“; ihre Abschlussprüfung öffnet erst nach Kursende.
- Fortschritt in `localStorage` unter `academy.v1` (Lektionsschlüssel `<kurs>/<nr>`);
  mehrere offene Tabs gleichen sich über das `storage`-Ereignis ab.
- `python3 scripts/smoke.py` prüft alle Routen hell und dunkel bei 1440, 390 und
  360 px, Clip-Lektionen (mit Testkurs), den Test per Tastatur, zwei Tabs und die
  Einstellungen – offline, Videos werden abgebrochen. `--stream` spielt zusätzlich
  echte ETH-Videos stumm ab (Fortsetzen, Clip-Folge, Lernzeit, „geschaut“); nichts
  wird gespeichert oder aufgezeichnet. Braucht `pip install playwright` und
  `python3 -m playwright install chromium`.

## Wie das Material geprüft wurde

Das ETH-Videoportal ist fast vollständig login-gesperrt. Ob eine Lektion
wirklich öffentlich ist, erkennt man **nicht** am Typ `AuthorizedEvent` – der
erscheint auch bei gesperrten Videos. Entscheidend ist, ob
`authorizedData.tracks` befüllt ist. Gegengeprüft wird zusätzlich mit einem
Bereichsabruf auf die Videodatei (Antwort 206, `video/mp4`). Der Server leitet
dabei zuerst mit 302 von `dist.tobira.ethz.ch` auf `dist01`/`dist02` um – der
Abruf muss der Weiterleitung folgen. Am 23.09. waren alle 55 Aufnahmen der
vier ETH-Kurse so geprüft öffentlich.

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
- **Wochenpflege der laufenden Kurse** (siehe oben), bis Semesterende.
- **Alte Untertitel-Dateien** `transcripts/theoinf/NN.*` und
  `transcripts/architektur/NN.*` werden nicht mehr benutzt (die App liest jetzt
  `<opencastId>.vtt`) und können gelöscht werden.
- **Fortschritt liegt nur im Browser** (localStorage). Vor einem Rechnerwechsel
  unter *Einstellungen* als Datei sichern.
