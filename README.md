# ZeitHit

Musik-Zeitleistenspiel als PWA: Die App öffnet direkt die Kamera, scannt den QR-Code einer
Spielkarte und spielt den Song über den YouTube-Player ab – das Video bleibt verdeckt.
Mehr macht die App nicht: Jahr, Titel und Interpret stehen auf der Rückseite der Karte.
Das Einsortieren der Songs in die Zeitleiste passiert am Tisch.

Nach dem Scan versucht die App, den Song sofort zu starten. Blockt iOS das automatische
Abspielen, erscheint „Zum Abspielen tippen" – dann reicht ein Tipp auf den Play-Button.

Veröffentlicht unter: <https://robinbeck12.github.io/hitster/>

## Lokal testen

1. In VS Code den Task **Server starten** ausführen (`python -m http.server 8000`).
2. Im Browser `http://localhost:8000` öffnen (die Kamera funktioniert auf `localhost`).
3. Zum Test am iPhone immer die veröffentlichte HTTPS-Seite verwenden.

## Songs pflegen

Die Songs stehen in `songs.json` (nur YouTube-IDs, keine Audiodateien):

```json
{ "id": "042", "yt": "VIDEO_ID", "start": 0, "title": "Titel", "artist": "Interpret", "year": 1985 }
```

`id` (dreistellig) steht im QR-Code der Karte, `start` ist die Startsekunde (Intro überspringen).

**Song hinzufügen** (Python-Umgebung wie unter „Karten drucken" einrichten):

```bash
python tools/add_song.py "https://www.youtube.com/watch?v=VIDEO_ID" 1985
python tools/add_song.py "https://youtu.be/VIDEO_ID" 1985 --start 12
```

Das Skript prüft, ob das Video existiert und eingebettet werden darf, schlägt Titel und
Interpret aus dem Videotitel vor und fragt nach, ob du sie ändern willst. Der Song bekommt
die nächste freie ID; die `TODO`-Platzhalter vom Start werden dabei zuerst belegt.
Mit `--yes` (und optional `--title`, `--artist`) läuft es ohne Rückfragen.

**Songs aus YouTube Music übernehmen:** Einmalig `ytmusicapi browser` ausführen, die Request-Header
einer eingeloggten Anfrage von music.youtube.com einfügen und die entstandene `browser.json` nach
`tools/ytmusic_auth.json` verschieben (steht in der `.gitignore`, nie committen oder teilen). Dann:

```bash
python tools/import_history.py --source likes --limit 200   # oder library / history
```

Das Skript listet neue Titel mit Albumjahr und Einbettbarkeit. Du wählst per Nummer aus und
bestätigst jedes Jahr einzeln, weil das Albumjahr bei Compilations vom Originaljahr abweichen kann.

**Alle Songs prüfen:**

```bash
python tools/check_songs.py
```

Das listet Einträge auf, deren Video gelöscht, privat oder nicht mehr einbettbar ist, sowie
doppelte IDs/Videos und unplausible Felder. Danach `python tools/make_cards.py` für die Karten.

**Veröffentlichen:** `songs.json` committen und pushen. Die App holt die neue Liste beim
nächsten Öffnen mit Internet (Stale-While-Revalidate), eventuell erst nach einem zweiten Start.

## Karten drucken

Einmalig die Python-Umgebung einrichten (Python 3 nötig):

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r tools/requirements.txt   # macOS/Linux: .venv/bin/python
```

Karten erzeugen (Ausgabe: `cards/cards.pdf`, wird nicht ins Repo committet):

```bash
python tools/make_cards.py              # alle Songs mit echter YouTube-ID
python tools/make_cards.py --ids 1-24   # nur bestimmte IDs, z. B. 1-12,30
python tools/make_cards.py --test       # Testseite mit Beispieldaten (cards/test.pdf)
```

- Karte: 60 × 60 mm, 3 mm Beschnitt, 12 Karten pro A4-Seite (3 × 4) mit Schnittmarken an den Ecken.
- Das PDF enthält abwechselnd eine Seite Vorderseiten (QR-Code) und eine Seite Rückseiten
  (Jahr, Titel, Interpret).
- Drucken: **doppelseitig, „an der langen Kante wenden"**, Skalierung **100 %** (nicht „an Seite anpassen").
  Die Rückseiten sind dafür pro Reihe gespiegelt angeordnet.
- Songs ohne echte YouTube-ID (`TODO`) werden übersprungen und gemeldet.

## Projektstand

Die Umsetzung läuft in Phasen (siehe `CLAUDE.md`, Abschnitt 12).

## Hinweis zu YouTube

Das Verdecken des Players ist für den privaten Gebrauch gedacht. Die YouTube-Richtlinien
verlangen grundsätzlich einen sichtbaren Player.
