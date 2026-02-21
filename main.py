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
        self.stop_event: asyncio.Event = asyncio.Event()

        self.current_song: dict | None = None
        self.paused: bool = False
        self.restart: bool = False

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

            if radio.stop_event.is_set():
                await asyncio.sleep(0.5)
                continue

            if not radio.current_song:
                song = get_random_song_by_genre(radio.genre)
                if not song:
                    await asyncio.sleep(5)
                    continue
                radio.current_song = song
            else:
                song = radio.current_song

            if not song:
                print("❌ Nincs szám ebben:", radio.genre)
                await asyncio.sleep(5)
                continue

            radio.paused = False
            radio.skip_event.clear()

            print("▶ Playing:", song)

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

            # biztos ne menjen párhuzamosan
            while voice.is_playing():
                await asyncio.sleep(0.1)

            voice.play(source, after=after_playing)

            while not voice.is_playing():
                await asyncio.sleep(0.05)

            await send_now_playing(song)

            wait_done = asyncio.create_task(done.wait())
            wait_skip = asyncio.create_task(radio.skip_event.wait())
            wait_stop = asyncio.create_task(radio.stop_event.wait())

            done_first, pending = await asyncio.wait(
                [wait_done, wait_skip, wait_stop],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if wait_stop in done_first:
                voice.stop()
                source.cleanup()
                while radio.stop_event.is_set():
                    await asyncio.sleep(0.5)
                continue

            if wait_skip in done_first:
                voice.stop()
                radio.skip_event.clear()
                radio.current_song = None

            if wait_done in done_first:
                if radio.restart:
                    radio.restart = False
                else:
                    radio.current_song = None

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

@bot.command()
async def pause(ctx):
    if not radio.voice or not radio.voice.is_playing():
        await ctx.send("⏸ Nincs mit pause-olni")
        return

    radio.voice.pause()
    radio.paused = True
    await ctx.send("⏸ Pause")

@bot.command()
async def play(ctx):

    voice = radio.voice
    if not voice:
        await ctx.send("❌ Nem vagyok voice channelben")
        return

    if radio.stop_event.is_set():
        radio.stop_event.clear()
        await ctx.send("▶ Lejátszás indítva")
        return

    if radio.paused:
        voice.resume()
        radio.paused = False
        await ctx.send("▶ Folytatás")
        return

    if voice.is_playing() and radio.current_song:
        radio.restart = True
        voice.stop()
        await ctx.send("▶ Újrakezdve (0:00)")

@bot.command()
async def stop(ctx):

    if not radio.voice:
        return

    radio.stop_event.set()
    radio.paused = False

    if radio.voice.is_playing():
        radio.voice.stop()

    await ctx.send("⏹ Stop (lejátszás megállítva)")

@bot.event
async def on_ready():

    print(f"Online mint: {bot.user}")

    if not radio.task:
        radio.task = bot.loop.create_task(radio_player())

bot.run(config.token)
