import json
import os
from pathlib import Path


class EmbedStateManager:
    def __init__(self, file_path: str = "radio_embed_state.json"):
        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.file_path = data_dir / file_path

    def save_value(self, key: str, value):
        data = self._load_data()
        data[key] = value
        
        temp_file = self.file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp_file, self.file_path)

    def load_value(self, key: str, default=None):
        return self._load_data().get(key, default)

    def save_message_id(self, key: str, message_id: int):
        self.save_value(key, message_id)

    def load_message_id(self, key: str) -> int | None:
        return self.load_value(key)

    def _load_data(self) -> dict:
        try:
            if not self.file_path.exists():
                return {}
            content = self.file_path.read_text(encoding="utf-8").strip()
            if not content:
                return {}
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return {}

    def clear(self):
        try:
            self.file_path.unlink()
        except FileNotFoundError:
            pass