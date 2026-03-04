from config_loader import load_config
from database import DatabaseManager
from scanner import scan_music_library, cleanup_database
from monitor import start_monitoring
from ui import update_now_playing, force_new_embed, refresh_all_uis, UnifiedStandbyView, FrequencyStationView, NowPlayingView, init_ui
from radio_state import RadioState
from player_engine import radio_player, init_player
import asyncio
import discord
from discord import app_commands
from radio_actions import RadioAction
from commands import setup_commands

async def main():
    config = load_config()
    db = DatabaseManager()
    await db.initialize()

    import time
    
    
    last_cleanup = await db.get_metadata("last_cleanup", "0")
    current_time = int(time.time())
    
    if (current_time - int(last_cleanup)) > (config.cleanup_interval_days * 86400):
        print(f"[SYSTEM] Starting music library cleanup (Last run: {config.cleanup_interval_days} days ago)...")
        removed = await cleanup_database(db)
        if removed:
            print(f"[SYSTEM] Removed {removed} non-existent songs from database.")
        await db.set_metadata("last_cleanup", current_time)
    else:
        print(f"[SYSTEM] Skipping cleanup (Last run was less than {config.cleanup_interval_days} days ago).")


    last_scan = await db.get_metadata("last_scan", "0")
    if (current_time - int(last_scan)) > (config.scan_interval_days * 86400):
        print(f"[SYSTEM] Scanning for new music (Last run: {config.scan_interval_days} days ago)...")
        inserted, skipped = await scan_music_library(config, db)
        print(f"[SYSTEM] Scan complete. Added: {inserted}, Skipped/Existing: {skipped}")
        await db.set_metadata("last_scan", current_time)
    else:
        print(f"[SYSTEM] Skipping scan (Last run was less than {config.scan_interval_days} days ago).")

    intents = discord.Intents.default()
    intents.voice_states = True

    global bot
    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)

    radio = RadioState(config, db)

    init_ui(bot, config, radio, db)
    init_player(bot, config, radio, db, update_now_playing, refresh_all_uis)

    setup_commands(tree, radio, db)

    async def embed_refresh_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(58 * 60)
            await force_new_embed()

    @bot.event
    async def on_ready():
        print(f"Online as: {bot.user}")

        genres = await db.get_all_genres()
        bot.add_view(UnifiedStandbyView(radio))
        bot.add_view(FrequencyStationView(radio))
        bot.add_view(NowPlayingView(radio, db, genres=genres))

        await force_new_embed()

        try:
            guild_id = config.guild_id
            if guild_id and guild_id != "YOUR_GUILD_ID":
                target_guild = discord.Object(id=int(guild_id))
                tree.copy_global_to(guild=target_guild)
                await tree.sync(guild=target_guild)
                print(f"Slash commands synced to guild: {guild_id}")
            else:
                await tree.sync()
                print("Slash commands synced globally!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

        if not radio.task:
            radio.task = bot.loop.create_task(radio_player())

        bot.loop.create_task(embed_refresh_loop())
        
        
        monitor = start_monitoring(config, db, bot.loop)
        if monitor:
            radio.monitor = monitor

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id:
            target_channel = after.channel
            old_channel = before.channel

            if target_channel:
                if not old_channel or old_channel.id != target_channel.id:
                    radio.voice_channel_id = target_channel.id
                    radio.voice = member.guild.voice_client
                    radio.embed_manager.save_value("voice_channel_id", target_channel.id)
                    await update_now_playing(radio.current_song or {})
                    print(f"[VOICE] Bot moved to {target_channel.name}")
            elif old_channel:
                radio.voice_channel_id = None
                radio.voice = None
                radio.embed_manager.save_value("voice_channel_id", None)
                await update_now_playing(radio.current_song or {})
                print(f"[VOICE] Bot disconnected from voice")

    async with bot:
        await bot.start(config.token)

if __name__ == "__main__":
    asyncio.run(main())

