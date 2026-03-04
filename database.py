import aiosqlite
import sqlite3
import time
import asyncio
from pathlib import Path

DB_DIR = Path("data")
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DB_DIR / "radio.db"

class DatabaseManager:
    def __init__(self):
        self.db_file = DB_FILE

    async def initialize(self):
        """Async initialization of the database."""
        async with self._connect() as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            await db.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                artist TEXT,
                title TEXT,
                album TEXT,
                date TEXT,
                label TEXT,
                catnum TEXT,
                genre TEXT,
                duration INTEGER,
                mediatype_flac TEXT,
                mediatype_mp3 TEXT,
                rating INTEGER DEFAULT 0,
                play_count INTEGER DEFAULT 0,
                last_played INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                dislikes INTEGER DEFAULT 0,
                mtime INTEGER DEFAULT 0
            )
            """)
            
            
            cursor = await db.execute("PRAGMA table_info(songs)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            if "mtime" not in column_names:
                await db.execute("ALTER TABLE songs ADD COLUMN mtime INTEGER DEFAULT 0")
                print("[DB] Added 'mtime' column to 'songs' table.")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS user_ratings (
                user_id INTEGER,
                song_path TEXT,
                rating_type TEXT CHECK(rating_type IN ('like', 'dislike')),
                PRIMARY KEY (user_id, song_path)
            )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_genre ON songs(genre)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_artist ON songs(artist)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_album ON songs(album)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_title ON songs(title)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_date ON songs(date)")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS song_covers (
                song_path TEXT PRIMARY KEY,
                cover_path TEXT,
                FOREIGN KEY(song_path) REFERENCES songs(path) ON DELETE CASCADE
            )
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER,
                created_at INTEGER NOT NULL
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER,
                song_path TEXT,
                position INTEGER,
                PRIMARY KEY (playlist_id, song_path),
                FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY(song_path) REFERENCES songs(path) ON DELETE CASCADE
            )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS playback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_path TEXT NOT NULL,
                user_id INTEGER,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY(song_path) REFERENCES songs(path) ON DELETE CASCADE
            )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON playback_history(timestamp)")
        
            await db.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)
            await db.commit()

    async def is_empty(self) -> bool:
        async with self._connect() as db:
            async with db.execute("SELECT COUNT(*) FROM songs") as cursor:
                row = await cursor.fetchone()
                return row[0] == 0

    async def insert_song_batch(self, db, data: dict):
        """Note: This takes an active connection for batch efficiency.
        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) if path exists.
        """
        await db.execute("""
        INSERT INTO songs (
            path, artist, title, album, date, label, catnum, genre,
            duration, mediatype_flac, mediatype_mp3, rating, mtime
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            artist=excluded.artist,
            title=excluded.title,
            album=excluded.album,
            date=excluded.date,
            label=excluded.label,
            catnum=excluded.catnum,
            genre=excluded.genre,
            duration=excluded.duration,
            mediatype_flac=excluded.mediatype_flac,
            mediatype_mp3=excluded.mediatype_mp3,
            rating=excluded.rating,
            mtime=excluded.mtime
        """, (
            data["path"], data["artist"], data["title"], data["album"],
            data["date"], data["label"], data["catnum"], data["genre"],
            data["duration"], data["mediatype_flac"], data["mediatype_mp3"],
            data["rating"], data.get("mtime", 0)
        ))
        return db.total_changes > 0

    async def get_random_song_by_genre(self, genre: str):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM songs WHERE genre = ? ORDER BY RANDOM() LIMIT 1
            """, (genre,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    def _connect(self):
        return aiosqlite.connect(self.db_file)

    async def update_last_played(self, song_path: str):
        async with self._connect() as db:
            await db.execute("""
                UPDATE songs
                SET last_played = ?, play_count = play_count + 1
                WHERE path = ?
            """, (int(time.time()), song_path))
            await db.commit()

    async def add_to_history(self, song_path: str, user_id: int | None = None):
        async with self._connect() as db:
            await db.execute("""
                INSERT INTO playback_history (song_path, user_id, timestamp)
                VALUES (?, ?, ?)
            """, (song_path, user_id, int(time.time())))
            await db.commit()

    async def get_metadata(self, key: str, default=None):
        async with self._connect() as db:
            async with db.execute("SELECT value FROM metadata WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

    async def set_metadata(self, key: str, value: str):
        async with self._connect() as db:
            await db.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, str(value)))
            await db.commit()

    async def get_random_song_by_rating(self, min_rating: int = 5):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM songs WHERE rating >= ? ORDER BY RANDOM() LIMIT 1
            """, (min_rating,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_genres(self) -> list[str]:
        async with self._connect() as db:
            async with db.execute("""
                SELECT DISTINCT genre FROM songs
                WHERE genre IS NOT NULL AND genre != ''
                ORDER BY genre COLLATE NOCASE ASC
            """) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_all_song_paths(self):
        async with self._connect() as db:
            async with db.execute("SELECT path FROM songs") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_song_by_path(self, path: str):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM songs WHERE path = ?", (path,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def remove_song_by_path(self, path: str):
        async with self._connect() as db:
            await db.execute("DELETE FROM songs WHERE path = ?", (path,))
            await db.commit()
            return True

    async def get_song_by_id(self, song_id: int):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM songs WHERE id = ?", (song_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def toggle_rating(self, user_id: int, song_path: str, rating_type: str):
        async with self._connect() as db:
            async with db.execute(
                "SELECT rating_type FROM user_ratings WHERE user_id = ? AND song_path = ?",
                (user_id, song_path)
            ) as cursor:
                existing = await cursor.fetchone()

            status = ""
            if existing:
                existing_type = existing[0]
                if existing_type == rating_type:
                    await db.execute(
                        "DELETE FROM user_ratings WHERE user_id = ? AND song_path = ?",
                        (user_id, song_path)
                    )
                    column = "likes" if rating_type == "like" else "dislikes"
                    await db.execute(f"UPDATE songs SET {column} = {column} - 1 WHERE path = ?", (song_path,))
                    status = "removed"
                else:
                    await db.execute(
                        "UPDATE user_ratings SET rating_type = ? WHERE user_id = ? AND song_path = ?",
                        (rating_type, user_id, song_path)
                    )
                    old_col = "likes" if existing_type == "like" else "dislikes"
                    new_col = "likes" if rating_type == "like" else "dislikes"
                    await db.execute(f"UPDATE songs SET {old_col} = {old_col} - 1, {new_col} = {new_col} + 1 WHERE path = ?", (song_path,))
                    status = "changed"
            else:
                await db.execute(
                    "INSERT INTO user_ratings (user_id, song_path, rating_type) VALUES (?, ?, ?)",
                    (user_id, song_path, rating_type)
                )
                column = "likes" if rating_type == "like" else "dislikes"
                await db.execute(f"UPDATE songs SET {column} = {column} + 1 WHERE path = ?", (song_path,))
                status = "added"

            await db.commit()
            return status

    async def get_song_cover_path(self, song_path: str) -> str | None:
        async with self._connect() as db:
            async with db.execute("SELECT cover_path FROM song_covers WHERE song_path = ?", (song_path,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def save_song_cover_path(self, song_path: str, cover_path: str, db=None):
        if db:
            await db.execute("""
                INSERT OR REPLACE INTO song_covers (song_path, cover_path)
                VALUES (?, ?)
            """, (song_path, cover_path))
            return

        async with self._connect() as db:
            await db.execute("""
                INSERT OR REPLACE INTO song_covers (song_path, cover_path)
                VALUES (?, ?)
            """, (song_path, cover_path))
            await db.commit()

    async def search_songs(self, query: str) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            words = query.split()
            if not words: return []

            where_clauses = []
            params = []
            for word in words:
                pattern = f"%{word}%"
                where_clauses.append("(artist LIKE ? OR title LIKE ? OR album LIKE ? OR date LIKE ?)")
                params.extend([pattern, pattern, pattern, pattern])

            where_sql = " AND ".join(where_clauses)
            full_pattern = f"%{query}%"
            start_pattern = f"{query}%"

            priority_sql = """
                CASE
                    WHEN artist = ? OR title = ? THEN 1
                    WHEN artist LIKE ? OR title LIKE ? THEN 2
                    ELSE 3
                END as priority
            """

            sql = f"""
                SELECT *, {priority_sql}
                FROM songs
                WHERE {where_sql}
                ORDER BY priority ASC, artist ASC, title ASC
            """
            all_params = [query, query, start_pattern, start_pattern] + params
            async with db.execute(sql, tuple(all_params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def search_by_artist(self, artist: str) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM songs WHERE artist = ? ORDER BY title ASC
            """, (artist,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def search_artists(self, query: str) -> list[str]:
        async with self._connect() as db:
            search_pattern = f"%{query}%"
            start_pattern = f"{query}%"
            sql = """
                SELECT DISTINCT artist,
                    CASE
                        WHEN artist = ? THEN 1
                        WHEN artist LIKE ? THEN 2
                        ELSE 3
                    END as priority
                FROM songs
                WHERE artist LIKE ?
                ORDER BY priority ASC, artist ASC
            """
            async with db.execute(sql, (query, start_pattern, search_pattern)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def search_albums(self, query: str) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            search_pattern = f"%{query}%"
            start_pattern = f"{query}%"
            sql = """
                SELECT DISTINCT artist, album,
                    CASE
                        WHEN album = ? THEN 1
                        WHEN album LIKE ? THEN 2
                        ELSE 3
                    END as priority
                FROM songs
                WHERE album LIKE ?
                ORDER BY priority ASC, album ASC
            """
            async with db.execute(sql, (query, start_pattern, search_pattern)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def search_by_album(self, artist: str, album: str) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM songs WHERE artist = ? AND album = ? ORDER BY title ASC
            """, (artist, album)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_albums_by_artist(self, artist: str) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT DISTINCT artist, album FROM songs WHERE artist = ? ORDER BY album ASC
            """, (artist,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_previous_song(self, exclude_paths: list[str] = []) -> dict | None:
        import os
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            placeholders = ",".join(["?"] * len(exclude_paths)) if exclude_paths else "''"
            query = f"""
                SELECT DISTINCT s.path, s.*
                FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                WHERE h.song_path NOT IN ({placeholders})
                ORDER BY h.timestamp DESC
                LIMIT 50
            """
            async with db.execute(query, tuple(exclude_paths)) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                song = dict(row)
                if os.path.exists(song["path"]):
                    return song
            return None

    async def get_full_history(self, limit=10, offset=0, filter_from=None, filter_to=None) -> list[dict]:
        from datetime import datetime
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            where_clauses = []
            params = []

            if filter_from:
                dt_from = datetime.strptime(filter_from.replace('.', '-'), '%Y-%m-%d')
                where_clauses.append("h.timestamp >= ?")
                params.append(dt_from.timestamp())

            if filter_to:
                dt_to = datetime.strptime(filter_to.replace('.', '-'), '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                where_clauses.append("h.timestamp <= ?")
                params.append(dt_to.timestamp())

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            sql = f"""
                SELECT s.*, h.timestamp as played_at FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                {where_sql}
                ORDER BY h.timestamp DESC LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            async with db.execute(sql, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_history_count(self, filter_from=None, filter_to=None) -> int:
        from datetime import datetime
        async with self._connect() as db:
            where_clauses = []
            params = []

            if filter_from:
                dt_from = datetime.strptime(filter_from.replace('.', '-'), '%Y-%m-%d')
                where_clauses.append("timestamp >= ?")
                params.append(dt_from.timestamp())

            if filter_to:
                dt_to = datetime.strptime(filter_to.replace('.', '-'), '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                where_clauses.append("timestamp <= ?")
                params.append(dt_to.timestamp())

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            sql = f"SELECT COUNT(*) FROM playback_history {where_sql}"
            async with db.execute(sql, tuple(params)) as cursor:
                row = await cursor.fetchone()
                return row[0]

    async def clear_history(self):
        async with self._connect() as db:
            await db.execute("DELETE FROM playback_history")
            await db.commit()

    async def create_playlist(self, name: str, user_id: int) -> int:
        async with self._connect() as db:
            async with db.execute(
                "INSERT INTO playlists (name, user_id, created_at) VALUES (?, ?, ?)",
                (name, user_id, int(time.time()))
            ) as cursor:
                await db.commit()
                return cursor.lastrowid

    async def get_all_playlists(self, user_id: int | None = None, strictly_personal: bool = False) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            if strictly_personal and user_id:
                sql = "SELECT * FROM playlists WHERE user_id = ? ORDER BY name ASC"
                params = (user_id,)
            elif user_id:
                sql = """
                    SELECT * FROM playlists
                    ORDER BY (CASE WHEN user_id = ? THEN 0 ELSE 1 END) ASC, name ASC
                """
                params = (user_id,)
            else:
                sql = "SELECT * FROM playlists ORDER BY name ASC"
                params = ()
            
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_playlist_songs(self, playlist_id: int) -> list[dict]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            sql = """
                SELECT s.*, ps.position FROM playlist_songs ps
                JOIN songs s ON ps.song_path = s.path
                WHERE ps.playlist_id = ? ORDER BY ps.position ASC
            """
            async with db.execute(sql, (playlist_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_song_to_playlist(self, playlist_id: int, song_path: str):
        async with self._connect() as db:
            async with db.execute("SELECT MAX(position) FROM playlist_songs WHERE playlist_id = ?", (playlist_id,)) as cursor:
                res = await cursor.fetchone()
                max_pos = res[0] or 0
            await db.execute(
                "INSERT OR IGNORE INTO playlist_songs (playlist_id, song_path, position) VALUES (?, ?, ?)",
                (playlist_id, song_path, max_pos + 1)
            )
            await db.commit()

    async def remove_song_from_playlist(self, playlist_id: int, song_path: str):
        async with self._connect() as db:
            await db.execute("DELETE FROM playlist_songs WHERE playlist_id = ? AND song_path = ?", (playlist_id, song_path))
            await db.commit()

    async def delete_playlist(self, playlist_id: int):
        async with self._connect() as db:
            await db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            await db.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
            await db.commit()

    async def rename_playlist(self, playlist_id: int, new_name: str):
        async with self._connect() as db:
            await db.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id))
            await db.commit()

    async def move_song_in_playlist(self, playlist_id: int, song_path: str, direction: int):
        async with self._connect() as db:
            async with db.execute("SELECT position FROM playlist_songs WHERE playlist_id = ? AND song_path = ?", (playlist_id, song_path)) as cursor:
                row = await cursor.fetchone()
                if not row: return
                curr_pos = row[0]
            
            new_pos = curr_pos + direction
            if new_pos < 1: return

            async with db.execute("SELECT song_path FROM playlist_songs WHERE playlist_id = ? AND position = ?", (playlist_id, new_pos)) as cursor:
                other = await cursor.fetchone()
                if other:
                    await db.execute("UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND song_path = ?", (curr_pos, playlist_id, other[0]))

            await db.execute("UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND song_path = ?", (new_pos, playlist_id, song_path))
            await db.commit()

    async def get_top_artists(self, days=7, limit=5):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            where_clause = ""
            params = []
            if days is not None:
                since = int(time.time()) - (days * 24 * 3600)
                where_clause = "WHERE h.timestamp > ?"
                params.append(since)
            
            params.append(limit)
            query = f"""
                SELECT s.artist, COUNT(*) as count FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                {where_clause} GROUP BY s.artist ORDER BY count DESC LIMIT ?
            """
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_top_songs(self, days=7, limit=5):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            where_clause = ""
            params = []
            if days is not None:
                since = int(time.time()) - (days * 24 * 3600)
                where_clause = "WHERE h.timestamp > ?"
                params.append(since)
                
            params.append(limit)
            query = f"""
                SELECT s.artist, s.title, COUNT(*) as count FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                {where_clause} GROUP BY s.path ORDER BY count DESC LIMIT ?
            """
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_top_users(self, days=7, limit=5):
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            where_clause = "WHERE user_id IS NOT NULL"
            params = []
            if days is not None:
                since = int(time.time()) - (days * 24 * 3600)
                where_clause += " AND timestamp > ?"
                params.append(since)
                
            params.append(limit)
            query = f"""
                SELECT user_id, COUNT(*) as count FROM playback_history
                {where_clause} GROUP BY user_id ORDER BY count DESC LIMIT ?
            """
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

