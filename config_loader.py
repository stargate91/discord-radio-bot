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
        self.supported_extensions = set(
            data.get("supported_extensions", [])
        )
        self.genres = data.get("genres", {})
        self.ffmpeg_path = data.get("ffmpeg_path", "ffmpeg")
        self.admin_role_id = int(data.get("admin_role_id", 0))
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
        self.levifav_min_rating = ui_settings.get("levifav_min_rating", 5)
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
        self.token = os.getenv("DISCORD_TOKEN")
        if not self.token:
            raise RuntimeError(
                "DISCORD_TOKEN missing from .env"
            )

def load_config():
    path = get_config_path()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(data)
