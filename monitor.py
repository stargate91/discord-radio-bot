import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from scanner import process_song

class MusicLibraryHandler(FileSystemEventHandler):
    def __init__(self, config, db, loop, genre_mapping):
        self.config = config
        self.db = db
        self.loop = loop
        self.genre_mapping = genre_mapping

    def on_created(self, event):
        if event.is_directory:
            return
        
        self.loop.call_later(2, lambda: self.loop.create_task(self.handle_change(event.src_path)))

    def on_moved(self, event):
        if event.is_directory:
            return
        self.loop.create_task(self.handle_delete(event.src_path))
        self.loop.call_later(1, lambda: self.loop.create_task(self.handle_change(event.dest_path)))

    def on_modified(self, event):
        if event.is_directory:
            return
        
        self.loop.call_later(2, lambda: self.loop.create_task(self.handle_change(event.src_path)))

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.loop.create_task(self.handle_delete(event.src_path))

    async def handle_change(self, file_path):
        p = Path(file_path)
        if not p.exists():
            return

        genre = self.get_genre_for_path(file_path)
        if not genre:
            return
        
        try:
            async with self.db.connect() as conn:
                if await process_song(p, genre, self.config, self.db, conn):
                    print(f"[MONITOR] Added/Updated: {file_path}")
                    await conn.commit()
        except Exception as e:
            print(f"[MONITOR] Error processing {file_path}: {e}")

    async def handle_delete(self, file_path):
        try:
            if await self.db.remove_song_by_path(str(file_path)):
                print(f"[MONITOR] Removed from DB: {file_path}")
        except Exception as e:
            print(f"[MONITOR] Error removing {file_path}: {e}")

    def get_genre_for_path(self, file_path):
        try:
            target = Path(file_path).resolve()
            for folder_str, genre in self.genre_mapping.items():
                folder_path = Path(folder_str).resolve()
                if str(target).startswith(str(folder_path)):
                    return genre
        except Exception as e:
            print(f"[MONITOR] Genre resolve failed for {file_path}: {e}")
        return None

def start_monitoring(config, db, loop):
    genre_mapping = {}
    for genre, paths in config.genres.items():
        for path in paths:
            genre_mapping[str(Path(path).resolve())] = genre

    handler = MusicLibraryHandler(config, db, loop, genre_mapping)
    observer = Observer()
    
    watched_folders = 0
    for folder in genre_mapping.keys():
        if Path(folder).exists():
            observer.schedule(handler, folder, recursive=True)
            watched_folders += 1
    
    if watched_folders > 0:
        observer.start()
        print(f"[MONITOR] Started monitoring {watched_folders} library folders.")
        return observer
    return None
