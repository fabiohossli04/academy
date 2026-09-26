# Handoff

Stand: 26.09.2026. Alles läuft, nichts ist halbfertig.

## Was das ist

Eine persönliche Lernoberfläche für 30 Minuten am Tag. Sieben Kurse,
88 Lektionen, 440 selbst geschriebene Testfragen, dazu ein Claude-Tutor neben dem Video.
Start mit `./start.sh`.

| Kurs | id | Lektionen | Umfang | Tests |
|---|---|---|---|---|
| Theoretische Informatik (ETH, Komm, HS23, deutsch) | `theoinf` | 24 | 34,9 h | 120 |
| Lineare Algebra I (ETH, Einsiedler, HS22, deutsch, ohne Untertitel) | `linalg` | 27 | 40,5 h | 135 |
| Analysis I: eine Variable (ETH, Einsiedler, HS26, deutsch, **läuft**) | `analysis` | 3 | 4,3 h | 15 |
| Digital Design und Rechnerarchitektur (ETH, Mutlu, FS25, englisch) | `architektur` | 22 | 33,7 h | 110 |
| Funktionale Programmierung in Scala (EPFL, Odersky) | `scala` | 7 | extern | 35 |
| Privacy Enhancing Technologies (ETH, Tramèr, HS26, englisch, **läuft**) | `privacy` | 3 | 3,1 h | 15 |
| Software Engineering (ETH, Lüthi, HS26, englisch, **läuft**, Kurzclips pro Woche) | `software` | 2 | 0,5 h | 10 |

## Vier Regeln, die nicht gebrochen werden dürfen

1. **Videos werden gestreamt, nie heruntergeladen.** Die App ist ein Abspieler,
   kein Archiv; der Player blendet das Download-Menü aus
   (`controlslist="nodownload"`). Auf dem Rechner waren zuletzt rund 30 GB frei –
   117 h Video passen da ohnehin nicht hin.
2. **`transcripts/` bleibt gitignored.** Das Repo ist öffentlich. Der Ordner
   enthält die Untertitel der ETH-Vorlesungen, also fremdes Material. Er liegt
   lokal, weil der ETH-Server keine CORS-Kopfzeile schickt und der Browser die
   Dateien sonst nicht einbinden darf. Dasselbe gilt für Skripte und
   Arbeitsmaterial der Vorlesungen: nur lokal, nie ins Repo.
3. **Testfragen bleiben eigene Formulierungen.** Sie prüfen Verständnis des
   Themas und geben keine Vorlesungsinhalte wieder. Untertitel und Skripte sind
   nur Arbeitsgrundlage.
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
   check.py und muster.py prüfen nur Form und Rate-Muster, **nicht, ob eine
   Frage fachlich stimmt**. Neue Fragen deshalb selbst lösen oder unabhängig
   blind lösen lassen (so geschehen für linalg und analysis am 24.09.).

## Aufbau

```
index.html  app.js  styles.css     Oberfläche, kein Build-Schritt
scripts/serve.py                   lokaler Server (127.0.0.1): Oberfläche + Claude-Tutor über dein Abo
scripts/tutor_prompt.md            Systemprompt des Tutors
data/lessons.json                  EINE Autorität für Stream-Kurse: Kursdaten, Lektionen mit fester Nummer und Clip-Liste (opencastIds)
data/academy.json                  gebaut aus lessons.json + Portal-Rohdaten – nie von Hand ändern
data/quiz/<kurs>.json              Testfragen, Schlüssel = Lektionsnummer
scripts/fetch.py                   zieht Metadaten aller Kurse aus lessons.json aus dem ETH-Videoportal (Video: höchste Auflösung bis 720p)
scripts/transcripts.py             lädt Untertitel nach opencastId (.vtt für den Player, .txt zum Lesen)
scripts/build.py                   baut academy.json, prüft den Kandidaten und schreibt nur, wenn alles gültig ist
scripts/check.py                   Vollständigkeits- und Plausibilitätsprüfung, inkl. Schutz veröffentlichter Lektionen
scripts/muster.py                  misst Rate-Muster in einer Quizdatei (Länge, Wortwahl, Satzzeichen …)
scripts/smoke.py                   Oberflächentest mit Playwright (optional, --stream mit echter Wiedergabe)
scripts/test_serve.py              Tests des Tutor-Servers (mit scripts/fake_claude.py, nie echtes Claude)
transcripts/                       lokal, gitignored
```

Optionale Felder in `lessons.json`:

- `"captions": false` am Kurs – der Kurs hat keine Untertitel (heute nur
  `linalg`). transcripts.py überspringt ihn, die Clips bekommen keine
  Untertitelspur. Bei allen anderen Kursen ist eine fehlende Untertitel-URL im
  Portal ein Fehler – so verschwinden Untertitel nie still.
- `"creators": [...]` am Kurs oder an einer Lektion – ersetzt die Dozenten aus
  dem Portal (Vorrang: Lektion vor Kurs vor Portal). Eine leere Liste zeigt
  keinen Namen. Das Portal nennt bei `linalg` auch den Dozenten der englischen
  Parallelvorlesung; die Lektionen 8 und 9 hielt eine Vertretung, deren Name
  nicht bekannt ist.

Komplett neu aufbauen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py \
  && python3 scripts/build.py && python3 scripts/check.py
```

`build.py --dry-run` prüft und berichtet, ohne academy.json anzufassen.
`fetch.py --selftest` prüft die Auswahl der Videospur ohne Netz.

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

`analysis`, `privacy` und `software` werden wöchentlich ergänzt. Ablauf:

1. `python3 scripts/fetch.py && python3 scripts/transcripts.py`
2. `python3 scripts/build.py --dry-run` – listet „neu im Portal, noch nicht
   aufgenommen: <kurs> <Datum> '<Titel>' <opencastId>“.
3. In `data/lessons.json` eine **neue** Lektion mit der nächsten Nummer anlegen:
   Titel und Themen aus dem Inhalt (die Untertitel liegen unter
   `transcripts/<kurs>/<opencastId>.txt`), `clips` = die opencastIds in
   Aufnahmereihenfolge. `analysis` und `privacy`: eine Lektion pro Vorlesung.
   `software`: eine Lektion pro Woche; kommen zu einer bereits aufgenommenen
   Woche Clips nach, werden sie eine neue Lektion („Woche 3, Nachtrag“).
   Fehlen einer neuen Aufnahme noch die Untertitel, meldet transcripts.py einen
   Fehler – dann die Aufnahme noch nicht aufnehmen und später erneut versuchen.
4. Fünf eigene Fragen unter der neuen Nummer in `data/quiz/<kurs>.json`,
   dann `muster.py --strict`, und jede Frage selbst lösen.
5. `python3 scripts/build.py && python3 scripts/check.py`, dann committen.

**Veröffentlichte Lektionen sind unveränderlich:** `check.py` vergleicht mit
`main:data/lessons.json` (fehlt `main`, mit HEAD); Nummer und Clip-Liste einer
veröffentlichten Lektion dürfen sich nicht mehr ändern (Titel, Themen und
`creators` schon). So hängen Fortschritt, Tests und Untertitel nie an der
falschen Aufnahme. Auf einem Branch bleiben neue Lektionen bis zum Merge
änderbar. Verschwindet eine kuratierte Aufnahme aus dem Portal, bricht
`build.py` ab und academy.json bleibt, wie sie ist.

Zum Semesterende `"running": false` setzen – dann öffnet die Abschlussprüfung.

## Oberfläche

- Hell und dunkel nach Systemeinstellung, unter *Einstellungen* fest wählbar.
- Startseite zeigt den nächsten Schritt: angefangene Lektion, offenen Test dazu,
  nächste Lektion oder Abschlussprüfung – dazu Tagesziel und die letzten sieben Tage.
- Lektionen aus mehreren Clips zeigen eine Clip-Liste; am Clip-Ende geht es
  automatisch weiter, ±10 s wirken über Clip-Grenzen, Tempo und Untertitel wechseln mit.
  Clips ohne Untertitel (Lineare Algebra) spielen einfach ohne Untertitelspur.
- Tests per Tastatur: A–D oder 1–4 wählt, Enter geht weiter. Nach dem Test
  stehen die falsch beantworteten Fragen mit Begründung zum Nachlesen da.
- Lernzeit zählt echte Zeit beim Abspielen (Uhr, nicht Videoposition): Sprünge,
  Pausen und Puffern zählen nicht, bei 1,5× zählt eine Videominute 40 s.
- Laufende Kurse tragen „Läuft“; ihre Abschlussprüfung öffnet erst nach Kursende.
- Fortschritt in `localStorage` unter `academy.v1` (Lektionsschlüssel `<kurs>/<nr>`);
  mehrere offene Tabs gleichen sich über das `storage`-Ereignis ab.
- `python3 scripts/smoke.py` prüft alle Routen hell und dunkel bei 1440, 390 und
  360 px, Clip-Lektionen (mit Testkurs, auch gemischt mit und ohne Untertitel),
  den Test per Tastatur, zwei Tabs und die Einstellungen – offline, Videos werden
  abgebrochen. `--stream` spielt zusätzlich echte ETH-Videos stumm ab
  (Fortsetzen, Clip-Folge, Lernzeit, „geschaut“, Clip ohne Untertitel); nichts
  wird gespeichert oder aufgezeichnet. Braucht `pip install playwright` und
  `python3 -m playwright install chromium`.

## Claude-Tutor („Frag Claude“)

Auf jeder Lektionsseite steht neben dem Video (auf dem Handy darunter) ein Chat mit Claude. Jede Frage trägt die
aktuelle Videoposition; Claude bekommt dazu Kurs, Lektion, Themen und – wo es Untertitel gibt – den Ausschnitt der
letzten vier Minuten vor dieser Stelle. Modell „Gründlich“ = Claude Opus 5 (mittlere Denktiefe), „Schnell“ = Claude Sonnet 5 (niedrige Denktiefe,
erstes Wort meist nach 1–2 s).

- **Läuft über dein Claude-Abo, nicht über die API.** Der lokale Server `scripts/serve.py` startet pro Frage
  `claude -p` (Claude Code im Kopf-los-Modus) mit deinem Login. Voraussetzung: `claude` ist installiert und
  angemeldet (im Terminal `claude`, dann `/login`). Jede Frage zählt auf dein Abo-Kontingent.
- **Nur für dich.** Anthropic erlaubt den claude.ai-Login nicht in Produkten für andere. Der Server lauscht deshalb
  nur auf 127.0.0.1, und der Tutor gehört nicht in die iPhone-App.
- **Abgeschottet:** `--safe-mode`, `--disable-slash-commands`, `--tools ""` (keine Werkzeuge), `--strict-mcp-config`,
  `--setting-sources project`, `--no-session-persistence`, eigener leerer Arbeitsordner `~/.academy-tutor` und eine
  bereinigte Umgebung ohne `ANTHROPIC_*`-Variablen. Meldet Claude beim Start etwas anderes als den Abo-Login
  (`apiKeySource: none`) oder Werkzeuge, bricht der Server ab. `--bare` geht nicht: es kennt nur API-Schlüssel.
- **Daten:** Frage, bisheriger Verlauf der Lektion und der Untertitel-Ausschnitt gehen an Anthropic, wie bei jeder
  Claude-Nutzung. Gespeichert wird der Verlauf nur im Browser (`academy.tutor.v1`, nicht im Fortschritts-Export;
  löschen unter *Einstellungen*). Claude Code legt dank `--no-session-persistence` keine Sitzungen ab.
- **Start:** `./start.sh` startet den Server (Port 8777, Protokoll in `~/.academy-tutor/server.log`) und öffnet den
  Browser. Läuft auf dem Port ein anderer Server, meldet es das und beendet nichts.
- **Schutz des Endpunkts:** exakter Host-Header, gleiche Herkunft (Origin) und ein Token pro Serverstart; höchstens
  zwei Fragen gleichzeitig; statische Dateien nur per Positivliste.
- **Tests:** `python3 -m unittest discover -s scripts -p test_serve.py` und `scripts/smoke.py` (ohne und mit
  Tutor-Server) arbeiten ausschließlich mit `scripts/fake_claude.py` – nie mit echten Claude-Aufrufen.
- **Modell-IDs fest:** `claude-opus-5` und `claude-sonnet-5`. Der Alias `opus` zeigt in CLI 2.1.267 auf ein
  Modell, das diese Version noch nicht kennt.

## Wie das Material geprüft wurde

Das ETH-Videoportal ist fast vollständig login-gesperrt. Ob eine Lektion
wirklich öffentlich ist, erkennt man **nicht** am Typ `AuthorizedEvent` – der
erscheint auch bei gesperrten Videos. Entscheidend ist, ob
`authorizedData.tracks` befüllt ist. Gegengeprüft wird zusätzlich mit einem
Bereichsabruf auf die Videodatei (Antwort 206, `video/mp4`). Der Server leitet
dabei zuerst mit 302 von `dist.tobira.ethz.ch` auf `dist01`/`dist02` um – der
Abruf muss der Weiterleitung folgen. Am 24.09. waren alle 85 Aufnahmen der
sechs ETH-Kurse so geprüft öffentlich (720p-Spur). Bis zum 24.09. wählte
fetch.py wegen eines Sortierfehlers die 360p-Spur.

Abfrage gegen `https://video.ethz.ch/graphql`, anonym:

```graphql
{ realmByPath(path: "/lectures/d-infk/2023/autumn/252-0057-00L") {
    blocks { ... on SeriesBlock { series { entries {
      ... on AuthorizedEvent { authorizedData { tracks { uri } } } } } } } } }
```

**Lineare Algebra I** hat keine Untertitel. Die Kursseite
(metaphor.ethz.ch, 401-1151-00L, HS22) nennt pro Termin Skriptabschnitte, die
aber nicht immer mit dem tatsächlich behandelten Stoff übereinstimmen. Titel und
Themen aller 27 Lektionen stammen deshalb aus Standbildern der Tafel (sechs pro
Vorlesung, im Browser aus dem Stream aufgenommen, nicht gespeichert). Die
Testfragen bauen auf dem öffentlichen deutschen Skript von Dr. Menny Akka
Ginosar und diesen Tafelbelegen auf und wurden unabhängig blind nachgelöst.
**Analysis I** hat deutsche Untertitel; die Kursbeschreibung im
Vorlesungsverzeichnis (401-1261-07L) nennt Zahlen, Folgen und Reihen,
Stetigkeit, Ableitung, Differentialgleichungen und Riemann-Integral.

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
