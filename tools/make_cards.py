"""Erzeugt druckbare, doppelseitige Spielkarten als PDF (cards/cards.pdf).

Karte: 60 x 60 mm beschnitten, 3 mm Beschnitt (gezeichnet 66 x 66 mm).
A4-Seite mit 3 Spalten x 4 Reihen = 12 Karten. Die Seiten wechseln sich ab:
Vorderseiten (QR-Code) und Rückseiten (Jahr, Titel, Interpret).

Aufruf:
    python tools/make_cards.py              # alle Songs
    python tools/make_cards.py --ids 1-24   # nur diese IDs (z. B. 1-24,30,31)
    python tools/make_cards.py --test       # eine Testseite mit Beispieldaten
    python tools/make_cards.py --photo      # JPGs für 15 x 20 cm Fotoabzüge (cards/photo/)

Druck: doppelseitig, "an der langen Kante wenden", Skalierung 100 % (nicht "an Seite anpassen").

Foto-Modus: 2 x 3 Karten pro 15 x 20 cm Abzug, Vorder- und Rückseiten als getrennte Bilder
(NN_vorne.jpg / NN_hinten.jpg). Gleiche Nummern Rücken an Rücken zusammenkleben und an den
Schnittmarken in einem Zug schneiden. Beschnitt gibt es nur an den Außenkanten des Gitters.
"""

import argparse
import json
import sys
from pathlib import Path

import segno
from fontTools.ttLib import TTFont
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont as RLTTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "fonts"
CARDS_DIR = ROOT / "cards"
FONT_CACHE = CARDS_DIR / ".fonts"

# ---------- Maße ----------
PAGE_W, PAGE_H = 210 * mm, 297 * mm
TRIM = 60 * mm
BLEED = 3 * mm
BOX = TRIM + 2 * BLEED  # 66 mm
COLS, ROWS = 3, 4
PER_PAGE = COLS * ROWS
GRID_W, GRID_H = COLS * BOX, ROWS * BOX
ORIGIN_X = (PAGE_W - GRID_W) / 2
ORIGIN_Y = (PAGE_H - GRID_H) / 2

# Foto-Layout: 15 x 20 cm Abzug, Karten ohne Abstand direkt nebeneinander (Schnitt durch beide Lagen)
PHOTO_W, PHOTO_H = 150 * mm, 200 * mm
PHOTO_COLS, PHOTO_ROWS = 2, 3
PHOTO_PER_SHEET = PHOTO_COLS * PHOTO_ROWS
PHOTO_DPI = 300

# ---------- Style-Schema: Schwarz / Rot ----------
BG = HexColor("#070607")
GLOW = HexColor("#4A070B")
PRIMARY = HexColor("#C4161C")
LINE = HexColor("#5A1014")
TEXT = HexColor("#ECE6E6")
MUTED = HexColor("#8C8184")

# Beispieldaten für --test (erfunden, nur zum Layouttest; keine echten Songs)
TEST_SONGS = [
    ("001", 1965, "Kurzer Titel", "Band A"),
    ("002", 1974, "Ein deutlich längerer Songtitel, der umbrechen muss", "Die Beispielgruppe"),
    ("003", 1983, "Titel mit Umlauten: Äpfel, Öl & Übermut", "Künstler Müller-Lüdenscheidt"),
    ("004", 1991, "Test", "Interpret mit sehr langem Namen und Zusatz feat. Gast"),
    ("005", 1999, "Supercalifragilisticexpialidocious-Medley", "A"),
    ("006", 2003, "Mittellanger Titel", "Duo B"),
    ("007", 2008, "Noch ein Test", "Sänger C"),
    ("008", 2012, "Nacht", "Chor D"),
    ("009", 2017, "Titel 009", "Interpret 009"),
    ("010", 2021, "Titel 010", "Interpret 010"),
    ("011", 1969, "Titel 011", "Interpret 011"),
    ("012", 1988, "Titel 012", "Interpret 012"),
]


# ---------- Schriften (woff2 -> ttf, da reportlab kein woff2 liest) ----------
def register_fonts() -> None:
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    for name, woff2 in [
        ("Bebas", "BebasNeue-Regular.woff2"),
        ("Inter", "Inter-Regular.woff2"),
        ("Inter-Bold", "Inter-Bold.woff2"),
    ]:
        ttf = FONT_CACHE / (Path(woff2).stem + ".ttf")
        if not ttf.exists():
            font = TTFont(FONT_DIR / woff2)
            font.flavor = None
            font.save(ttf)
        pdfmetrics.registerFont(RLTTFont(name, str(ttf)))


# ---------- Helfer ----------
def parse_ids(spec: str) -> list[str]:
    ids: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            ids.extend(f"{n:03d}" for n in range(int(a), int(b) + 1))
        else:
            ids.append(f"{int(part):03d}")
    return ids


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if stringWidth(trial, font, size) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_text(text, font, max_w, start, min_size, max_lines):
    """Größte Schriftgröße (<= start), bei der der Text in max_lines Zeilen passt."""
    size = start
    while size > min_size:
        lines = wrap(text, font, size, max_w)
        if len(lines) <= max_lines and all(stringWidth(l, font, size) <= max_w for l in lines):
            return size, lines
        size -= 0.25
    return min_size, wrap(text, font, min_size, max_w)[:max_lines]


def draw_lines(c, lines, font, size, cx, top_y, color, leading=1.15):
    """Zentrierte Zeilen, erste Zeile mit Oberkante bei top_y. Gibt die untere y-Kante zurück."""
    c.setFont(font, size)
    c.setFillColor(color)
    y = top_y
    for line in lines:
        y -= size
        c.drawCentredString(cx, y, line)
        y -= size * (leading - 1)
    return y


# ---------- Kartenmotive ----------
def draw_qr(c, url, cx, cy, block):
    qr = segno.make(url, error="m", boost_error=False)
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    quiet = 4  # Module Ruhezone
    module = block / (n + 2 * quiet)

    # weißer, abgerundeter Block
    c.setFillColor(white)
    c.roundRect(cx - block / 2, cy - block / 2, block, block, 3 * mm, stroke=0, fill=1)

    # QR-Module als zusammenhängende Läufe pro Zeile (leicht überlappend gegen Nähte)
    c.setFillColor(HexColor("#000000"))
    x0 = cx - block / 2 + quiet * module
    y_top = cy + block / 2 - quiet * module
    eps = 0.02 * mm
    for r, row in enumerate(matrix):
        col = 0
        while col < n:
            if row[col]:
                start = col
                while col < n and row[col]:
                    col += 1
                c.rect(
                    x0 + start * module,
                    y_top - (r + 1) * module - eps,
                    (col - start) * module,
                    module + 2 * eps,
                    stroke=0,
                    fill=1,
                )
            else:
                col += 1


def draw_front(c, tx, ty, song_id, base_url):
    """tx, ty = linke untere Ecke der Beschnitt-Fläche (66 mm)."""
    bx, by = tx, ty  # Box-Ursprung
    cx, cy = bx + BOX / 2, by + BOX / 2

    # Hintergrund: Schwarz mit dunkelrotem Glimmen von unten, begrenzt auf die Karte
    c.saveState()
    clip = c.beginPath()
    clip.rect(bx, by, BOX, BOX)
    c.clipPath(clip, stroke=0, fill=0)
    c.setFillColor(BG)
    c.rect(bx, by, BOX, BOX, stroke=0, fill=1)
    c.radialGradient(cx, by - 6 * mm, 62 * mm, (GLOW, BG), extend=True)
    c.restoreState()

    draw_qr(c, f"{base_url}#{song_id}", cx, cy, 38 * mm)


def draw_back(c, tx, ty, song):
    sid, year, title, artist = song
    bx, by = tx, ty
    cx = bx + BOX / 2
    color = PRIMARY
    inner_w = TRIM - 10 * mm

    c.setFillColor(BG)
    c.rect(bx, by, BOX, BOX, stroke=0, fill=1)

    # dünner, dunkelroter Rahmen
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3 * mm)
    inset = BLEED + 3 * mm
    c.rect(bx + inset, by + inset, TRIM - 6 * mm, TRIM - 6 * mm, stroke=1, fill=0)

    # Jahr riesig
    year_s = str(year)
    size = 84.0
    while stringWidth(year_s, "Bebas", size) > inner_w:
        size -= 1
    top = by + BLEED + TRIM - 8 * mm
    c.setFont("Bebas", size)
    c.setFillColor(color)
    year_base = top - size * 0.72  # Versalhöhe von Bebas ~0.7 em
    c.drawCentredString(cx, year_base, year_s)

    # Titel + Interpret: Schrift schrumpft, bis alles zwischen Jahr und ID-Zeile passt
    y = year_base - 4.5 * mm
    avail = y - (by + BLEED + 9 * mm)
    t_start = 13.0
    while True:
        t_size, t_lines = fit_text(title, "Inter-Bold", inner_w, t_start, 6, 3)
        a_size, a_lines = fit_text(artist, "Inter", inner_w, t_start * 0.8, 5.5, 2)
        height = (len(t_lines) * t_size + len(a_lines) * a_size) * 1.15 + 1.5 * mm
        if height <= avail or t_start <= 6:
            break
        t_start -= 0.5
    y = draw_lines(c, t_lines, "Inter-Bold", t_size, cx, y, TEXT)
    y -= 1.5 * mm
    draw_lines(c, a_lines, "Inter", a_size, cx, y, MUTED)

    # ID unten, klein
    c.setFont("Inter", 6.5)
    c.setFillColor(MUTED)
    c.drawCentredString(cx, by + BLEED + 5.5 * mm, f"#{sid}")


def draw_crop_marks(c, bx, by):
    """Schnittmarken an den vier Trimm-Ecken, innerhalb des Beschnitts (wird mit abgeschnitten)."""
    c.setStrokeColor(white)
    c.setLineWidth(0.25)
    gap, length = 1.0 * mm, 1.6 * mm
    for ex, sx in [(bx + BLEED, -1), (bx + BLEED + TRIM, 1)]:
        for ey, sy in [(by + BLEED, -1), (by + BLEED + TRIM, 1)]:
            c.line(ex + sx * gap, ey, ex + sx * (gap + length), ey)
            c.line(ex, ey + sy * gap, ex, ey + sy * (gap + length))


def slot_origin(row, col):
    """Linke untere Ecke des Kartenfelds; Reihe 0 liegt oben."""
    return ORIGIN_X + col * BOX, ORIGIN_Y + (ROWS - 1 - row) * BOX


# ---------- Foto-Modus (15 x 20 cm Abzüge) ----------
def photo_cell(row, col):
    """Linke untere Ecke der Schnittfläche (60 mm) im Foto-Layout; Reihe 0 liegt oben."""
    ox = (PHOTO_W - PHOTO_COLS * TRIM) / 2
    oy = (PHOTO_H - PHOTO_ROWS * TRIM) / 2
    return ox + col * TRIM, oy + (PHOTO_ROWS - 1 - row) * TRIM


def draw_photo_card(c, row, col, draw):
    """Zeichnet eine Karte auf ihre Schnittfläche; Beschnitt nur an den Außenkanten des Gitters."""
    x, y = photo_cell(row, col)
    left = BLEED if col == 0 else 0
    right = BLEED if col == PHOTO_COLS - 1 else 0
    top = BLEED if row == 0 else 0
    bottom = BLEED if row == PHOTO_ROWS - 1 else 0
    c.saveState()
    clip = c.beginPath()
    clip.rect(x - left, y - bottom, TRIM + left + right, TRIM + bottom + top)
    c.clipPath(clip, stroke=0, fill=0)
    draw(c, x - BLEED, y - BLEED)
    c.restoreState()


def draw_photo_marks(c, label):
    """Schnittlinien-Marken im weißen Rand, außerhalb des Beschnitts, plus Seitenbeschriftung."""
    gx, gy = photo_cell(PHOTO_ROWS - 1, 0)
    gw, gh = PHOTO_COLS * TRIM, PHOTO_ROWS * TRIM
    near, far = BLEED + 1 * mm, BLEED + 4 * mm
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(0.25)
    for i in range(PHOTO_COLS + 1):
        x = gx + i * TRIM
        c.line(x, gy + gh + near, x, gy + gh + far)
        c.line(x, gy - near, x, gy - far)
    for j in range(PHOTO_ROWS + 1):
        y = gy + j * TRIM
        c.line(gx - near, y, gx - far, y)
        c.line(gx + gw + near, y, gx + gw + far, y)
    c.setFont("Inter", 6)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(gx + TRIM / 2, gy + gh + BLEED + 2.5 * mm, label)


def render_photos(cards, base_url, app_name, out_dir):
    """Schreibt ein PDF und je Seite ein JPG (300 dpi) für 15 x 20 cm Fotoabzüge."""
    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    pdf_path = out_dir / "fotoabzuege.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(PHOTO_W, PHOTO_H))
    c.setTitle(f"{app_name} Fotoabzüge 15x20")
    c.setAuthor(app_name)

    sheets = [cards[i : i + PHOTO_PER_SHEET] for i in range(0, len(cards), PHOTO_PER_SHEET)]
    total = len(sheets)
    for n, chunk in enumerate(sheets, 1):
        for i, (sid, *_rest) in enumerate(chunk):
            draw_photo_card(c, i // PHOTO_COLS, i % PHOTO_COLS, lambda cv, bx, by, sid=sid: draw_front(cv, bx, by, sid, base_url))
        draw_photo_marks(c, f"VORDERSEITE {n:02d}/{total:02d}")
        c.showPage()

        for i, song in enumerate(chunk):
            draw_photo_card(c, i // PHOTO_COLS, PHOTO_COLS - 1 - i % PHOTO_COLS, lambda cv, bx, by, song=song: draw_back(cv, bx, by, song))
        draw_photo_marks(c, f"RÜCKSEITE {n:02d}/{total:02d}")
        c.showPage()
    c.save()

    doc = pymupdf.open(pdf_path)
    for page_no, page in enumerate(doc):
        n, side = page_no // 2 + 1, "vorne" if page_no % 2 == 0 else "hinten"
        pix = page.get_pixmap(dpi=PHOTO_DPI, colorspace=pymupdf.csRGB, alpha=False)
        pix.set_dpi(PHOTO_DPI, PHOTO_DPI)
        pix.save(str(out_dir / f"{n:02d}_{side}.jpg"), jpg_quality=95)
    size = f"{pix.width} x {pix.height} px"
    doc.close()
    return total, size


# ---------- Hauptprogramm ----------
def load_cards(args, base_url):
    if args.test:
        return [(sid, y, t, a) for sid, y, t, a in TEST_SONGS], []

    songs = json.loads((ROOT / "songs.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in songs}
    wanted = parse_ids(args.ids) if args.ids else [s["id"] for s in songs]

    cards, skipped = [], []
    for sid in wanted:
        s = by_id.get(sid)
        if s is None:
            skipped.append((sid, "nicht in songs.json"))
        elif not s.get("yt") or s["yt"] == "TODO":
            skipped.append((sid, "yt ist TODO"))
        else:
            cards.append((s["id"], int(s["year"]), s["title"], s["artist"]))
    return cards, skipped


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Kartengenerator für ZeitHit")
    ap.add_argument("--ids", help="z. B. 1-24 oder 1-12,30")
    ap.add_argument("--test", action="store_true", help="eine Testseite mit Beispieldaten")
    ap.add_argument("--photo", action="store_true", help="JPGs für 15 x 20 cm Fotoabzüge statt A4-PDF")
    args = ap.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    base_url, app_name = config["baseUrl"], config["appName"]

    cards, skipped = load_cards(args, base_url)
    for sid, reason in skipped:
        print(f"übersprungen: {sid} ({reason})")
    if not cards:
        print("Keine Karten zu erzeugen. Songs mit echter YouTube-ID eintragen (tools/add_song.py).")
        return 1

    register_fonts()
    CARDS_DIR.mkdir(exist_ok=True)

    if args.photo:
        out_dir = CARDS_DIR / ("photo_test" if args.test else "photo")
        sheets, size = render_photos(cards, base_url, app_name, out_dir)
        print(f"{len(cards)} Karten auf {sheets} Abzügen (je Vorder- und Rückseite, {size}) -> {out_dir.relative_to(ROOT)}")
        return 0

    out = CARDS_DIR / ("test.pdf" if args.test else "cards.pdf")

    c = canvas.Canvas(str(out), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"{app_name} Karten")
    c.setAuthor(app_name)

    for page_start in range(0, len(cards), PER_PAGE):
        chunk = cards[page_start : page_start + PER_PAGE]

        # Vorderseiten
        for i, (sid, *_rest) in enumerate(chunk):
            bx, by = slot_origin(i // COLS, i % COLS)
            draw_front(c, bx, by, sid, base_url)
            draw_crop_marks(c, bx, by)
        c.showPage()

        # Rückseiten: Spalten pro Reihe gespiegelt (Wenden an der langen Kante)
        for i, song in enumerate(chunk):
            bx, by = slot_origin(i // COLS, COLS - 1 - i % COLS)
            draw_back(c, bx, by, song)
            draw_crop_marks(c, bx, by)
        c.showPage()

    c.save()
    pages = (len(cards) + PER_PAGE - 1) // PER_PAGE
    print(f"{len(cards)} Karten, {pages * 2} Seiten -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
