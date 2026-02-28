# Discord Radio Bot

This is a 24/7 Discord radio bot that plays music from local folders in a voice channel. 

It connects to a specified voice channel and plays random tracks from selected genres. The bot manages songs using an SQLite database and includes a comprehensive UI panel for control.

## Requirements

- Python 3.10 or higher
- FFmpeg installed and added to your system PATH
- A Discord bot token and server (guild) ID
- Music files (MP3, FLAC, etc.) on your local machine

Python dependencies:
```bash
pip install discord.py mutagen python-dotenv
```

## Project Structure

- `main.py`: The main entry point, managing the radio loop and Discord client.
- `config_loader.py`: Handles loading settings from `config.json`.
- `database.py`: Manages the SQLite database (`data/radio.db`).
- `scanner.py`: Scans local folders, extracts metadata, and handles cover art.
- `ui.py`: Handles the Discord embeds and button interactions.
- `embed_state.py`: Manages persistent message IDs to keep the UI up-to-date across restarts.
- `radio_actions.py`: Defines the actions and states for the radio engine.
- `data/`: Directory containing the database and cached cover art.

## Configuration

The bot uses a `config.json` file for general settings and a `.env` file for the sensitive Discord token.

### 1. Set up the Token

Create a file named `.env` in the root directory and add your Discord bot token:

```text
DISCORD_TOKEN=your_token_here
```

### 2. General Settings

Set up your `config.json` file with your server details:

```json
{
    "guild_id": "YOUR_SERVER_ID",
    "voice_channel_id": "VOICE_CHANNEL_ID",
    "radio_text_channel_id": "TEXT_CHANNEL_ID",
    "default_genre": "Electronic",
    "genres": {
        "Electronic": [
            "C:/music/electronic"
        ],
        "Rock": [
            "C:/music/rock"
        ]
    },
    "ffmpeg_path": "C:/ffmpeg/bin/ffmpeg.exe",
    "supported_extensions": ["mp3", "flac", "m4a", "wav"]
}
```

### Configuration terms:

- `guild_id`: The ID of the server where the bot will operate.
- `voice_channel_id`: The ID of the voice channel the bot should join.
- `radio_text_channel_id`: The ID of the text channel for the control panel.
- `default_genre`: The genre the bot starts playing when launched.
- `genres`: A mapping of genre names to lists of local folder paths.
- `ffmpeg_path`: Optional path to the ffmpeg executable.
- `supported_extensions`: List of file extensions the scanner should look for.

## How it works

1. Run the bot:
   ```bash
   python main.py
   ```
2. On the first run, the bot scans the folders defined in `config.json`.
3. It extracts metadata (Artist, Title, Album, Year, Label, Duration, etc.).
4. It extracts and caches cover art in `data/covers/`.
5. The bot joins the voice channel and starts playing random tracks.
6. A persistent UI panel is displayed in the text channel for management.

## Features

- **24/7 Playback**: Automatically reconnects and plays music.
- **Queue System**: Keeps track of upcoming songs (toggleable view).
- **Genre Switching**: Change genres on the fly via a dropdown menu.
- **Cover Art**: Displays album art in the detailed info view.
- **Ratings**: Users can Like or Dislike songs, and the bot can prioritize favorites (`levifav`).
- **Persistent UI**: UI messages are tracked and updated to prevent spam.

### Controls

- **▶ Play**: Resume or replay the current track.
- **⏸ Pause**: Pause playback.
- **⏹ Stop**: Stop playback and go to IDLE state.
- **⏭ Skip**: Play the next random song from the queue.
- **⏩ Move To**: Jump to a specific timestamp (mm:ss).
- **🔊 Vol**: Adjust the playback volume (0-100%).
- **❤️ Like / 👎 Dislike**: Rate the current track.
- **📂 Info**: Toggle the detailed metadata and cover art embed.
- **📋 Queue**: Toggle the "Up Next" list.

## Database Info

The bot uses SQLite (`data/radio.db`). Key tables:

- `songs`: Stores path, metadata (artist, title, etc.), play counts, and aggregate ratings.
- `user_ratings`: Tracks individual user likes/dislikes.
- `song_covers`: Links song paths to cached cover art files.

## Troubleshooting

- **Permission issues**: Ensure the bot has 'Connect', 'Speak', 'Send Messages', and 'Use External Emojis'.
- **FFmpeg not found**: Double-check `ffmpeg_path` or ensure it's in your system PATH.
- **Slow startup**: Initial scan of large libraries may take time.

---
Built for high-fidelity personal radio hosting.
