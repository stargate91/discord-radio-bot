import json
from pathlib import Path

CONFIG_FILE = Path("config.json")

class Config:
    def __init__(self, data: dict):
        self.token = data["token"]
        self.guild_id = int(data["guild_id"])
        self.voice_channel_id = int(data["voice_channel_id"])
        self.radio_text_channel_id = int(data["radio_text_channel_id"])
        self.default_genre = data["default_genre"]
        self.supported_extensions = set(data.get("supported_extensions", []))
        self.genres = data.get("genres", {})
        self.ffmpeg_path = data.get("ffmpeg_path", "ffmpeg")


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.json nem található!")

    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return Config(data)