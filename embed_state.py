import json
import os
from pathlib import Path


class EmbedStateManager:
    def __init__(self, file_path: str = "radio_embed_state.json"):
        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.file_path = data_dir / file_path

    def save_message_id(self, message_id: int):
        temp_file = self.file_path.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({"message_id": message_id}, f)

        os.replace(temp_file, self.file_path)

    def load_message_id(self) -> int | None:
        try:
            if not self.file_path.exists():
                return None

            content = self.file_path.read_text(encoding="utf-8").strip()
            if not content:
                return None

            data = json.loads(content)
            return data.get("message_id")

        except (json.JSONDecodeError, OSError):
            return None

    def clear(self):
        try:
            self.file_path.unlink()
        except FileNotFoundError:
            pass