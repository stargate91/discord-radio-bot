from config_loader import load_config
from database import DatabaseManager
from scanner import scan_music_library
from ui import update_now_playing, force_new_embed, UnifiedStandbyView, FrequencyStationView, NowPlayingView, init_ui
from radio_state import RadioState
from player_engine import radio_player, init_player
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

radio = RadioState(config, db)

init_ui(bot, config, radio, db)
init_player(bot, config, radio, db, update_now_playing)

async def embed_refresh_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(58 * 60)
        await force_new_embed()

@bot.event
async def on_ready():
    print(f"Online as: {bot.user}")

    bot.add_view(UnifiedStandbyView(radio))
    bot.add_view(FrequencyStationView(radio))
    bot.add_view(NowPlayingView(radio, db))

    await force_new_embed()

    if not radio.task:
        radio.task = bot.loop.create_task(radio_player())

    bot.loop.create_task(embed_refresh_loop())

bot.run(config.token)
