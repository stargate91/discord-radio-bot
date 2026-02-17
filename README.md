# 📻 Discord Radio Bot

A simple 24/7 Discord radio bot that plays music from your local folders
into a voice channel.

The bot: - Connects to a voice channel automatically - Plays random
songs from selected genres - Stores songs in SQLite database - Shows a
live radio panel with progress bar - Has buttons for skip, seek and
volume control

------------------------------------------------------------------------

## ⚙️ Requirements

-   Python 3.10+
-   FFmpeg installed
-   Discord bot token
-   Music files on your computer

Python packages:

    pip install discord.py

You also need **FFmpeg** installed and added to PATH\
(or set the path inside `config.json`).

------------------------------------------------------------------------

## 📁 Project Structure

    project/
    │
    ├── bot.py
    ├── config.json
    ├── radio.db (auto created)
    └── README.md

------------------------------------------------------------------------

## 🔧 Configuration

Edit the `config.json` file:

``` json
{
    "token": "YOUR_DISCORD_BOT_TOKEN",
    "guild_id": "YOUR_SERVER_ID",
    "voice_channel_id": "VOICE_CHANNEL_ID",
    "radio_text_channel_id": "TEXT_CHANNEL_ID",
    "default_genre": "Electronic",
    "genres": {
        "Electronic": [
            "C:/music/electronic"
        ]
    }
}
```

### Fields explanation

-   **token** -- Your Discord bot token\
-   **guild_id** -- Your server ID\
-   **voice_channel_id** -- Voice channel where the bot joins\
-   **radio_text_channel_id** -- Text channel where the radio panel
    appears\
-   **default_genre** -- Genre selected at startup\
-   **genres** -- Local folders containing music

You can add multiple genres like this:

``` json
"genres": {
    "Electronic": ["C:/music/electronic"],
    "Rock": ["C:/music/rock"]
}
```

------------------------------------------------------------------------

## ▶️ Running the Bot

Start the bot:

    python bot.py

On first start: - The database will be created - Music folders will be
scanned - Songs will be imported into SQLite

------------------------------------------------------------------------

## 🎛 Features

-   🎵 Random song selection per genre
-   📊 Song play statistics stored in database
-   ⏩ Skip button
-   ⏮ Seek -10 seconds
-   ⏩ Seek +10 seconds
-   🔊 Volume control
-   📻 Live progress bar UI

------------------------------------------------------------------------

## 🗄 Database

The bot uses SQLite (`radio.db`).

Table: `songs`

Columns: - `id` - `path` - `genre` - `play_count` - `last_played`

The database is created automatically.

------------------------------------------------------------------------

## ❗ Notes

-   The bot must have permission to:
    -   Connect to voice channel
    -   Speak
    -   Send messages
    -   Use components (buttons/selects)
-   Large music folders may take some time to import first time.
-   If FFmpeg is not found, set `"ffmpeg_path"` inside config.

Example:

``` json
"ffmpeg_path": "C:/ffmpeg/bin/ffmpeg.exe"
```

------------------------------------------------------------------------

Made for learning and fun 🙂
