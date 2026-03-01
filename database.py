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
                SET last_played = ?
                WHERE path = ?
            """, (int(time.time()), song_path))
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

    def get_song_by_id(self, song_id: int):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM songs WHERE id = ?", (song_id,))
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
            
            cursor.execute("""
                SELECT *
                FROM songs
                WHERE artist LIKE ? 
                   OR title LIKE ? 
                   OR album LIKE ? 
                   OR date LIKE ?
                ORDER BY artist ASC, title ASC
            """, (search_pattern, search_pattern, search_pattern, search_pattern))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
