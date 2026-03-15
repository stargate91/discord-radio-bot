import os
from pathlib import Path
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC
from mutagen.flac import FLAC
import hashlib

def get_cover_art(file_path: Path, config=None) -> bytes | None:
    if not file_path.is_file():
        return None
    folder = file_path.parent
    cover_names = config.cover_filenames if config else ["cover.jpg", "cover.png", "cover.jpeg", "folder.jpg", "folder.png", "front.jpg", "front.png"]
    for name in cover_names:
        cover_path = folder / name
        if cover_path.exists():
            return cover_path.read_bytes()
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return None
        if isinstance(audio, FLAC):
            if audio.pictures:
                return audio.pictures[0].data
        elif isinstance(audio, ID3):
            for tag in audio.values():
                if isinstance(tag, APIC):
                    return tag.data
        elif hasattr(audio, "tags") and audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, "data") and (isinstance(tag, APIC) or "PIC" in str(type(tag))):
                    return tag.data
    except Exception as e:
        print(f"Error extracting cover art: {e}")
    return None
async def find_and_save_cover(file_path: Path, config=None) -> str | None:
    folder = file_path.parent
    cover_names = config.cover_filenames if config else ["cover.jpg", "cover.png", "cover.jpeg", "folder.jpg", "folder.png", "front.jpg", "front.png"]
    for name in cover_names:
        cover_path = folder / name
        if cover_path.exists():
            return str(cover_path)
    art_bytes = get_cover_art(file_path, config=config)
    if not art_bytes:
        return None
    cache_dir = Path("data/covers")
    cache_dir.mkdir(parents=True, exist_ok=True)
    file_hash = hashlib.md5(str(file_path).encode()).hexdigest()
    ext = "png"
    if art_bytes.startswith(b'\xff\xd8'): ext = "jpg"
    elif art_bytes.startswith(b'\x89PNG'): ext = "png"
    cache_path = cache_dir / f"{file_hash}.{ext}"
    if not cache_path.exists():
        cache_path.write_bytes(art_bytes)
    return str(cache_path)

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

def extract_tags(file_path: Path, config=None):
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
                if hasattr(value, "rating"):
                    return popm_to_stars(value.rating)
                if hasattr(value, "text"):
                    return join.join([str(v) for v in value.text])
                if isinstance(value, list):
                    return join.join([str(v) for v in value])
                return str(value)
        return None

    def find_tag(field_name):
        if not config:
            # Fallback for old behavior
            mapping = {
                "artist": ["artist", "ARTIST", "TPE1"],
                "title": ["title", "TITLE", "TIT2"],
                "album": ["album", "ALBUM", "TALB"],
                "date": ["date", "DATE", "year", "YEAR", "TDRC"],
                "label": ["organization", "ORGANIZATION", "TPUB"],
                "catnum": ["catalognumber", "CATALOGNUMBER", "TXXX:CATALOGNUMBER"],
                "mediatype": ["mediatype", "MEDIATYPE", "TMED"],
                "rating": ["rating", "RATING", "POPM"]
            }
            keys = mapping.get(field_name, [])
        else:
            keys = config.metadata_fields.get(field_name, [])
        return get_tag(tags, *keys)

    artist = find_tag("artist")
    title = find_tag("title")
    album = find_tag("album")
    date = find_tag("date")
    label = find_tag("label")
    catnum = find_tag("catnum")
    mediatype = find_tag("mediatype")
    rating = find_tag("rating")
    duration = int(audio.info.length) if audio.info else 0
    return {
        "artist": artist,
        "title": title,
        "album": album,
        "date": date,
        "label": label,
        "catnum": catnum,
        "duration": duration,
        "mediatype": mediatype,
        "rating": safe_int(rating),
        "mtime": int(file_path.stat().st_mtime) if file_path.exists() else 0
    }
async def process_song(full_path: Path, genre: str, config, db, conn, force=False):
    file_mtime = int(full_path.stat().st_mtime)
    if not force:
        existing = await db.get_song_by_path(str(full_path))
        if existing and existing.get('mtime', 0) >= file_mtime:
            return False
    tags = extract_tags(full_path, config=config)
    if not tags:
        return False
    inserted_flag = await db.insert_song_batch(conn, {
        "path": str(full_path),
        "artist": tags["artist"],
        "title": tags["title"],
        "album": tags["album"],
        "date": tags["date"],
        "genre": genre,
        "label": tags["label"],
        "catnum": tags["catnum"],
        "duration": tags["duration"],
        "mediatype": tags["mediatype"],
        "rating": tags["rating"],
        "mtime": tags["mtime"]
    })
    if inserted_flag:
        cover_art_path = await find_and_save_cover(full_path, config=config)
        if cover_art_path:
            await db.save_song_cover_path(str(full_path), cover_art_path, db=conn)
    return inserted_flag
async def scan_music_library(config, db, force=False):
    inserted = 0
    skipped = 0
    batch_size = 500
    count = 0
    print(f"[SCAN] Starting music library scan (Batch size: {batch_size})...")
    async with db.connect() as conn:
        for genre, paths in config.genres.items():
            print(f"[SCAN] Current Genre: {genre.upper()}")
            for base_path in paths:
                base_path = Path(base_path)
                if not base_path.exists():
                    print(f" [SCAN] Missing path: {base_path}")
                    continue
                print(f" [SCAN] Path: {base_path}")
                for root, _, files in os.walk(base_path):
                    if files:
                        print(f"  [SCAN] Processing directory: {root}")
                    for file in files:
                        ext = Path(file).suffix.lower().replace(".", "")
                        if ext not in config.supported_extensions:
                            continue
                        full_path = Path(root) / file
                        if await process_song(full_path, genre, config, db, conn, force=force):
                            inserted += 1
                        else:
                            skipped += 1
                        count += 1
                        if count % 100 == 0:
                            await conn.commit()
                            print(f"   [SCAN] Progress: {count} files scanned... (Added: {inserted}, Skipped: {skipped})")
        await conn.commit()
    print(f"[SCAN] Scan finished. Total: {count}, Added: {inserted}, Skipped: {skipped}")
    return inserted, skipped
async def scan_specific_path(target_path_str: str, config, db, force=True):
    target_path = Path(target_path_str).resolve()
    if not target_path.exists():
        return 0, 0, "Directory does not exist."
    
    assigned_genre = None
    for g, paths in config.genres.items():
        for p in paths:
            genre_root = Path(p).resolve()
            try:
                if target_path == genre_root or target_path.is_relative_to(genre_root):
                    assigned_genre = g
                    break
            except (ValueError, TypeError):
                if str(target_path).lower().startswith(str(genre_root).lower()):
                    assigned_genre = g
                    break
        if assigned_genre:
            break
            
    if not assigned_genre:
        return 0, 0, "unauthorized_path"
    
    inserted = 0
    skipped = 0
    count = 0
    async with db.connect() as conn:
        for root, _, files in os.walk(target_path):
            for file in files:
                ext = Path(file).suffix.lower().replace(".", "")
                if ext not in config.supported_extensions:
                    continue
                full_path = Path(root) / file
                if await process_song(full_path, assigned_genre, config, db, conn, force=force):
                    inserted += 1
                else:
                    skipped += 1
                count += 1
                if count % 50 == 0:
                    await conn.commit()
        await conn.commit()
    return inserted, skipped, None

async def cleanup_database(db):
    paths = await db.get_all_song_paths()
    removed = 0
    for path in paths:
        if not Path(path).exists():
            await db.remove_song_by_path(path)
            removed += 1
    return removed
