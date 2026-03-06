import discord
from pathlib import Path
from scanner import find_and_save_cover
from ui_translate import t, init_translate
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_base import handle_ui_error
from ui_player import UnifiedStandbyView, FrequencyStationView, NowPlayingView, init_player_ui
from ui_search import SearchResultsView, FullQueueView
from ui_studio import PlaylistStudioView, PlaylistEditorView, HistoryView
from ui_utils import safe_delete_message, safe_fetch_message
bot = None
config = None
radio = None

def init_ui(_bot, _config, _radio):
    global bot, config, radio
    bot = _bot
    config = _config
    radio = _radio
    init_translate(radio)
    from ui_theme import Theme
    Theme.init_theme(config)
    init_player_ui(bot, config, update_now_playing)
async def update_now_playing(song: dict):
    try:
        if radio.status == RadioStatusEnum.PLAYING and song:
            artist = song.get("artist", "Unknown")
            title = song.get("title", "Unknown")
            prefix = t("presence_listening")
            activity = discord.Game(name=f"{prefix} {artist} - {title}")
            await bot.change_presence(activity=activity)
        elif radio.status == RadioStatusEnum.PAUSED and song:
            artist = song.get("artist", "Unknown")
            title = song.get("title", "Unknown")
            status_text = t("presence_paused")
            activity = discord.Game(name=f"[{status_text}] {artist} - {title}")
            await bot.change_presence(activity=activity)
        else:
            activity = discord.Game(name=config.default_presence)
            await bot.change_presence(activity=activity)
    except Exception as e:
        print(f"Failed to update presence: {e}")
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(config.radio_text_channel_id)
        except Exception as e:
            return

    is_idle = radio.status == RadioStatusEnum.IDLE
    has_no_song = not song or not song.get("path")
    
    if not radio.voice_channel_id or has_no_song:
        if radio.now_playing_message:
            await safe_delete_message(radio.now_playing_message)
            radio.now_playing_message = None
            radio.embed_manager.save_message_id("player", None)
        
        # Always show standby view if idle or no song, even if in voice channel
        view = UnifiedStandbyView(radio)
        if not radio.station_message:
            msg_id = radio.embed_manager.load_message_id("station")
            radio.station_message = await safe_fetch_message(channel, msg_id)
        
        if radio.station_message:
            try: 
                await radio.station_message.edit(view=view)
            except Exception as e: 
                radio.station_message = await channel.send(view=view)
        else:
            radio.station_message = await channel.send(view=view)
        
        radio.embed_manager.save_message_id("station", radio.station_message.id)
        return
    station_view = FrequencyStationView(radio)
    if not radio.station_message:
        msg_id = radio.embed_manager.load_message_id("station")
        radio.station_message = await safe_fetch_message(channel, msg_id)
    if radio.station_message:
        try: await radio.station_message.edit(view=station_view)
        except: radio.station_message = await channel.send(view=station_view)
    else:
        radio.station_message = await channel.send(view=station_view)
    radio.embed_manager.save_message_id("station", radio.station_message.id)
    file = None
    cover_path = None
    song_path = song.get("path")
    if song_path:
        cover_path = await radio.db.get_song_cover_path(song_path)
        if not cover_path or not Path(cover_path).exists():
            temp_path = await find_and_save_cover(Path(song_path))
            if temp_path:
                await radio.db.save_song_cover_path(song_path, temp_path)
                cover_path = temp_path
    valid_file = False
    if cover_path and Path(cover_path).exists() and Path(cover_path).is_file():
        try:
            file = discord.File(str(cover_path), filename="cover.png")
            valid_file = True
        except:
            file = None
    genres = await radio.db.get_all_genres()

    is_fav = False
    if song and radio.last_user:
        is_fav = await radio.db.is_song_in_favorites(radio.last_user.id, song.get("path", ""))

    player_view = NowPlayingView(radio, genres=genres, song=song, cover_path=cover_path if valid_file else None, is_favorited=is_fav)
    if not radio.now_playing_message:
        msg_id = radio.embed_manager.load_message_id("player")
        radio.now_playing_message = await safe_fetch_message(channel, msg_id)
    if radio.now_playing_message:
        try:
            await radio.now_playing_message.edit(
                embed=None,
                view=player_view,
                attachments=[file] if file else []
            )
        except Exception as e:
            retry_file = None
            if cover_path and Path(cover_path).exists():
                retry_file = discord.File(cover_path, filename="cover.png")
            radio.now_playing_message = await channel.send(view=player_view, file=retry_file)
    else:
        radio.now_playing_message = await channel.send(view=player_view, file=file)
    radio.embed_manager.save_message_id("player", radio.now_playing_message.id)
    if radio.active_view_type == "queue":
        search_id = radio.embed_manager.load_message_id("search")
        msg = await safe_fetch_message(channel, search_id)
        if msg:
            try:
                await msg.edit(view=FullQueueView(radio, page=radio.last_queue_page))
            except Exception as e:
                print(f"[UI] Failed to auto-refresh queue view: {e}")
async def force_new_embed():
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return
    
    for key in ["player", "station", "queue", "details", "search"]:
        msg_id = radio.embed_manager.load_message_id(key)
        if msg_id:
            msg = await safe_fetch_message(channel, msg_id)
            if msg:
                await safe_delete_message(msg)
        radio.embed_manager.save_message_id(key, None)
    
    radio.now_playing_message = None
    radio.station_message = None
    radio.editing_playlist_id = None
    radio.playlist_editor_user = None
    await update_now_playing(radio.current_song or {})
async def refresh_all_uis():
    await update_now_playing(radio.current_song or {})
    search_id = radio.embed_manager.load_message_id("search")
    if not search_id:
        return
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return
    try:
        msg = await safe_fetch_message(channel, search_id)
        if not msg: return
        if radio.active_view_type == "history":
            limit = config.history_items_per_page
            history = await radio.db.get_full_history(
                limit=limit,
                offset=radio.last_history_page * limit,
                filter_from=radio.filter_from,
                filter_to=radio.filter_to
            )
            total_count = await radio.db.get_history_count(filter_from=radio.filter_from, filter_to=radio.filter_to)
            await msg.edit(view=HistoryView(radio, history, total_count, page=radio.last_history_page))
        elif radio.active_view_type == "search":
            results = radio.last_search_results
            query = radio.last_search_query
            user = radio.last_search_user
            existing_paths = set()
            all_playlists = []
            if radio.editing_playlist_id:
                playlist_songs = await radio.db.get_playlist_songs(radio.editing_playlist_id)
                existing_paths = {s['path'] for s in playlist_songs}
                all_playlists = await radio.db.get_all_playlists()
            await msg.edit(view=SearchResultsView(
                radio, results, query, user,
                page=radio.last_search_page,
                search_type=radio.last_search_type,
                existing_paths=existing_paths,
                all_playlists=all_playlists
            ))
        elif radio.active_view_type == "studio":
            playlists = await radio.db.get_all_playlists(radio.playlist_editor_user, strictly_personal=True)
            await msg.edit(view=PlaylistStudioView(radio, playlists=playlists))
        elif radio.active_view_type == "playlist_editor" and radio.editing_playlist_id:
            songs = await radio.db.get_playlist_songs(radio.editing_playlist_id)
            all_playlists = await radio.db.get_all_playlists(radio.playlist_editor_user, strictly_personal=True)
            await msg.edit(view=PlaylistEditorView(radio, radio.editing_playlist_id, page=radio.last_editor_page, songs=songs, all_playlists=all_playlists))
        elif radio.active_view_type == "queue":
            await msg.edit(view=FullQueueView(radio, page=radio.last_queue_page))
    except Exception as e:
        print(f"DEBUG: refresh_all_uis failed: {e}")
