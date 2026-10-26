# Projekt: ZeitHit (Arbeitstitel) – Musik-Zeitleistenspiel als PWA

> Diese Datei ist der komplette Auftrag. Lies sie vollständig, bevor du etwas tust.
> Arbeite die Phasen der Reihe nach ab, committe nach jeder Phase und frage nur nach,
> wenn hier etwas wirklich fehlt. Der Nutzer heißt Robin und spricht Deutsch.

## 1. Ziel

Eine Web-App (PWA) für das iPhone, die einen QR-Code auf einer Spielkarte scannt und den
dazugehörigen Song über den YouTube-IFrame-Player abspielt. Das Cover/Video bleibt verdeckt.
Jahr, Titel und Interpret zeigt die App **nicht** – die stehen auf der Kartenrückseite. Dazu gehört ein
Generator, der druckbare, doppelseitige Karten (Vorder-/Rückseite) als PDF erzeugt.

Das Spielprinzip (Songs nach Erscheinungsjahr in eine Zeitleiste einsortieren) liegt
bei den Menschen am Tisch, nicht in der App. Die App ist nur Scanner + verdeckter Player.

**Wichtig:** Den Namen „Hitster" und dessen Logo/Design NICHT verwenden. Eigener Name
(`appName` in `config.json`), eigenes Design.

## 2. Feste Entscheidungen (nicht neu diskutieren)

- **Hosting:** GitHub Pages, öffentliches Repo `zeithit`, Branch `main`, Root `/`.
- **Technik:** Vanilla HTML/CSS/JavaScript (ES-Module). **Kein Build-Schritt, kein Framework.**
- **Alle Pfade relativ** (`./app.js`), weil die App unter `/zeithit/` läuft.
- **QR-Scanner:** `html5-qrcode`, als Datei lokal in `vendor/` abgelegt (nicht per CDN), damit
  die App offline startet. Version pinnen und die Version in `vendor/README.md` notieren.
- **Musik:** nur YouTube-IDs im Repo. **Niemals MP3s oder andere Audiodateien ins Repo legen**
  (öffentliches Repo = Verbreitung geschützter Musik).
- **Schriften selbst hosten** (DSGVO, offline): Bebas Neue (Überschriften/Jahr) und Inter
  (Text), beide OFL-lizenziert, als `.woff2` in `fonts/` (z. B. von fontsource herunterladen).
- **Kartengenerator:** Python 3 mit `segno` (QR als SVG), `reportlab` (PDF), `Pillow` (Icons).
- **Editor:** VS Code-Projekt (Dateien `.vscode/` anlegen, siehe Phase 1).

## 3. Voraussetzungen (prüfe zuerst, melde Fehlendes an Robin)

```bash
git --version
gh --version && gh auth status      # falls nicht angemeldet: Robin muss `gh auth login` ausführen
python3 --version
pip install segno reportlab pillow  # ggf. in einer venv (.venv, in .gitignore)
```

GitHub-Benutzername ermitteln: `gh api user --jq .login`. Daraus ergibt sich die Basis-URL
`https://<USER>.github.io/zeithit/` und wird in `config.json` gespeichert.

## 4. Projektstruktur

```
zeithit/
  CLAUDE.md                 (diese Datei)
  README.md                 (kurze Anleitung für Robin, deutsch)
  index.html
  app.js
  style.css
  songs.json
  config.json               {"appName": "ZeitHit", "baseUrl": "https://<USER>.github.io/zeithit/"}
  manifest.json
  sw.js
  icons/                    icon-180.png, icon-192.png, icon-512.png
  fonts/                    BebasNeue-Regular.woff2, Inter-*.woff2
  vendor/                   html5-qrcode.min.js, README.md
  tools/
    make_cards.py           PDF-Generator
    make_icons.py           Icons mit Pillow erzeugen
    add_song.py             Song per YouTube-URL hinzufügen
    check_songs.py          Einbettbarkeit prüfen
  cards/                    erzeugte PDFs (in .gitignore)
  .vscode/                  settings.json, extensions.json, tasks.json
  .gitignore
```

## 5. Datenformat `songs.json`

```json
[
  { "id": "001", "yt": "VIDEO_ID", "start": 0, "title": "Titel",
    "artist": "Interpret", "year": 1985 }
]
```

- `id`: dreistellig als String, fortlaufend, steht im QR-Code.
- `start`: Sekunden, ab denen abgespielt wird (Intros überspringen), Standard 0.
- Keine erfundenen Video-IDs! Lege zum Start 3 Platzhalter mit `"yt": "TODO"` an.
  Die App ignoriert/markiert Einträge mit `TODO`. Robin trägt echte Songs über
  `tools/add_song.py` ein.

## 6. App-Spezifikation

**QR-Inhalt:** `<baseUrl>#<id>`, z. B. `https://robin.github.io/zeithit/#042`.
Die App akzeptiert beim Scan sowohl die volle URL als auch nur die ID (`/(\d{3})$/`).
Wird die URL mit der normalen iPhone-Kamera gescannt, öffnet sie die App, und das
`hashchange`/Start-Hash lädt die Karte direkt.

**Ablauf:** App öffnen → Scanner startet sofort → Scan → Song spielt verdeckt → „Nächste Karte" → Scanner.

**Bildschirme / UI** (geändert auf Robins Wunsch, 2026-10-15: keine Auflösung in der App):
1. **Scanner** (startet automatisch): Rückkamera (`facingMode: "environment"`), `fps: 10`.
   Nach erfolgreichem Scan Scanner stoppen, Doppelscans entprellen. Bei Kamerafehler Meldung
   und „Erneut versuchen".
2. **Player:** Song startet nach dem Scan automatisch; blockt iOS das, erscheint „Zum Abspielen
   tippen" und ein Tipp auf den großen runden Play/Pause-Button reicht. Außerdem nur
   „Nächste Karte". Der YouTube-Player liegt unter einem undurchsichtigen Overlay
   (Equalizer-Animation), nichts vom Video ist sichtbar. Kein Jahr, Titel oder Interpret.
3. **Hinweis-Bildschirm** (nur im Fehlerfall, z. B. unbekannte Karte): Meldung + „Karte scannen".

**YouTube:** IFrame-Player-API (`https://www.youtube.com/iframe_api`), `playerVars`:
`controls:0, modestbranding:1, playsinline:1, rel:0, start:<start>`. Lädt die API nicht
(offline), zeige eine klare Meldung („Für die Musik wird Internet gebraucht"), die App
selbst muss trotzdem starten. Optional: Wake Lock API, damit das Display an bleibt.

**Hinweis (nur in README erwähnen):** Das Verdecken des Players ist für den privaten
Gebrauch gedacht. YouTube-Richtlinien verlangen grundsätzlich einen sichtbaren Player.

**Nicht im Umfang:** Punktezählung, Teams, Multiplayer, Konto, Backend.

## 7. PWA-Anforderungen

- `manifest.json`: `name`, `short_name`, `start_url: "./"`, `scope: "./"`,
  `display: "standalone"`, `background_color`/`theme_color` aus dem Style-Schema, Icons.
- `index.html`: `viewport-fit=cover`, `apple-touch-icon` (180 px),
  `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style=black-translucent`,
  Safe-Area-Abstände (`env(safe-area-inset-*)`).
- `sw.js`: Konstante `CACHE = "zeithit-v1"`. Beim Install alle App-Dateien vorab cachen
  (index, app.js, style.css, songs.json, manifest, Icons, Fonts, vendor). Strategie:
  Cache-First für App-Dateien, Stale-While-Revalidate für `songs.json`. Anfragen an
  fremde Domains (youtube.com, ytimg.com …) **nicht** abfangen. `skipWaiting` +
  `clients.claim`, alte Caches beim Aktivieren löschen. Bei jeder Veröffentlichung die
  Cache-Version erhöhen.
- Icons mit `tools/make_icons.py` erzeugen (Pillow, einfaches Motiv im Style-Schema).

## 8. Style-Schema (als CSS-Variablen in `:root`)

Geändert auf Robins Wunsch (2026-10-15): weg vom bunten Retro-Look, hin zu **Schwarz/Rot, düster**.

| Variable | Wert |
|---|---|
| `--bg` | `#070607` |
| `--surface` | `#141012` |
| `--line` | `#2A1D20` |
| `--primary` (Rot) | `#C4161C` |
| `--primary-hi` | `#E3262D` |
| `--text` | `#ECE6E6` |
| `--muted` | `#8C8184` |

Keine Jahrzehntfarben mehr (Jahr auf der Karte einheitlich in Rot). Schriften: Bebas Neue
(Überschriften, Jahr, gesperrt), Inter (Text). UI: dunkler Hintergrund mit rotem Glimmen von
unten, eckigere Buttons mit Versalien, roter Play-Button, Sucher-Ecken im Scanner,
Bedienelemente im unteren Daumenbereich.

## 9. Kartengenerator `tools/make_cards.py`

- Karte: **60 × 60 mm** beschnitten, **3 mm Beschnitt** (gezeichnet 66 × 66 mm).
- A4-Seite, **3 Spalten × 4 Reihen = 12 Karten**, Schnittmarken an den Ecken.
- Ausgabe `cards/cards.pdf`: abwechselnd Seite „Vorderseiten" und Seite „Rückseiten".
- **Vorderseite:** schwarzer Hintergrund mit dunkelrotem Glimmen, weißer QR-Block mit Ruhezone
  (ca. 38 mm, abgerundet), kein Name, keine Linie, **keine Song-Infos**.
- **Rückseite:** Jahr riesig in Rot, darunter Titel + Interpret (Schrift
  automatisch verkleinern, wenn zu lang), unten klein die ID.
- **Duplex-Spiegelung:** Für Druck „an der langen Kante wenden" die Spalten der Rückseite
  pro Reihe umkehren (Spalte c → 2 − c), sonst passen Vorder- und Rückseite nicht zusammen.
- Optionen: `--ids 1-24`, `--test` (nur eine Testseite).
- QR-Inhalt aus `config.json` (`baseUrl`) + `#<id>`; QR als SVG mit `segno`
  (Fehlerkorrektur `M`), mit reportlab (`svglib` nicht nötig, QR-Matrix direkt zeichnen).
- Fehlende/`TODO`-Songs überspringen und melden.

## 10. Hilfsskripte

- `tools/add_song.py <youtube-url> <jahr> [--start 12]`: extrahiert die Video-ID, ruft
  `https://www.youtube.com/oembed?url=<url>&format=json` ab, prüft die Einbettbarkeit
  (HTTP 200 = ok, 401/403 = nicht einbettbar, 404 = existiert nicht), schlägt Titel/Interpret
  aus dem Videotitel vor, lässt Robin bestätigen bzw. ändern und hängt den Eintrag mit der
  nächsten freien ID an `songs.json` an.
- `tools/check_songs.py`: prüft alle Einträge per oEmbed und listet Problemfälle.

## 11. VS Code

- `.vscode/extensions.json`: Empfehlung für Prettier, Live Preview (optional).
- `.vscode/settings.json`: Formatierung bei Speichern, Einrückung 2 Leerzeichen.
- `.vscode/tasks.json`: Tasks „Server starten" (`python3 -m http.server 8000`) und
  „Karten erzeugen" (`python3 tools/make_cards.py`).
- Lokal testen auf `http://localhost:8000` (Kamera funktioniert auf localhost). Zum Test am
  iPhone immer die veröffentlichte HTTPS-Seite verwenden.

## 12. Phasen (nach jeder Phase committen)

- [x] **P1 Gerüst:** Voraussetzungen prüfen, Ordner, `.gitignore`, `.vscode/`, `config.json`,
  `README.md`, leere Seite. Repo erstellen und veröffentlichen:
  ```bash
  git init -b main && git add -A && git commit -m "Initial commit"
  gh repo create zeithit --public --source=. --remote=origin --push
  gh api -X POST repos/{owner}/zeithit/pages -f "source[branch]=main" -f "source[path]=/"
  gh api repos/{owner}/zeithit/pages --jq .html_url   # URL in config.json eintragen
  ```
- [x] **P2 PWA:** Manifest, Service Worker, Icons, Fonts, Style-Grundlage.
- [x] **P3 Player:** `songs.json`, YouTube-Player, Overlay, Hash-Routing (Auflösung später auf Wunsch entfernt).
- [x] **P4 Scanner:** `html5-qrcode` lokal einbinden, Scan-Ablauf, Entprellen, Fehlermeldungen
  (Kamera verweigert, keine Kamera, unbekannte ID).
- [x] **P5 Karten:** `make_cards.py`, Testseite erzeugen und visuell prüfen.
- [x] **P6 Songs:** `add_song.py` und `check_songs.py`, README um Songpflege ergänzen.
- [ ] **P7 Abschluss:** Alles pushen, Pages-URL prüfen, Cache-Version erhöhen,
  Checkliste unten abarbeiten.

## 13. Abnahme-Checkliste (für Robin, am iPhone)

1. Veröffentlichte URL in **Safari** öffnen (mit Internet), kurz warten.
2. Teilen → **Zum Home-Bildschirm**.
3. Flugmodus an, App vom Homescreen starten: Die App öffnet sich, nur die Musik meldet „kein Internet".
4. Internet an, QR scannen: Song startet (ggf. nach Tipp auf Play), Overlay verdeckt das Video.
5. Die App zeigt weder Jahr noch Titel/Interpret; Abgleich mit der Kartenrückseite.
6. Testdruck der Karten: Vorder- und Rückseiten passen zusammen (Duplex-Spiegelung prüfen).
7. Update-Test: Änderung pushen, Cache-Version erhöhen, App einmal online öffnen, Änderung ist da.

## 14. Arbeitsregeln für dich (Claude Code)

- Keine Videos oder Audiodateien herunterladen oder ins Repo legen.
- Keine erfundenen YouTube-IDs, Songs oder Jahreszahlen.
- Kein npm-Build, kein Framework, keine Tracker oder externen CDNs zur Laufzeit.
- Kleine, klare Commits (deutsch, z. B. „P3: Player mit Overlay").
- Am Ende jeder Phase kurz berichten: was fertig ist, was Robin manuell tun muss.
- Was nur Robin tun kann: `gh auth login`, Songs auswählen, drucken, iPhone-Installation.
