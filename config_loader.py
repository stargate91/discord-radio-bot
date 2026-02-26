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
        self.radio_text_channel_id = int(data["radio_text_channel_id"])

        self.default_genre = data["default_genre"]
        self.supported_extensions = set(
            data.get("supported_extensions", [])
        )
        self.genres = data.get("genres", {})
        self.ffmpeg_path = data.get("ffmpeg_path", "ffmpeg")

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
