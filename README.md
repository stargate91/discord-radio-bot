# Discord Radio Bot

This is a 24/7 Discord radio bot that plays music from local folders in a voice channel. 

It connects to a specified voice channel and plays random tracks from selected genres. The bot manages songs using an SQLite database and includes a UI panel for basic controls.

## Requirements

- Python 3.10 or higher
- FFmpeg installed and added to your system PATH
- A Discord bot token and server (guild) ID
- Music files (MP3, etc.) on your local machine

Python dependencies:
```bash
pip install discord.py mutagen python-dotenv
```

## Project Structure

- main.py: The main entry point for the bot.
- config_loader.py: Handles loading settings from config.json.
- database.py: Manages the SQLite database for song metadata.
- scanner.py: Scans local folders and adds songs to the database.
- ui.py: Handles the Discord embed and button interactions.
- radio.db: The database file (created automatically).
- radio_actions.py: Handles the bot's actions.
- embed_state.py: Handles the bot's embed state.

## Configuration

The bot uses a `config.json` file for general settings and a `.env` file for the sensitive Discord token.

### 1. Set up the Token

Create a file named `.env` in the root directory and add your Discord bot token (from the developer portal):

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
    "ffmpeg_path": "C:/ffmpeg/bin/ffmpeg.exe"
}
```

### Configuration terms:

- guild_id: The ID of the server where the bot will operate.
- voice_channel_id: The ID of the voice channel the bot should join.
- radio_text_channel_id: The ID of the text channel for the control panel.
- default_genre: The genre the bot starts playing when launched.
- genres: A mapping of genre names to lists of local folder paths.
- ffmpeg_path: Optional path to the ffmpeg executable if it is not in your system PATH.

## How it works

1. Run the bot:
   ```bash
   python main.py
   ```
2. On the first run, the bot will scan the folders defined in config.json.
3. It saves song metadata (path, genre, duration) in radio.db.
4. The bot joins the voice channel and starts playing random tracks.
5. It displays a persistent UI panel in the text channel with playback information.

## Features

- Automatic voice channel connection.
- Local library scanning and database storage.
- UI panel with progress bar and current song info.
- Buttons for:
    - Skip: Play the next random song.
    - Seek: Jump to a specific time in the song.
    - Volume: Adjust the playback volume between 0% and 100%.
    - Like: Like the current song.
    - Dislike: Dislike the current song.

## Database Info

The bot uses SQLite (radio.db). The main table is 'songs' which stores:
- id
- path
- genre
- play_count
- last_played
- likes
- dislikes

## Troubleshooting

- Permission issues: Ensure the bot has 'Connect', 'Speak', 'Send Messages', and 'Use External Emojis' permissions.
- FFmpeg not found: If the bot crashes regarding ffmpeg, double-check the 'ffmpeg_path' in your config.json.
- Slow startup: Large music libraries might take a moment to scan on the first launch.

This project was built for learning Python and the discord.py library.
