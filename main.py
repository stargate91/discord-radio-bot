from config_loader import load_config
from database import DatabaseManager
from scanner import scan_music_library
import asyncio
import discord
from discord.ext import commands
from pathlib import Path

config = load_config()
db = DatabaseManager()
inserted, skipped = scan_music_library(config, db)

print("\n Scan complete")
print(f"Inserted: {inserted}")
print(f"Skipped: {skipped}")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

class RadioState:
    def __init__(self):
        self.voice: discord.VoiceClient | None = None
        self.genre: str = config.default_genre
        self.task: asyncio.Task | None = None
        self.skip_event: asyncio.Event = asyncio.Event()

radio = RadioState()

def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


async def send_now_playing(song: dict):
    channel = bot.get_channel(config.radio_text_channel_id)

    if not channel:
        return

    genre = song.get("genre") or "Unknown Genre"
    artist = song.get("artist") or "Unknown Artist"
    title = song.get("title") or Path(song["path"]).stem
    album = song.get("album") or "Unknown Album"
    year = song.get("date") or "----"

    source = song.get("mediatype_flac") or song.get("mediatype_mp3") or "Unknown Source"

    duration = format_duration(song.get("duration", 0))

    msg = (
        f"🎧 {genre.upper()}\n"
        f"▶ **{artist} - {title}**\n"
        f"📀 {album} ({year})\n"
        f"💽 Source: {source}\n"
        f"⏱ {duration}"
    )

    await channel.send(msg)


def get_random_song_by_genre(genre: str):
    return db.get_random_song_by_genre(genre)

async def ensure_voice():

    guild = bot.get_guild(config.guild_id)
    channel = guild.get_channel(config.voice_channel_id)

    if not channel:
        print("Voice channel nem található")
        return None

    if guild.voice_client:
        radio.voice = guild.voice_client
        if radio.voice.channel.id != channel.id:
            await radio.voice.move_to(channel)
    else:
        radio.voice = await channel.connect(reconnect=True)

    return radio.voice

async def radio_player():

    await bot.wait_until_ready()

    while not bot.is_closed():
        try:

            voice = await ensure_voice()

            if not voice:
                await asyncio.sleep(5)
                continue

            song = get_random_song_by_genre(radio.genre)

            if not song:
                print("❌ Nincs szám ebben:", radio.genre)
                await asyncio.sleep(5)
                continue

            print("▶ Playing:", song)

            radio.skip_event.clear()

            source = discord.FFmpegOpusAudio(
                song["path"],
                executable=config.ffmpeg_path,
                before_options="-nostdin -re",
                options="-vn"
            )

            done = asyncio.Event()

            def after_playing(error):
                if error:
                    print("FFMPEG error:", error)
                bot.loop.call_soon_threadsafe(done.set)

            while voice.is_playing():
                await asyncio.sleep(0.1)

            voice.play(source, after=after_playing)

            while not voice.is_playing():
                await asyncio.sleep(0.05)

            await send_now_playing(song)

            wait_done = asyncio.create_task(done.wait())
            wait_skip = asyncio.create_task(radio.skip_event.wait())

            done_first, pending = await asyncio.wait(
                [wait_done, wait_skip],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if wait_skip in done_first:
                voice.stop()
                while voice.is_playing():
                    await asyncio.sleep(0.05)

            source.cleanup()

        except Exception as e:
            print("Radio loop crash:", e)
            await asyncio.sleep(5)

@bot.command()
async def skip(ctx):

    if radio.voice and radio.voice.is_playing():
        radio.skip_event.set()
        await ctx.send("⏭ Skip")


@bot.command()
async def genres(ctx):

    g = "\n".join(config.genres.keys())
    await ctx.send(f"Elérhető genre-ek:\n{g}")


@bot.command()
async def genre(ctx, *, new_genre: str):

    if new_genre not in config.genres:
        await ctx.send("❌ Nincs ilyen genre")
        return

    radio.genre = new_genre
    radio.skip_event.set()

    await ctx.send(f"🎧 Genre váltva: {new_genre}")

@bot.event
async def on_ready():

    print(f"Online mint: {bot.user}")

    if not radio.task:
        radio.task = bot.loop.create_task(radio_player())

bot.run(config.token)
