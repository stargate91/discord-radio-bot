from config_loader import load_config
from database import DatabaseManager
from scanner import scan_music_library
from ui import update_now_playing, force_new_embed, RadioControlView
from ui import init_ui
import asyncio
import discord

config = load_config()
db = DatabaseManager()

inserted, skipped = scan_music_library(config, db)

print("\n Scan complete")
print(f"Inserted: {inserted}")
print(f"Skipped: {skipped}")

intents = discord.Intents.default()
intents.voice_states = True

bot = discord.Client(intents=intents)

class RadioState:
    def __init__(self):
        self.voice: discord.VoiceClient | None = None
        self.genre: str = config.default_genre
        self.task: asyncio.Task | None = None
        self.skip_event: asyncio.Event = asyncio.Event()
        self.current_song: dict | None = None
        self.seek_position: int | None = None
        self.is_seeking: bool = False
        self.skip_notification: bool = False
        self.volume: float = 0.5
        self.now_playing_message: discord.Message | None = None

radio = RadioState()
init_ui(bot, config, radio, db)

def get_random_song_by_genre(genre: str):
    if genre.lower() == "levifav":
        return db.get_random_song_by_rating(min_rating=5)

    return db.get_random_song_by_genre(genre)


async def ensure_voice():
    guild = bot.get_guild(config.guild_id)
    channel = guild.get_channel(config.voice_channel_id)

    if not channel:
        print("❌ Voice channel not found")
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

            if radio.is_seeking and radio.current_song:
                song = radio.current_song
            else:
                song = get_random_song_by_genre(radio.genre)
                radio.current_song = song
                radio.is_seeking = False

            if not song:
                print("❌ There is no track in this:", radio.genre)
                await asyncio.sleep(5)
                continue

            print("▶ Playing:", song)

            radio.skip_event.clear()

            before_opts = "-nostdin -re"

            if radio.seek_position is not None:
                before_opts += f" -ss {radio.seek_position}"

            volume_filter = f"-filter:a volume={radio.volume}"

            raw_source = discord.FFmpegOpusAudio(
                song["path"],
                executable=config.ffmpeg_path,
                before_options=before_opts,
                options=f"-vn {volume_filter}"
            )

            radio.seek_position = None

            done = asyncio.Event()

            def after_playing(error):
                if error:
                    print("FFMPEG error:", error)
                bot.loop.call_soon_threadsafe(done.set)

            while voice.is_playing():
                await asyncio.sleep(0.1)

            voice.play(raw_source, after=after_playing)

            while not voice.is_playing():
                await asyncio.sleep(0.05)

            await update_now_playing(song)

            radio.skip_notification = False

            song_duration = song.get("duration", 0)
            ten_percent_duration = int(song_duration * 0.1)

            start_time = asyncio.get_event_loop().time()

            wait_done = asyncio.create_task(done.wait())
            wait_skip = asyncio.create_task(radio.skip_event.wait())

            done_first, pending = await asyncio.wait(
                [wait_done, wait_skip],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            elapsed_time = asyncio.get_event_loop().time() - start_time

            if wait_skip in done_first:
                voice.stop()

                while voice.is_playing():
                    await asyncio.sleep(0.05)

                if elapsed_time >= ten_percent_duration:
                    db.update_last_played(song["path"])
                    print(f"✓ Last played updated for: {song['path']}")
            else:
                db.update_last_played(song["path"])
                print(f"✓ Last played updated for: {song['path']}")

            raw_source.cleanup()

        except Exception as e:
            print("Radio loop crash:", e)
            await asyncio.sleep(5)


async def embed_refresh_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await asyncio.sleep(58 * 60)
        await force_new_embed()

@bot.event
async def on_ready():
    print(f"Online as: {bot.user}")

    bot.add_view(RadioControlView(radio, db))

    await force_new_embed()

    if not radio.task:
        radio.task = bot.loop.create_task(radio_player())

    bot.loop.create_task(embed_refresh_loop())


bot.run(config.token)
