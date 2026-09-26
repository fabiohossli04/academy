# Academy

Eine kleine persönliche Lernoberfläche für sieben Kurse, ausgelegt auf 30 Minuten am Tag.

## Starten

```bash
./start.sh
```

Startet den lokalen Server `scripts/serve.py` und öffnet `http://127.0.0.1:8777/`. Ein lokaler
Server ist nötig, weil die App ihre Daten per `fetch` lädt – und er beantwortet die Fragen an den
Claude-Tutor. Dafür muss Claude Code installiert und mit deinem Abo angemeldet sein (`claude`, dann `/login`).

## Was drin ist

| Kurs | Quelle | Umfang |
|---|---|---|
| Theoretische Informatik | ETH Zürich, Dennis Komm, HS 2023 (deutsch) | 24 Lektionen, 34,9 h |
| Lineare Algebra I | ETH Zürich, Manfred Einsiedler, HS 2022 (deutsch, ohne Untertitel) | 27 Lektionen, 40,5 h |
| Analysis I: eine Variable | ETH Zürich, Manfred Einsiedler, HS 2026 (deutsch, läuft) | 3 Lektionen, 4,3 h |
| Digital Design und Rechnerarchitektur | ETH Zürich, Onur Mutlu, FS 2025 (englisch) | 22 Lektionen, 33,7 h |
| Funktionale Programmierung in Scala | EPFL, Martin Odersky, Coursera | 7 Wochen, extern |
| Privacy Enhancing Technologies | ETH Zürich, Florian Tramèr, HS 2026 (englisch, läuft) | 3 Lektionen, 3,1 h |
| Software Engineering | ETH Zürich, Marcel Lüthi, HS 2026 (englisch, läuft) | 2 Wochen aus Kurzclips, 0,5 h |

Zu jeder Lektion gibt es fünf Testfragen, pro Kurs eine Abschlussprüfung. Die drei laufenden
Kurse werden wöchentlich ergänzt; wie, steht in `HANDOFF.md` unter *Laufende Kurse pflegen*.

## Bedienung

- Die Startseite zeigt, was als Nächstes dran ist, und wie weit das Tagesziel ist.
- Lektionen aus mehreren Kurzclips laufen als Clip-Liste am Stück durch.
- Im Test wählen die Tasten A–D (oder 1–4) eine Antwort, Enter geht weiter.
  Falsch beantwortete Fragen stehen danach mit Begründung zum Nachlesen da.
- Neben dem Video (auf dem Handy darunter) steht „Frag Claude“: Fragen tragen die aktuelle
  Videoposition, Claude kennt Lektion, Themen und den Untertitel-Ausschnitt davor. Läuft über dein
  Claude-Abo, nur lokal; `/` springt ins Eingabefeld.
- Hell oder dunkel folgt dem System und lässt sich unter *Einstellungen* festlegen.

## Wie das Material eingebunden ist

Die ETH-Kurse sind öffentlich zugänglich. Die Videos werden **direkt vom
ETH-Server gestreamt** – diese App kopiert und verbreitet kein Videomaterial, sie ist
ein Abspieler mit Fortschrittsverwaltung.

Die Untertitel liegen lokal unter `transcripts/`, weil der ETH-Server keine
CORS-Kopfzeile schickt und der Browser sie sonst nicht einbinden darf
(Lineare Algebra I hat keine Untertitel). Dieser Ordner
ist bewusst per `.gitignore` ausgeschlossen: er enthält fremdes Material und gehört
nicht in ein Repository.

Der Scala-Kurs liegt hinter dem Coursera-Login und wird nur verlinkt. Die zugehörigen
EPFL-Folien sind frei abrufbar und direkt verlinkt.

Die Testfragen sind eigens geschrieben und geben keine Vorlesungsinhalte wieder.

## Aufbau

```
index.html  app.js  styles.css     Oberfläche
data/lessons.json                  Kurse und Lektionen (Kuratierung, feste Nummern)
data/academy.json                  daraus gebaut, nicht von Hand ändern
data/quiz/<kurs>.json              Testfragen
scripts/fetch.py                   Metadaten aus dem ETH-Portal ziehen
scripts/transcripts.py             Untertitel holen
scripts/build.py                   academy.json bauen (schreibt nur einen geprüften Stand)
scripts/check.py                   Daten und Testfragen prüfen
scripts/muster.py                  Rate-Muster in Testfragen messen
scripts/smoke.py                   Oberfläche prüfen (Playwright, optional; --stream mit echter Wiedergabe)
scripts/serve.py                   lokaler Server mit Claude-Tutor (nur 127.0.0.1)
transcripts/                       lokal, gitignored
```

Neu aufbauen und prüfen:

```bash
python3 scripts/fetch.py && python3 scripts/transcripts.py \
  && python3 scripts/build.py && python3 scripts/check.py
```

## Fortschritt

Liegt ausschließlich im Browser (localStorage). Unter *Einstellungen* lässt er sich
als Datei sichern und wieder einlesen – vor einem Rechnerwechsel unbedingt sichern.
