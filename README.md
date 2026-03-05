# Discord Radio Bot

A premium, 24/7 Discord radio engine designed for high-fidelity personal hosting. It plays music from local directories, manages a rich metadata-driven library via SQLite, and provides a feature-packed interactive control panel.

## Key Features

- **24/7 Streaming**: Persistent playback that stays connected and reloads automatically.
- **Slash Command Engine**: Interactive `/play` command with real-time autocomplete search.
- **Advanced Library Management**:
    - **Smart Scanner**: Automatic metadata extraction (Artist, Title, Album, Year, Label) and cover art caching.
    - **SQLite Powered**: Fast searching and reliable storage for history, playlists, and ratings.
- **Sophisticated Control Panel**:
    - **Dual UI Modes**: Switch between **Full** (Icons + Labels) and **Compact** (Icons only) modes for different needs.
    - **Playlist Studio**: Create, rename, delete, and organize your own personal playback lists.
    - **History & Search**: Paginated history with date filtering and a robust search tab system.
- **Enhanced Interactions**:
    - **Rating System**: Like and Dislike tracks; specific support for favorites (levifav mode).
    - **Multi-language**: Seamless on-the-fly switching between **English** and **Hungarian** locales.
    - **Audio Controls**: Jump to timestamps (Seek), Forward/Back to previous tracks, and Shuffle controls.

## Project Architecture

- `main.py`: The central hub for bot initialization, event handling, and command registration.
- `commands.py`: Definition of slash commands and autocomplete interaction logic.
- `player_engine.py`: The audio playback loop, action handling, and FFmpeg streaming.
- `radio_state.py`: Global state management and action dispatching.
- `database.py`: Clean wrapper for all SQLite operations (songs, history, playlists, ratings).
- `scanner.py`: High-performance filesystem scanner with mutagen for metadata extraction.
- `ui_player.py`: The main persistent player interface (standby and now-playing views).
- `ui_studio.py`: Interfaces for managing playlists and browsing playback history.
- `ui_search.py`: Comprehensive search results with tabbed navigation (Songs, Artists, Albums, Playlists).
- `ui_translate.py`: Localization dictionary managing multi-language UI tokens.
- `ui_icons.py`: Centralized registration for all emojis and visual status indicators.
- `config_loader.py`: Handles configuration loading from config.json.

## Configuration

1. **Environment Setup**:
   Create a `.env` file in the root directory:
   ```text
   DISCORD_TOKEN=your_bot_token_here
   ```

2. **Server Configuration**:
   Edit the `config.json` file with your server details:
   ```json
   {
       "guild_id": "YOUR_SERVER_ID",
       "voice_channel_id": "VOICE_CHANNEL_ID",
       "radio_text_channel_id": "CONTROL_PANEL_TEXT_ID",
       "admin_role_id": "ADMIN_ROLE_ID",
       "genres": {
           "Electronic": ["C:/Music/Electronic"],
           "Jazz": ["C:/Music/Jazz"]
       },
       "ffmpeg_path": "ffmpeg"
   }
   ```

## Getting Started

### Prerequisites
- **Python 3.10+**
- **FFmpeg** (installed and added to your system PATH)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd discord-radio-bot

# Install required libraries
# Voice support requires [voice] extra
pip install "discord.py[voice]" mutagen python-dotenv

# Start the broadcast
python main.py
```

## Commands

- `/play <query>`: Instant search and play. Supports multi-word queries and autocomplete suggestions.
