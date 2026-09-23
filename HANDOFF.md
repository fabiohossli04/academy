# Handoff

Stand: 23.09.2026. Alles laeuft, nichts ist halbfertig.

## Was das ist

Eine persoenliche Lernoberflaeche fuer 30 Minuten am Tag. Drei Kurse,
53 Lektionen, 265 selbst geschriebene Testfragen. Start mit `./start.sh`.

| Kurs | id | Lektionen | Umfang | Tests |
|---|---|---|---|---|
| Theoretische Informatik (ETH, Komm, HS23, deutsch) | `theoinf` | 24 | 34,9 h | 120 |
| Digital Design und Rechnerarchitektur (ETH, Mutlu, FS25, englisch) | `architektur` | 22 | 33,7 h | 110 |
| Funktionale Programmierung in Scala (EPFL, Odersky) | `scala` | 7 | extern | 35 |

## Vier Regeln, die nicht gebrochen werden duerfen

1. **Videos werden gestreamt, nie heruntergeladen.** Die App ist ein Abspieler,
   kein Archiv. Auf dem Rechner waren zuletzt 32 GB frei - 68 h Video passen da
   ohnehin nicht hin.
2. **`transcripts/` bleibt gitignored.** Das Repo ist oeffentlich. Der Ordner
   enthaelt die Untertitel der ETH-Vorlesungen, also fremdes Material. Er liegt
   lokal, weil der ETH-Server keine CORS-Kopfzeile schickt und der Browser die
   Dateien sonst nicht einbinden darf.
3. **Testfragen bleiben eigene Formulierungen.** Sie pruefen Verstaendnis des
   Themas und geben keine Vorlesungsinhalte wieder.
4. **`python3 scripts/check.py` muss gruen sein**, bevor etwas committet wird.
   Die Routine schlaegt unter anderem fehl, wenn die richtige Antwort bei mehr
   als 45 % der Fragen an derselben Position steht. Genau das war beim ersten
   Durchgang der Fall (94-100 % auf Position 2) und wurde durch Mischen behoben.

## Aufbau

```
index.html  app.js  styles.css     Oberflaeche, kein Build-Schritt
data/academy.json                  Kurse, Lektionen, Video- und Untertitel-URLs
data/quiz/<kurs>.json              Testfragen, Schluessel = Lektionsnummer
scripts/fetch.py                   zieht Metadaten aus dem ETH-Videoportal
scripts/transcripts.py             laedt Untertitel (.vtt fuer den Player, .txt zum Lesen)
scripts/build.py                   Titel + Rohdaten -> data/academy.json
scripts/check.py                   Vollstaendigkeits- und Plausibilitaetspruefung
transcripts/                       lokal, gitignored
```

Komplett neu aufbauen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py \
  && python3 scripts/build.py && python3 scripts/check.py
```

Format einer Frage:

```json
{ "q": "Frage?", "options": ["a","b","c","d"], "answer": 2, "why": "Begruendung." }
```

`answer` ist der Index der richtigen Antwort. Nach jedem Hinzufuegen `check.py`
laufen lassen und bei einseitiger Verteilung mischen.

## Wie das Material geprueft wurde

Das ETH-Videoportal ist fast vollstaendig login-gesperrt. Ob eine Lektion
wirklich oeffentlich ist, erkennt man **nicht** am Typ `AuthorizedEvent` - der
erscheint auch bei gesperrten Videos. Entscheidend ist, ob
`authorizedData.tracks` befuellt ist. Gegengeprueft wurde zusaetzlich mit einem
Bereichsabruf auf die Videodatei (Antwort 206, `video/mp4`).

Abfrage gegen `https://video.ethz.ch/graphql`, anonym:

```graphql
{ realmByPath(path: "/lectures/d-infk/2023/autumn/252-0057-00L") {
    blocks { ... on SeriesBlock { series { entries {
      ... on AuthorizedEvent { authorizedData { tracks { uri } } } } } } } } }
```

## Was offen ist

- **Noch nicht gepusht.** Das Repo ist oeffentlich; der erste Push sollte
  bewusst passieren: `git push -u origin main`
- **Scala-Videos sind nicht eingebettet**, weil sie hinter dem Coursera-Login
  liegen. Verlinkt sind der Kurs und die frei abrufbaren EPFL-Folien. Die
  Fragen dort stammen aus dem veroeffentlichten Kursplan, nicht aus den Videos -
  das steht auch so in der App.
- **Laufende Kurse als Nachschub:** ETH veroeffentlicht gerade woechentlich
  *Privacy Enhancing Technologies* (HS26, Tramer) und *Software Engineering*
  (HS26, Luethi, Kurzclips von 2-7 min). Beide sind oeffentlich und liessen sich
  mit `scripts/fetch.py` als vierter und fuenfter Kurs aufnehmen.
- **Fortschritt liegt nur im Browser** (localStorage). Vor einem Rechnerwechsel
  unter *Einstellungen* exportieren.
