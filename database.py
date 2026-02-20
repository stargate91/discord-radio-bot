import sqlite3
from pathlib import Path

DB_FILE = "radio.db"

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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_genre ON songs(genre)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist ON songs(artist)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_album ON songs(album)")

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
            genre,
            duration,
            mediatype_flac,
            mediatype_mp3,
            rating
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["path"],
        data["artist"],
        data["title"],
        data["album"],
        data["date"],
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