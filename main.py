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
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from commands import setup_commands
async def main():
    config = load_config()
    db = DatabaseManager(config.db_path)
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
    init_ui(bot, config, radio)
    init_player(bot, config, radio, update_now_playing, refresh_all_uis)
    setup_commands(tree, radio)
    async def embed_refresh_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(config.embed_refresh_minutes * 60)
            await force_new_embed()

    async def progress_update_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(config.progress_update_seconds)
            if radio.status == RadioStatusEnum.PLAYING and radio.now_playing_message:
                try:
                    await update_now_playing(radio.current_song or {})
                except:
                    pass

    @bot.event
    async def on_ready():
        print(f"Online as: {bot.user}")
        try:
            genres = await radio.get_all_genres()
            bot.add_view(UnifiedStandbyView(radio))
            bot.add_view(FrequencyStationView(radio))
            bot.add_view(NowPlayingView(radio, genres=genres))
            await force_new_embed()
        except Exception as e:
            print(f"Error during on_ready: {e}")

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
            
        if config.auto_join_channel_id > 0:
            try:
                channel = bot.get_channel(config.auto_join_channel_id)
                if not channel:
                    channel = await bot.fetch_channel(config.auto_join_channel_id)
                
                if channel and isinstance(channel, discord.VoiceChannel):
                    if not channel.guild.voice_client:
                        print(f"[SYSTEM] Auto-joining channel: {channel.name}")
                        await channel.connect()
                        radio.voice_channel_id = channel.id
                        radio.voice = channel.guild.voice_client
                        radio.status = RadioStatusEnum.IDLE
                        radio.embed_manager.save_message_id("player", None)
            except Exception as e:
                print(f"[SYSTEM] Auto-join failed: {e}")

        if not radio.task:
            radio.task = bot.loop.create_task(radio_player())
        bot.loop.create_task(embed_refresh_loop())
        bot.loop.create_task(progress_update_loop())
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
        
        # AFK Check logic: Disconnect if bot is left alone for X seconds
        voice_client = member.guild.voice_client
        if voice_client and voice_client.channel:
            real_members = [m for m in voice_client.channel.members if not m.bot]
            if len(real_members) == 0:
                if not radio.afk_task:
                    async def afk_timer():
                        try:
                            await asyncio.sleep(config.afk_timeout_seconds)
                            print(f"[AFK] Channel {voice_client.channel.name} empty for {config.afk_timeout_seconds}s. Auto-exiting.")
                            radio.dispatch(RadioAction.DISCONNECT, user=bot.user)
                        except asyncio.CancelledError:
                            pass
                        finally:
                            radio.afk_task = None
                    
                    radio.afk_task = asyncio.create_task(afk_timer())
                    print(f"[AFK] Bot is alone in {voice_client.channel.name}. Timer started ({config.afk_timeout_seconds}s).")
            else:
                if radio.afk_task:
                    radio.afk_task.cancel()
                    radio.afk_task = None
                    print(f"[AFK] User joined {voice_client.channel.name}. Timer cancelled.")
    async with bot:
        await bot.start(config.token)
if __name__ == "__main__":
    asyncio.run(main())
