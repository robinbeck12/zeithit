"""Schlägt Songs aus deinem YouTube-Music-Konto vor und trägt die gewählten in songs.json ein.

Einmalige Einrichtung (die Datei bleibt lokal und steht in der .gitignore):
    ytmusicapi browser
Das fragt nach den Request-Headern einer eingeloggten Anfrage von music.youtube.com
(Anleitung: https://ytmusicapi.readthedocs.io/en/stable/setup/browser.html) und legt
browser.json an. Verschiebe sie nach tools/ytmusic_auth.json.

Aufruf:
    python tools/import_history.py [--source likes|library|history] [--limit 100]

Das Jahr ist das Erscheinungsjahr des Albums bei YouTube Music und kann bei Compilations und
Neuauflagen vom Originaljahr abweichen. Jedes Jahr wird deshalb einzeln bestätigt.
"""

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from add_song import next_slot
from _common import SONGS_FILE, load_songs, oembed, save_songs

AUTH_FILE = Path(__file__).resolve().parent / "ytmusic_auth.json"
SOURCES = {"likes": "Titel mit Daumen hoch", "library": "Bibliothek", "history": "Verlauf"}
TYPES = {
    "MUSIC_VIDEO_TYPE_ATV": "Audio",
    "MUSIC_VIDEO_TYPE_OMV": "Musikvideo",
    "MUSIC_VIDEO_TYPE_UGC": "User-Upload",
    "MUSIC_VIDEO_TYPE_OFFICIAL_SOURCE_MUSIC": "Offiziell",
}


def fetch(yt, source: str, limit: int) -> list[dict]:
    if source == "likes":
        return yt.get_liked_songs(limit)["tracks"]
    if source == "library":
        return yt.get_library_songs(limit)
    return yt.get_history()[:limit]


def candidates(tracks: list[dict], known: set[str]) -> list[dict]:
    """Doppelte und bereits eingetragene Titel entfernen, Felder vereinheitlichen."""
    seen, out = set(known), []
    for t in tracks:
        vid = t.get("videoId")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        album = t.get("album") or {}
        out.append(
            {
                "yt": vid,
                "title": t.get("title", "").strip(),
                "artist": ", ".join(a["name"] for a in t.get("artists") or [] if a.get("name")),
                "album_id": album.get("id"),
                "type": TYPES.get(t.get("videoType"), "?"),
                "year": None,
                "embed": None,
            }
        )
    return out


def enrich(yt, items: list[dict]) -> None:
    """Albumjahr und Einbettbarkeit parallel nachladen."""
    album_ids = {i["album_id"] for i in items if i["album_id"]}

    def album_year(album_id):
        try:
            m = re.search(r"\d{4}", str(yt.get_album(album_id).get("year", "")))
            return album_id, int(m.group()) if m else None
        except Exception:
            return album_id, None

    with ThreadPoolExecutor(8) as pool:
        years = dict(pool.map(album_year, album_ids))
        embeds = list(pool.map(lambda i: oembed(i["yt"])[0], items))
    for item, status in zip(items, embeds):
        item["year"] = years.get(item["album_id"])
        item["embed"] = status


def parse_selection(text: str, count: int) -> list[int]:
    if text.strip().lower() in ("alle", "all"):
        return list(range(count))
    picked = []
    for part in re.split(r"[\s,]+", text.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"Nicht verstanden: {part!r}")
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if not 1 <= lo <= hi <= count:
            raise ValueError(f"Außerhalb der Liste: {part}")
        picked += range(lo - 1, hi)
    return list(dict.fromkeys(picked))


def main() -> int:
    ap = argparse.ArgumentParser(description="Songs aus YouTube Music übernehmen")
    ap.add_argument("--source", choices=SOURCES, default="likes", help="likes (Standard), library oder history")
    ap.add_argument("--limit", type=int, default=100, help="Wie viele Titel abgerufen werden")
    ap.add_argument("--auth", type=Path, default=AUTH_FILE, help="Pfad zur Auth-Datei")
    ap.add_argument("--songs", type=Path, default=SONGS_FILE, help="Pfad zur songs.json")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        from ytmusicapi import YTMusic
    except ImportError:
        return fail("ytmusicapi fehlt: pip install ytmusicapi")
    if not args.auth.exists():
        return fail(f"{args.auth.name} fehlt. Einrichtung siehe Kopf dieser Datei (ytmusicapi browser).")

    yt = YTMusic(str(args.auth))
    songs = load_songs(args.songs)
    known = {s["yt"] for s in songs}

    print(f"Lade {SOURCES[args.source]} (bis zu {args.limit}) …")
    items = candidates(fetch(yt, args.source, args.limit), known)
    if not items:
        print("Keine neuen Titel gefunden.")
        return 0
    print(f"{len(items)} neue Titel, prüfe Jahr und Einbettbarkeit …")
    enrich(yt, items)

    for n, i in enumerate(items, 1):
        year = i["year"] or "????"
        embed = "" if i["embed"] == 200 else "  [NICHT EINBETTBAR]"
        print(f"{n:3}  {year}  {i['artist']} – {i['title']}  ({i['type']}){embed}")

    if not sys.stdin.isatty():
        return 0
    try:
        picked = parse_selection(input("\nWelche übernehmen? (z. B. 1 4 7-12 oder alle, Enter = keine): "), len(items))
    except EOFError:
        return 0
    except ValueError as e:
        return fail(str(e))

    added = 0
    for idx in picked:
        i = items[idx]
        if i["embed"] != 200:
            print(f"Übersprungen (nicht einbettbar): {i['artist']} – {i['title']}")
            continue
        raw = input(f"Jahr für {i['artist']} – {i['title']} [{i['year'] or ''}] (- = überspringen): ").strip()
        if raw == "-":
            continue
        try:
            year = int(raw or i["year"] or 0)
        except ValueError:
            year = 0
        if not 1900 <= year <= date.today().year + 1:
            print("  Unplausibles Jahr, übersprungen.")
            continue
        new_id, replace_at = next_slot(songs)
        song = {"id": new_id, "yt": i["yt"], "start": 0, "title": i["title"], "artist": i["artist"], "year": year}
        if replace_at is not None:
            songs[replace_at] = song
        else:
            songs.append(song)
        added += 1
    if added:
        save_songs(songs, args.songs)
    print(f"{added} Song(s) eingetragen.")
    return 0


def fail(message: str) -> int:
    print(f"Fehler: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
