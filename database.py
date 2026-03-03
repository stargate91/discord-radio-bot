import sqlite3
import time
from pathlib import Path

DB_DIR = Path("data")
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DB_DIR / "radio.db"

class DatabaseManager:
    def __init__(self):
        self.db_file = DB_FILE
        self._init_db()

    def _init_db(self):

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA journal_mode=WAL;")

            cursor.execute("""
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
                dislikes INTEGER DEFAULT 0
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ratings (
                user_id INTEGER,
                song_path TEXT,
                rating_type TEXT CHECK(rating_type IN ('like', 'dislike')),
                PRIMARY KEY (user_id, song_path)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_genre ON songs(genre)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist ON songs(artist)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_album ON songs(album)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON songs(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON songs(date)")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS song_covers (
                song_path TEXT PRIMARY KEY,
                cover_path TEXT,
                FOREIGN KEY(song_path) REFERENCES songs(path) ON DELETE CASCADE
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER,
                created_at INTEGER NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER,
                song_path TEXT,
                position INTEGER,
                PRIMARY KEY (playlist_id, song_path),
                FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY(song_path) REFERENCES songs(path) ON DELETE CASCADE
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON playback_history(timestamp)")

    def is_empty(self) -> bool:

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM songs")
            return cursor.fetchone()[0] == 0

    def insert_song_batch(self, cursor, data: dict):

        cursor.execute("""
        INSERT OR IGNORE INTO songs (
            path,
            artist,
            title,
            album,
            date,
            label,
            catnum,
            genre,
            duration,
            mediatype_flac,
            mediatype_mp3,
            rating
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["path"],
        data["artist"],
        data["title"],
        data["album"],
        data["date"],
        data["label"],
        data["catnum"],
        data["genre"],
        data["duration"],
        data["mediatype_flac"],
        data["mediatype_mp3"],
        data["rating"]
    ))
        return cursor.rowcount > 0

    def get_random_song_by_genre(self, genre: str):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM songs
                WHERE genre = ?
                ORDER BY RANDOM()
                LIMIT 1
            """, (genre,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def _connect(self):
        return sqlite3.connect(self.db_file)

    def update_last_played(self, song_path: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE songs
                SET last_played = ?, play_count = play_count + 1
                WHERE path = ?
            """, (int(time.time()), song_path))
            conn.commit()

    def add_to_history(self, song_path: str, user_id: int | None = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playback_history (song_path, user_id, timestamp)
                VALUES (?, ?, ?)
            """, (song_path, user_id, int(time.time())))
            conn.commit()

    def get_random_song_by_rating(self, min_rating: int = 5):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM songs
                WHERE rating >= ?
                ORDER BY RANDOM()
                LIMIT 1
            """, (min_rating,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_genres(self) -> list[str]:
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT genre
                FROM songs
                WHERE genre IS NOT NULL
                  AND genre != ''
                ORDER BY genre COLLATE NOCASE ASC
            """)

            rows = cursor.fetchall()

            return [row[0] for row in rows]

    def get_song_by_path(self, path: str):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM songs WHERE path = ?", (path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def toggle_rating(self, user_id: int, song_path: str, rating_type: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT rating_type FROM user_ratings WHERE user_id = ? AND song_path = ?",
                (user_id, song_path)
            )
            existing = cursor.fetchone()
            
            status = ""
            if existing:
                existing_type = existing[0]
                if existing_type == rating_type:
                    cursor.execute(
                        "DELETE FROM user_ratings WHERE user_id = ? AND song_path = ?",
                        (user_id, song_path)
                    )
                    column = "likes" if rating_type == "like" else "dislikes"
                    cursor.execute(f"UPDATE songs SET {column} = {column} - 1 WHERE path = ?", (song_path,))
                    status = "removed"
                else:
                    cursor.execute(
                        "UPDATE user_ratings SET rating_type = ? WHERE user_id = ? AND song_path = ?",
                        (rating_type, user_id, song_path)
                    )
                    old_col = "likes" if existing_type == "like" else "dislikes"
                    new_col = "likes" if rating_type == "like" else "dislikes"
                    cursor.execute(f"UPDATE songs SET {old_col} = {old_col} - 1, {new_col} = {new_col} + 1 WHERE path = ?", (song_path,))
                    status = "changed"
            else:
                cursor.execute(
                    "INSERT INTO user_ratings (user_id, song_path, rating_type) VALUES (?, ?, ?)",
                    (user_id, song_path, rating_type)
                )
                column = "likes" if rating_type == "like" else "dislikes"
                cursor.execute(f"UPDATE songs SET {column} = {column} + 1 WHERE path = ?", (song_path,))
                status = "added"
                
            conn.commit()
            return status

    def get_song_cover_path(self, song_path: str) -> str | None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cover_path FROM song_covers WHERE song_path = ?", (song_path,))
            row = cursor.fetchone()
            return row[0] if row else None

    def save_song_cover_path(self, song_path: str, cover_path: str, cursor=None):
        if cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO song_covers (song_path, cover_path)
                VALUES (?, ?)
            """, (song_path, cover_path))
            return

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO song_covers (song_path, cover_path)
                VALUES (?, ?)
            """, (song_path, cover_path))
            conn.commit()

    def search_songs(self, query: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            search_pattern = f"%{query}%"
            start_pattern = f"{query}%"
            
            cursor.execute("""
                SELECT *,
                    CASE 
                        WHEN artist = ? OR title = ? THEN 1
                        WHEN artist LIKE ? OR title LIKE ? THEN 2
                        ELSE 3
                    END as priority
                FROM songs
                WHERE artist LIKE ? 
                   OR title LIKE ? 
                   OR album LIKE ? 
                   OR date LIKE ?
                ORDER BY priority ASC, artist ASC, title ASC
            """, (query, query, start_pattern, start_pattern, search_pattern, search_pattern, search_pattern, search_pattern))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def search_by_artist(self, artist: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM songs
                WHERE artist = ?
                ORDER BY title ASC
            """, (artist,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def search_artists(self, query: str) -> list[str]:
        with self._connect() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            start_pattern = f"{query}%"
            cursor.execute("""
                SELECT DISTINCT artist,
                    CASE 
                        WHEN artist = ? THEN 1
                        WHEN artist LIKE ? THEN 2
                        ELSE 3
                    END as priority
                FROM songs
                WHERE artist LIKE ?
                ORDER BY priority ASC, artist ASC
            """, (query, start_pattern, search_pattern))
            return [row[0] for row in cursor.fetchall()]

    def search_albums(self, query: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            start_pattern = f"{query}%"
            cursor.execute("""
                SELECT DISTINCT artist, album,
                    CASE 
                        WHEN album = ? THEN 1
                        WHEN album LIKE ? THEN 2
                        ELSE 3
                    END as priority
                FROM songs
                WHERE album LIKE ?
                ORDER BY priority ASC, album ASC
            """, (query, start_pattern, search_pattern))
            return [dict(row) for row in cursor.fetchall()]

    def search_by_album(self, artist: str, album: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM songs
                WHERE artist = ? AND album = ?
                ORDER BY title ASC
            """, (artist, album))
            return [dict(row) for row in cursor.fetchall()]

    def get_albums_by_artist(self, artist: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT artist, album
                FROM songs
                WHERE artist = ?
                ORDER BY album ASC
            """, (artist,))
            return [dict(row) for row in cursor.fetchall()]

    def get_previous_song(self, exclude_paths: list[str] = []) -> dict | None:
        import os
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            placeholders = ",".join(["?"] * len(exclude_paths)) if exclude_paths else "''"
            query = f"""
                SELECT DISTINCT s.path, s.* 
                FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                WHERE h.song_path NOT IN ({placeholders})
                ORDER BY h.timestamp DESC
                LIMIT 50
            """
            cursor.execute(query, tuple(exclude_paths))
            rows = cursor.fetchall()
            
            for row in rows:
                song = dict(row)
                if os.path.exists(song["path"]):
                    return song
                    
            return None

    def get_full_history(self, limit=10, offset=0, filter_from=None, filter_to=None) -> list[dict]:
        from datetime import datetime
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
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
                SELECT s.*, h.timestamp as played_at
                FROM playback_history h
                JOIN songs s ON h.song_path = s.path
                {where_sql}
                ORDER BY h.timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor.execute(sql, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

    def get_history_count(self, filter_from=None, filter_to=None) -> int:
        from datetime import datetime
        with self._connect() as conn:
            cursor = conn.cursor()
            
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
            cursor.execute(sql, tuple(params))
            return cursor.fetchone()[0]

    def clear_history(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playback_history")
            conn.commit()

    def create_playlist(self, name: str, user_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO playlists (name, user_id, created_at) VALUES (?, ?, ?)",
                (name, user_id, int(time.time()))
            )
            conn.commit()
            return cursor.lastrowid

    def get_all_playlists(self, user_id: int | None = None, strictly_personal: bool = False) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if strictly_personal and user_id:
                cursor.execute("SELECT * FROM playlists WHERE user_id = ? ORDER BY name ASC", (user_id,))
            elif user_id:
                # Order by: first own playlists (0), then others (1). Within those, alphabetical by name.
                cursor.execute("""
                    SELECT * FROM playlists 
                    ORDER BY (CASE WHEN user_id = ? THEN 0 ELSE 1 END) ASC, name ASC
                """, (user_id,))
            else:
                cursor.execute("SELECT * FROM playlists ORDER BY name ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_playlist_songs(self, playlist_id: int) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, ps.position 
                FROM playlist_songs ps
                JOIN songs s ON ps.song_path = s.path
                WHERE ps.playlist_id = ?
                ORDER BY ps.position ASC
            """, (playlist_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_song_to_playlist(self, playlist_id: int, song_path: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(position) FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
            max_pos = cursor.fetchone()[0] or 0
            cursor.execute(
                "INSERT OR IGNORE INTO playlist_songs (playlist_id, song_path, position) VALUES (?, ?, ?)",
                (playlist_id, song_path, max_pos + 1)
            )
            conn.commit()

    def remove_song_from_playlist(self, playlist_id: int, song_path: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlist_songs WHERE playlist_id = ? AND song_path = ?", (playlist_id, song_path))
            conn.commit()

    def delete_playlist(self, playlist_id: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            cursor.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
            conn.commit()

    def rename_playlist(self, playlist_id: int, new_name: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id))
            conn.commit()

    def move_song_in_playlist(self, playlist_id: int, song_path: str, direction: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT position FROM playlist_songs WHERE playlist_id = ? AND song_path = ?", (playlist_id, song_path))
            row = cursor.fetchone()
            if not row: return
            curr_pos = row[0]
            new_pos = curr_pos + direction
            if new_pos < 1: return

            cursor.execute("SELECT song_path FROM playlist_songs WHERE playlist_id = ? AND position = ?", (playlist_id, new_pos))
            other = cursor.fetchone()
            if other:
                cursor.execute("UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND song_path = ?", (curr_pos, playlist_id, other[0]))
            
            cursor.execute("UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND song_path = ?", (new_pos, playlist_id, song_path))
            conn.commit()
