import os
from pathlib import Path
from mutagen import File as MutagenFile

def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

def popm_to_stars(popm):
    if popm is None:
        return 0

    popm = int(popm)

    if popm == 0:
        return 0
    elif popm <= 31:
        return 1
    elif popm <= 95:
        return 2
    elif popm <= 159:
        return 3
    elif popm <= 223:
        return 4
    else:
        return 5

def extract_tags(file_path: Path):
    try:
        audio = MutagenFile(file_path)
    except Exception as e:
        print(f"Tag read error: {file_path} -> {e}")
        return None     
    if audio is None:
        return None

    tags = audio.tags or {}

    def get_tag(tags, *keys, join=", "):
        for key in keys:
            if key in tags:
                value = tags[key]

                # MP3 POPM rating
                if hasattr(value, "rating"):
                    return popm_to_stars(value.rating)

                # MP3 text frames
                if hasattr(value, "text"):
                    return join.join([str(v) for v in value.text])

                # FLAC
                if isinstance(value, list):
                    return join.join([str(v) for v in value])

                return str(value)

        return None

    artist = get_tag(tags, "artist", "ARTIST", "TPE1")
    title = get_tag(tags, "title", "TITLE", "TIT2")
    album = get_tag(tags, "album", "ALBUM", "TALB")
    date = get_tag(tags, "date", "DATE", "year", "YEAR", "TDRC")
    mediatype_flac = get_tag(tags, "mediatype", "MEDIATYPE")
    mediatype_mp3 = get_tag(tags, "TMED")
    rating = get_tag(tags, "rating", "RATING", "POPM")

    duration = int(audio.info.length) if audio.info else 0

    return {
        "artist": artist,
        "title": title,
        "album": album,
        "date": date,
        "duration": duration,
        "mediatype_flac": mediatype_flac,
        "mediatype_mp3": mediatype_mp3,
        "rating": safe_int(rating)
    }


def scan_music_library(config, db):
    inserted = 0
    skipped = 0

    if not db.is_empty():
        return 0, 0

    with db._connect() as conn:
        cursor = conn.cursor()

        for genre, paths in config.genres.items():
            print(f"\n🎵 Genre: {genre}")

            for base_path in paths:
                base_path = Path(base_path)

                if not base_path.exists():
                    print(f"  ❌ Missing path: {base_path}")
                    continue

                for root, _, files in os.walk(base_path):
                    for file in files:

                        print(f"\n File: {file}")

                        ext = Path(file).suffix.lower().replace(".", "")
                        if ext not in config.supported_extensions:
                            continue

                        full_path = Path(root) / file
                        tags = extract_tags(full_path)

                        if not tags:
                            skipped += 1
                            continue

                        inserted_flag = db.insert_song_batch(cursor, {
                            "path": str(full_path),
                            "artist": tags["artist"],
                            "title": tags["title"],
                            "album": tags["album"],
                            "date": tags["date"],
                            "genre": genre,
                            "duration": tags["duration"],
                            "mediatype_flac": tags["mediatype_flac"],
                            "mediatype_mp3": tags["mediatype_mp3"],
                            "rating": tags["rating"],
                        })

                        if inserted_flag:
                            inserted += 1

        conn.commit()

    return inserted, skipped