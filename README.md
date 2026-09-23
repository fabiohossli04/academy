# Academy

Eine kleine persoenliche Lernoberflaeche fuer drei Kurse, ausgelegt auf 30 Minuten am Tag.

## Starten

```bash
./start.sh
```

Oeffnet `http://127.0.0.1:8777/`. Ein lokaler Server ist noetig, weil die App ihre
Daten per `fetch` laedt - ein Doppelklick auf `index.html` reicht nicht.

## Was drin ist

| Kurs | Quelle | Umfang |
|---|---|---|
| Theoretische Informatik | ETH Zuerich, Dennis Komm, HS 2023 (deutsch) | 24 Lektionen, 34,9 h |
| Digital Design und Rechnerarchitektur | ETH Zuerich, Onur Mutlu, FS 2025 (englisch) | 22 Lektionen, 33,7 h |
| Funktionale Programmierung in Scala | EPFL, Martin Odersky, Coursera | 7 Wochen, extern |

## Wie das Material eingebunden ist

Die beiden ETH-Kurse sind oeffentlich zugaenglich. Die Videos werden **direkt vom
ETH-Server gestreamt** - diese App kopiert und verbreitet kein Videomaterial, sie ist
ein Abspieler mit Fortschrittsverwaltung.

Die Untertitel liegen lokal unter `transcripts/`, weil der ETH-Server keine
CORS-Kopfzeile schickt und der Browser sie sonst nicht einbinden darf. Dieser Ordner
ist bewusst per `.gitignore` ausgeschlossen: er enthaelt fremdes Material und gehoert
nicht in ein Repository.

Der Scala-Kurs liegt hinter dem Coursera-Login und wird nur verlinkt. Die zugehoerigen
EPFL-Folien sind frei abrufbar und direkt verlinkt.

Die Testfragen sind eigens geschrieben und geben keine Vorlesungsinhalte wieder.

## Aufbau

```
index.html  app.js  styles.css     Oberflaeche
data/academy.json                  Kurse und Lektionen
data/quiz/<kurs>.json              Testfragen
scripts/fetch.py                   Metadaten aus dem ETH-Portal ziehen
scripts/transcripts.py             Untertitel holen
scripts/build.py                   academy.json bauen
transcripts/                       lokal, gitignored
```

Neu aufbauen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py && python3 scripts/build.py
```

## Fortschritt

Liegt ausschliesslich im Browser (localStorage). Unter *Einstellungen* laesst er sich
als Datei sichern und wieder einlesen - vor einem Rechnerwechsel unbedingt exportieren.
