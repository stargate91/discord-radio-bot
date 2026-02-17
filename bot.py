import discord
from discord.ext import commands
from discord import ui, Interaction
import asyncio
import sqlite3
import os
import json
import time
import subprocess
import random

# ================= CONFIG =================

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

TOKEN = config["token"]
GUILD_ID = int(config["guild_id"])
VOICE_CHANNEL_ID = int(config["voice_channel_id"])
RADIO_TEXT_CHANNEL_ID = int(config["radio_text_channel_id"])
CURRENT_GENRE = config["default_genre"]
FFMPEG_PATH = config.get("ffmpeg_path", "ffmpeg")


# ================= SQLITE =================

DB_FILE = "radio.db"

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE,
    genre TEXT,
    play_count INTEGER DEFAULT 0,
    last_played INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_genre ON songs(genre)
""")

conn.commit()

# ================= DISCORD =================

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

voice_client: discord.VoiceClient | None = None
radio_text_channel = None
radio_message: discord.Message | None = None
radio_message_created_at = 0

play_lock = asyncio.Lock()
is_reconnecting = False

# ================= CURRENT SONG =================

current_song_start = 0
current_song_duration = 0
current_song_path = None
current_volume = 0.5

# ================= UI CONFIG =================

GENRE_DISPLAY = {
    "Drum & Bass & Jungle": "Drum & Bass / Jungle",
    "IDM & Ambient": "IDM / Ambient",
    "Dubstep & Garage": "Dubstep / Garage",
    "Vault - Rare Music": "🗝 Vault (Rare)",
    "Misc (From Downtempo to Folk)": "Misc / Downtempo → Folk",
}

GENRE_EMOJI = {
    "Drum & Bass & Jungle": "🥁",
    "IDM & Ambient": "🌌",
    "Techno": "⚙️",
    "Hardcore Gabber": "🔥",
    "Dubstep & Garage": "🔊",
    "Breakbeat": "🌀",
    "Vault - Rare Music": "🗝️",
    "DJ Mixes": "🎧",
    "Film & Movie Music": "🎬",
    "Rock & Metal": "🎸",
    "Misc / Downtempo → Folk": "🎹",
    "Alternative & Indie": "🎤",
    "Goa & Psy-Trance": "🌀",
    "Pop": "🎶",
    "House & Trance": "🏠",
    "Industrial EBM": "⚡",
    "Oldies": "💿",
}

GENRE_COLORS = {
    "Drum & Bass & Jungle": discord.Color.orange(),
    "IDM & Ambient": discord.Color.dark_teal(),
    "Techno": discord.Color.dark_gray(),
    "Hardcore Gabber": discord.Color.red(),
    "Dubstep & Garage": discord.Color.purple(),
    "Breakbeat": discord.Color.gold(),
    "Vault - Rare Music": discord.Color.dark_gold(),
    "DJ Mixes": discord.Color.blurple(),
}

LAST_UI_UPDATE = 0
UI_UPDATE_COOLDOWN = 8

# ================= AUDIO =================

def get_audio_duration(path):
    try:
        result = subprocess.run(
            [
                "ffprobe","-v","error",
                "-show_entries","format=duration",
                "-of","default=noprint_wrappers=1:nokey=1",
                path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        return float(result.stdout)
    except:
        return 0

def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02}:{seconds % 60:02}"

def create_progress_bar(elapsed, total, length=20):
    if total <= 0:
        return "▬" * length
    ratio = min(elapsed / total, 1)
    filled = int(ratio * length)
    return "▰" * filled + "▱" * (length - filled)

# ================= MUSIC =================

def import_genre_to_db(genre):
    paths = config["genres"].get(genre, [])
    to_insert = []

    for base in paths:
        if not os.path.exists(base):
            continue

        for root, _, files in os.walk(base):
            for f in files:
                if f.lower().endswith((".mp3", ".wav", ".flac", ".ogg")):
                    full = os.path.join(root, f)
                    to_insert.append((full, genre))

    cursor.executemany(
        "INSERT OR IGNORE INTO songs (path, genre) VALUES (?, ?)",
        to_insert
    )
    conn.commit()

def is_db_empty():
    cursor.execute("SELECT COUNT(*) FROM songs")
    return cursor.fetchone()[0] == 0

def get_next_song(genre):
    cursor.execute("""
        SELECT COUNT(*) FROM songs
        WHERE genre = ?
    """, (genre,))
    
    count = cursor.fetchone()[0]

    if count == 0:
        return None

    random_offset = random.randint(0, count - 1)

    cursor.execute("""
        SELECT id, path
        FROM songs
        WHERE genre = ?
        LIMIT 1 OFFSET ?
    """, (genre, random_offset))

    song = cursor.fetchone()

    if not song:
        return None

    # 4️⃣ Statisztika frissítés
    cursor.execute("""
        UPDATE songs
        SET play_count = play_count + 1,
            last_played = ?
        WHERE id = ?
    """, (int(time.time()), song["id"]))

    conn.commit()

    return song["path"]

# ================= VOICE =================

async def ensure_voice():
    global voice_client, is_reconnecting

    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(VOICE_CHANNEL_ID)

    if voice_client and voice_client.is_connected():
        return True

    if is_reconnecting:
        return False

    is_reconnecting = True
    try:
        voice_client = await channel.connect(reconnect=True)
        await asyncio.sleep(1)
    except:
        is_reconnecting = False
        return False

    is_reconnecting = False
    return True

# ================= RADIO UI =================

def build_radio_embed():
    if current_song_path:
        elapsed = time.time() - current_song_start
        total = current_song_duration
        bar = create_progress_bar(elapsed, total)
        time_text = f"{format_time(elapsed)} / {format_time(total)}"
        song_name = os.path.basename(current_song_path)
        status = "🔴 LIVE"
    else:
        bar = "▬" * 20
        time_text = "00:00 / 00:00"
        song_name = "Betöltés..."
        status = "🟡 WAITING"

    display = GENRE_DISPLAY.get(CURRENT_GENRE, CURRENT_GENRE)
    emoji = GENRE_EMOJI.get(CURRENT_GENRE, "🎶")
    color = GENRE_COLORS.get(CURRENT_GENRE, discord.Color.blurple())

    embed = discord.Embed(
        title=f"📻 PixelRadio Online • {status}",
        color=color
    )

    embed.add_field(name=f"{emoji} Műfaj", value=f"**{display}**", inline=True)
    embed.add_field(name="🔊 Hangerő", value=f"**{int(current_volume*100)}%**", inline=True)
    embed.add_field(name="🎵 Most játszott", value=f"`{song_name}`", inline=False)
    embed.add_field(name="⏱ Lejátszás", value=f"`{bar}`\n{time_text}", inline=False)

    embed.set_footer(text="PixelRadio • 24/7 Discord Radio")
    return embed

async def update_radio_message(force=False):
    global LAST_UI_UPDATE

    if not radio_message:
        return

    now = time.time()
    if not force and now - LAST_UI_UPDATE < UI_UPDATE_COOLDOWN:
        return

    LAST_UI_UPDATE = now
    await radio_message.edit(embed=build_radio_embed(), view=RadioView())

# ================= PLAYBACK =================

async def play_next(seek_time=0):
    global current_song_start, current_song_duration, current_song_path

    async with play_lock:
        if not await ensure_voice():
            return

        if voice_client.is_playing():
            return

        if seek_time == 0:
            song = get_next_song(CURRENT_GENRE)
            if not song:
                return
            current_song_path = song
            current_song_duration = get_audio_duration(song)
        else:
            song = current_song_path

        current_song_start = time.time() - seek_time
        await update_radio_message(force=True)

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                song,
                executable=FFMPEG_PATH,
                before_options=f"-ss {seek_time}" if seek_time else None
            ),
            volume=current_volume
        )

        def after_playing(_):
            bot.loop.create_task(play_next())

        voice_client.play(source, after=after_playing)

# ================= UI =================

class GenreSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=GENRE_DISPLAY.get(g, g),
                value=g,
                emoji=GENRE_EMOJI.get(g)
            )
            for g in config["genres"]
        ]
        super().__init__(placeholder="🎵 Válassz műfajt", options=options)

    async def callback(self, interaction: Interaction):
        global CURRENT_GENRE
        await interaction.response.defer()
        CURRENT_GENRE = self.values[0]
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        else:
            await play_next()

class RadioView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GenreSelect())

    @ui.button(label="⏮ -10s", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: Interaction, _):
        await interaction.response.defer()
        if not current_song_path:
            return
        elapsed = time.time() - current_song_start
        voice_client.stop()
        await play_next(max(0, elapsed - 10))

    @ui.button(label="⏭ Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: Interaction, _):
        await interaction.response.defer()
        voice_client.stop()

    @ui.button(label="⏩ +10s", style=discord.ButtonStyle.secondary)
    async def forward(self, interaction: Interaction, _):
        await interaction.response.defer()
        if not current_song_path:
            return
        elapsed = time.time() - current_song_start
        voice_client.stop()
        await play_next(min(elapsed + 10, current_song_duration))

    @ui.button(label="🔉 -10%", style=discord.ButtonStyle.secondary)
    async def volume_down(self, interaction: Interaction, _):
        global current_volume
        await interaction.response.defer()
        current_volume = max(0, current_volume - 0.1)
        if voice_client.source:
            voice_client.source.volume = current_volume
        await update_radio_message(force=True)

    @ui.button(label="🔊 +10%", style=discord.ButtonStyle.secondary)
    async def volume_up(self, interaction: Interaction, _):
        global current_volume
        await interaction.response.defer()
        current_volume = min(1, current_volume + 0.1)
        if voice_client.source:
            voice_client.source.volume = current_volume
        await update_radio_message(force=True)

# ================= EVENTS =================

@bot.event
async def on_ready():
    global radio_text_channel, radio_message

    print("Bejelentkezve:", bot.user)

    if is_db_empty():
        print("Adatbázis üres → importálás...")
        for g in config["genres"]:
            await asyncio.to_thread(import_genre_to_db, g)

    radio_text_channel = bot.get_channel(RADIO_TEXT_CHANNEL_ID)

    await ensure_voice()

    radio_message = await radio_text_channel.send(
        embed=build_radio_embed(),
        view=RadioView()
    )

    await play_next()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return

    if after.channel is None:
        await asyncio.sleep(2)
        await ensure_voice()
        await play_next()

# ================= RUN =================

bot.run(TOKEN)
