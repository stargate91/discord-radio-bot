import discord
from pathlib import Path
from embed_state import EmbedStateManager
from scanner import find_and_save_cover
from ui_translate import t, init_translate
from ui_utils import format_duration, fixed
from ui_components import init_components
from ui_views import UnifiedStandbyView, FrequencyStationView, NowPlayingView, init_views

embed_state = EmbedStateManager()

bot = None
config = None
radio = None
db = None

def init_ui(_bot, _config, _radio, _db):
    global bot, config, radio, db
    bot = _bot
    config = _config
    radio = _radio
    db = _db
    
    init_translate(radio)
    init_components(update_now_playing)
    init_views(bot, config)

async def update_now_playing(song: dict):
    print(f"[UI] Updating now playing. Current radio language: {radio.language}")
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    if not radio.voice_channel_id:
        if radio.now_playing_message:
            try: await radio.now_playing_message.delete()
            except: pass
            radio.now_playing_message = None
            embed_state.save_message_id("player", None)

        view = UnifiedStandbyView(radio)
        if not radio.station_message:
            msg_id = embed_state.load_message_id("station")
            if msg_id:
                try: radio.station_message = await channel.fetch_message(msg_id)
                except: radio.station_message = None

        if radio.station_message:
            try: await radio.station_message.edit(view=view)
            except: radio.station_message = await channel.send(view=view)
        else:
            radio.station_message = await channel.send(view=view)
        embed_state.save_message_id("station", radio.station_message.id)
        return

    station_view = FrequencyStationView(radio)
    if not radio.station_message:
        msg_id = embed_state.load_message_id("station")
        if msg_id:
            try: radio.station_message = await channel.fetch_message(msg_id)
            except: radio.station_message = None

    if radio.station_message:
        try: await radio.station_message.edit(view=station_view)
        except: radio.station_message = await channel.send(view=station_view)
    else:
        radio.station_message = await channel.send(view=station_view)
    embed_state.save_message_id("station", radio.station_message.id)

    player_view = NowPlayingView(radio, db)
    if not radio.now_playing_message:
        msg_id = embed_state.load_message_id("player")
        if msg_id:
            try: radio.now_playing_message = await channel.fetch_message(msg_id)
            except: radio.now_playing_message = None

    file = None
    cover_path = db.get_song_cover_path(song.get("path", ""))
    if cover_path and Path(cover_path).exists():
        file = discord.File(cover_path, filename="cover.png")
    else:
        temp_path = find_and_save_cover(Path(song.get("path", "")), db)
        if temp_path:
            db.save_song_cover_path(song.get("path", ""), temp_path)
            file = discord.File(temp_path, filename="cover.png")

    if radio.now_playing_message:
        try:
            await radio.now_playing_message.edit(
                embed=None,
                view=player_view,
                attachments=[file] if file else []
            )
        except:
            radio.now_playing_message = await channel.send(view=player_view, file=file)
    else:
        radio.now_playing_message = await channel.send(view=player_view, file=file)
    embed_state.save_message_id("player", radio.now_playing_message.id)

    if radio.active_view_type == "queue":
        search_id = embed_state.load_message_id("search")
        if search_id:
            try:
                msg = await channel.fetch_message(search_id)
                from ui_views import FullQueueView
                await msg.edit(view=FullQueueView(radio, page=radio.last_queue_page))
            except: pass


async def force_new_embed():
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    for key in ["player", "station", "queue", "details", "search"]:
        msg_id = embed_state.load_message_id(key)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except: pass
            embed_state.save_message_id(key, None)

    radio.now_playing_message = None
    radio.station_message = None
    radio.queue_message = None
    radio.details_message = None
    
    radio.editing_playlist_id = None
    radio.playlist_editor_user = None

    await update_now_playing(radio.current_song or {})

async def refresh_all_uis():
    await update_now_playing(radio.current_song or {})
    
    search_id = embed_state.load_message_id("search")
    if not search_id:
        return
        
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    try:
        msg = await channel.fetch_message(search_id)
        if radio.active_view_type == "history":
            from ui_views import HistoryView
            history = db.get_full_history(
                limit=10, 
                offset=radio.last_history_page * 10,
                filter_from=radio.filter_from,
                filter_to=radio.filter_to
            )
            total_count = db.get_history_count(filter_from=radio.filter_from, filter_to=radio.filter_to)
            await msg.edit(view=HistoryView(radio, db, history, total_count, page=radio.last_history_page))
        elif radio.active_view_type == "search" and radio.last_search_query:
            from ui_views import SearchResultsView
            await msg.edit(view=SearchResultsView(
                radio, db, radio.last_search_results, radio.last_search_query, 
                radio.last_search_user, page=radio.last_search_page, 
                search_type=radio.last_search_type
            ))
        elif radio.active_view_type == "studio":
            from ui_views import PlaylistStudioView
            await msg.edit(view=PlaylistStudioView(radio, db))
        elif radio.active_view_type == "playlist_editor" and radio.editing_playlist_id:
            from ui_views import PlaylistEditorView
            await msg.edit(view=PlaylistEditorView(radio, db, radio.editing_playlist_id, page=radio.last_editor_page))
    except:
        pass
