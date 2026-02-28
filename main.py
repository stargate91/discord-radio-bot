from config_loader import load_config
from database import DatabaseManager
from scanner import scan_music_library
from ui import update_now_playing, force_new_embed, RadioControlView
from ui import init_ui
import asyncio
import discord

from radio_actions import RadioState as RadioStatusEnum, RadioAction
import asyncio

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
        self.queue_message: discord.Message | None = None
        self.queue: list[dict] = []
        self.show_queue: bool = False
        self.show_details: bool = False
        self.details_message: discord.Message | None = None
        
        self.status = RadioStatusEnum.PLAYING
        self.action_queue = asyncio.Queue()
        self.last_user: discord.Member | discord.User | None = None

    def refresh_queue(self):
        self.queue = []
        for _ in range(11):
            song = get_random_song_by_genre(self.genre)
            if song:
                self.queue.append(song)

    def dispatch(self, action: RadioAction, data=None, user: discord.Member | discord.User | None = None):
        print(f"[ACTION] Dispatching: {action.name} with data: {data} by user: {user}")
        if user:
            self.last_user = user
        self.action_queue.put_nowait((action, data))

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

            if radio.status == RadioStatusEnum.IDLE:
                print("[RADIO] Idle, waiting for action...")
                action, data = await radio.action_queue.get()
                if action == RadioAction.SET_GENRE:
                    radio.genre = data
                    radio.is_seeking = False
                    radio.refresh_queue()
                elif action == RadioAction.SET_VOLUME:
                    radio.volume = data
                    continue
                elif action == RadioAction.REPLAY:
                    radio.is_seeking = True
                    radio.seek_position = 0
                elif action == RadioAction.SKIP:
                    radio.is_seeking = False
                else:
                    continue
                
                radio.status = RadioStatusEnum.PLAYING

            while radio.action_queue.qsize() > 0:
                action, data = radio.action_queue.get_nowait()
                if action == RadioAction.SET_GENRE:
                    radio.genre = data
                    radio.is_seeking = False
                    radio.refresh_queue()
                elif action == RadioAction.SET_VOLUME:
                    radio.volume = data
                elif action == RadioAction.SKIP:
                    radio.is_seeking = False
                elif action == RadioAction.STOP:
                    radio.status = RadioStatusEnum.IDLE
                    radio.refresh_queue()

            if radio.status == RadioStatusEnum.IDLE:
                continue

            if radio.is_seeking and radio.current_song:
                song = radio.current_song
            else:
                if not radio.queue:
                    radio.refresh_queue()
                
                if radio.queue:
                    song = radio.queue.pop(0)
                    new_song = get_random_song_by_genre(radio.genre)
                    if new_song:
                        radio.queue.append(new_song)
                else:
                    song = None

                radio.current_song = song
            
            radio.is_seeking = False

            if not song:
                print("❌ There is no track in this:", radio.genre)
                radio.status = RadioStatusEnum.IDLE
                await asyncio.sleep(5)
                continue

            radio.status = RadioStatusEnum.PLAYING
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

            while voice.is_playing() or voice.is_paused():
                await asyncio.sleep(0.1)

            voice.play(raw_source, after=after_playing)

            while not voice.is_playing() and not voice.is_paused():
                await asyncio.sleep(0.05)

            await update_now_playing(song)
            radio.skip_notification = False

            song_duration = song.get("duration", 0)
            ten_percent_duration = int(song_duration * 0.1)
            start_time = asyncio.get_event_loop().time()

            while not done.is_set():
                try:
                    action_task = asyncio.create_task(radio.action_queue.get())
                    done_task = asyncio.create_task(done.wait())
                    
                    finished, pending = await asyncio.wait(
                        [action_task, done_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=5.0
                    )

                    for task in pending:
                        task.cancel()

                    if action_task in finished:
                        action, data = action_task.result()
                        print(f"[PROCESS] Action: {action.name}")
                        
                        if action == RadioAction.SKIP:
                            radio.is_seeking = False
                            voice.stop()
                            break
                        elif action == RadioAction.SEEK:
                            radio.seek_position = data
                            radio.is_seeking = True
                            radio.skip_notification = True
                            voice.stop()
                            break
                        elif action == RadioAction.SET_VOLUME:
                            radio.volume = data
                            radio.is_seeking = True
                            radio.skip_notification = True
                            voice.stop()
                            break
                        elif action == RadioAction.REPLAY:
                            if radio.status == RadioStatusEnum.PAUSED:
                                voice.resume()
                                radio.status = RadioStatusEnum.PLAYING
                                await update_now_playing(song)
                            else:
                                radio.seek_position = 0
                                radio.is_seeking = True
                                radio.skip_notification = True
                                voice.stop()
                                break
                        elif action == RadioAction.PAUSE:
                            if voice.is_playing():
                                voice.pause()
                                radio.status = RadioStatusEnum.PAUSED
                                await update_now_playing(song)
                        elif action == RadioAction.STOP:
                            radio.is_seeking = True
                            radio.seek_position = 0
                            radio.status = RadioStatusEnum.IDLE
                            voice.stop()
                            await update_now_playing(song)
                            break
                        elif action == RadioAction.SET_GENRE:
                            radio.genre = data
                            radio.is_seeking = False
                            radio.refresh_queue()
                            voice.stop()
                            break
                    
                    if done_task in finished:
                        break

                except asyncio.TimeoutError:
                    continue

            elapsed_time = asyncio.get_event_loop().time() - start_time

            if elapsed_time >= ten_percent_duration or not radio.is_seeking:
                db.update_last_played(song["path"])
                print(f"✓ Last played updated for: {song['path']}")

            raw_source.cleanup()

        except Exception as e:
            print("Radio loop crash:", e)
            import traceback
            traceback.print_exc()
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
