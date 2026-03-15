import json
import os
from dotenv import load_dotenv
load_dotenv()

def get_config_path():
    path = "config.local.json"
    if os.path.exists(path):
        return path
    return "config.json"

class Config:

    def __init__(self, data: dict):
        self.guild_id = int(data["guild_id"])
        self.voice_channel_id = int(data["voice_channel_id"])
        self.auto_join_channel_id = int(data.get("auto_join_channel_id", 0))
        self.radio_text_channel_id = int(data["radio_text_channel_id"])
        self.feedback_channel_id = int(data.get("feedback_channel_id", 0))
        self.afk_channel_id = int(data.get("afk_channel_id", 0))
        self.default_genre = data["default_genre"]
        self.default_language = data.get("default_language", "en")
        self.default_ui_mode = data.get("default_ui_mode", "full")
        self.default_presence = data.get("default_presence", "Waiting for signal...")
        scanner = data.get("scanner", {})
        self.supported_extensions = set(
            scanner.get("supported_extensions", data.get("supported_extensions", ["mp3", "flac", "wav"]))
        )
        self.cover_filenames = scanner.get("cover_filenames", [
            "cover.jpg", "cover.png", "cover.jpeg", "folder.jpg", "folder.png", "front.jpg", "front.png"
        ])
        self.metadata_fields = scanner.get("metadata_fields", {
            "artist": ["artist", "ARTIST", "TPE1"],
            "title": ["title", "TITLE", "TIT2"],
            "album": ["album", "ALBUM", "TALB"],
            "date": ["date", "DATE", "year", "YEAR", "TDRC"],
            "label": ["organization", "ORGANIZATION", "TPUB"],
            "catnum": ["catalognumber", "CATALOGNUMBER", "TXXX:CATALOGNUMBER"],
            "mediatype": ["mediatype", "MEDIATYPE", "TMED"],
            "rating": ["rating", "RATING", "POPM"]
        })
        self.locales = scanner # Alias for scanner settings as requested
        self.genres = data.get("genres", {})
        self.virtual_genres = data.get("virtual_genres", [])
        self.ffmpeg_path = data.get("ffmpeg_path", "ffmpeg")
        self.admin_role_id = int(data.get("admin_role_id", 0))
        self.sysadmin_role_id = int(data.get("sysadmin_role_id", 0))
        self.restricted_channels = {
            int(k): int(v) for k, v in data.get("restricted_channels", {}).items()
        }
        ui_settings = data.get("ui_settings", {})
        self.search_items_per_page = ui_settings.get("search_items_per_page", 5)
        self.history_items_per_page = ui_settings.get("history_items_per_page", 5)
        self.queue_items_per_page = ui_settings.get("queue_items_per_page", 5)
        self.playlist_items_per_page = ui_settings.get("playlist_items_per_page", 5)
        self.queue_refresh_limit = ui_settings.get("queue_refresh_limit", 11)
        self.player_upcoming_limit = ui_settings.get("player_upcoming_limit", 5)
        theme_data = ui_settings.get("theme", {})
        self.theme_primary = int(theme_data.get("primary", "0x5865F2"), 16)
        self.theme_secondary = int(theme_data.get("secondary", "0x2b2d31"), 16)
        self.theme_success = int(theme_data.get("success", "0x5865F2"), 16)
        self.theme_warning = int(theme_data.get("warning", "0xFEE75C"), 16)
        self.theme_danger = int(theme_data.get("danger", "0xED4245"), 16)
        self.theme_idle = int(theme_data.get("idle", "0xED4245"), 16)
        self.theme_paused = int(theme_data.get("paused", "0xFEE75C"), 16)
        self.theme_playing = int(theme_data.get("playing", "0x5865F2"), 16)
        self.theme_background = int(theme_data.get("background", "0x2b2d31"), 16)
        self.theme_accent = int(theme_data.get("accent", "0x5865F2"), 16)
        self.cleanup_interval_days = int(data.get("cleanup_interval_days", 7))
        self.scan_interval_days = int(data.get("scan_interval_days", 1))
        
        self.db_path = data.get("db_path", "data/radio.db")
        
        timings = data.get("timings", {})
        self.embed_refresh_minutes = int(timings.get("embed_refresh_minutes", 58))
        self.progress_update_seconds = int(timings.get("progress_update_seconds", 15))
        self.history_save_seconds = int(timings.get("history_save_seconds", 2))
        self.play_count_threshold_percent = float(timings.get("play_count_threshold_percent", 0.1))
        self.error_retry_seconds = int(timings.get("error_retry_seconds", 5))
        self.afk_timeout_seconds = int(timings.get("afk_timeout_seconds", 120))
        
        defaults = data.get("defaults", {})
        self.default_volume = float(defaults.get("volume", 0.5))
        self.use_loudnorm = bool(defaults.get("use_loudnorm", True))
        self.autocomplete_limit = int(defaults.get("autocomplete_limit", 25))
        
        self.languages = data.get("languages", [
            {"code": "en", "label": "English", "emoji": "🇺🇸"},
            {"code": "hu", "label": "Magyar", "emoji": "🇭🇺"}
        ])

        self.token = os.getenv("DISCORD_TOKEN")
        if not self.token:
            raise RuntimeError("DISCORD_TOKEN missing from .env")
    def save_genres(self, new_genres: dict):
        self.genres = new_genres
        path = get_config_path()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["genres"] = new_genres
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    def save_config_value(self, key: str, value):
        path = get_config_path()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    def get_token(self):
        return os.getenv("DISCORD_TOKEN")

def load_config():
    path = get_config_path()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(data)
