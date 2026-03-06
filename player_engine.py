import asyncio
import discord
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_icons import Icons
_bot_ref = None
_config_ref = None
_radio_ref = None
_update_now_playing_fn = None
_refresh_ui_fn = None

def init_player(bot, config, radio, update_fn, refresh_fn):
    global _bot_ref, _config_ref, _radio_ref, _update_now_playing_fn, _refresh_ui_fn
    _bot_ref = bot
    _config_ref = config
    _radio_ref = radio
    _update_now_playing_fn = update_fn
    _refresh_ui_fn = refresh_fn
async def ensure_voice():
    if not _radio_ref.voice_channel_id:
        return None
    guild = _bot_ref.get_guild(_config_ref.guild_id)
    channel = guild.get_channel(_radio_ref.voice_channel_id)
    if not channel:
        print("Voice channel not found")
        return None
    if guild.voice_client:
        _radio_ref.voice = guild.voice_client
        if _radio_ref.voice.channel.id != channel.id:
            await _radio_ref.voice.move_to(channel)
    else:
        _radio_ref.voice = await channel.connect(reconnect=True)
    return _radio_ref.voice
async def radio_player():
    await _bot_ref.wait_until_ready()
    while not _bot_ref.is_closed():
        try:
            voice = await ensure_voice()
            if not voice:
                action, data = await _radio_ref.action_queue.get()
                if action == RadioAction.JOIN:
                    _radio_ref.voice_channel_id = data
                    _radio_ref.embed_manager.save_value("voice_channel_id", data)
                    _radio_ref.status = RadioStatusEnum.PLAYING
                    await _update_now_playing_fn(_radio_ref.current_song or {})
                elif action == RadioAction.ADD_TO_QUEUE:
                    # If someone wants to play a song but bot isn't in a channel, try to join them
                    user = _radio_ref.last_user
                    if user and hasattr(user, 'voice') and user.voice:
                        _radio_ref.voice_channel_id = user.voice.channel.id
                        _radio_ref.embed_manager.save_value("voice_channel_id", user.voice.channel.id)
                        _radio_ref.queue.insert(0, data)
                        _radio_ref.status = RadioStatusEnum.PLAYING
                        print(f"[SYSTEM] Auto-joining {user.display_name} in {user.voice.channel.name} to play requested song.")
                elif action == RadioAction.SET_LANGUAGE:
                    _radio_ref.language = data
                    await _refresh_ui_fn()
                    print(f"DEBUG: Language changed to: {data}")
                continue
            if _radio_ref.status == RadioStatusEnum.IDLE:
                print("[RADIO] Idle, waiting for action...")
                action, data = await _radio_ref.action_queue.get()
                if action == RadioAction.SET_GENRE:
                    _radio_ref.genre = data
                    _radio_ref.is_seeking = False
                    await _radio_ref.refresh_queue()
                elif action == RadioAction.SET_VOLUME:
                    _radio_ref.volume = data
                    continue
                elif action == RadioAction.REPLAY:
                    _radio_ref.is_seeking = True
                    _radio_ref.seek_position = 0
                elif action == RadioAction.SKIP:
                    _radio_ref.is_seeking = False
                elif action == RadioAction.JOIN:
                    _radio_ref.voice_channel_id = data
                    _radio_ref.embed_manager.save_value("voice_channel_id", data)
                elif action == RadioAction.DISCONNECT:
                    _radio_ref.voice_channel_id = None
                    _radio_ref.embed_manager.save_value("voice_channel_id", None)
                    _radio_ref.status = RadioStatusEnum.IDLE
                    guild = _bot_ref.get_guild(_config_ref.guild_id)
                    if guild and guild.voice_client:
                        await guild.voice_client.disconnect()
                    _radio_ref.voice = None
                    _radio_ref.current_song = None
                    await _update_now_playing_fn({})
                    continue
                elif action == RadioAction.SET_LANGUAGE:
                    _radio_ref.language = data
                    await _refresh_ui_fn()
                    continue
                elif action == RadioAction.ADD_TO_QUEUE:
                    _radio_ref.queue.insert(0, data)
                    _radio_ref.is_seeking = False
                else:
                    continue
                _radio_ref.status = RadioStatusEnum.PLAYING
            while _radio_ref.action_queue.qsize() > 0:
                action, data = _radio_ref.action_queue.get_nowait()
                if action == RadioAction.SET_GENRE:
                    _radio_ref.genre = data
                    _radio_ref.is_seeking = False
                    await _radio_ref.refresh_queue()
                elif action == RadioAction.SET_VOLUME:
                    _radio_ref.volume = data
                elif action == RadioAction.SKIP:
                    _radio_ref.is_seeking = False
                elif action == RadioAction.STOP:
                    _radio_ref.status = RadioStatusEnum.IDLE
                    await _radio_ref.refresh_queue()
                elif action == RadioAction.JOIN:
                    _radio_ref.voice_channel_id = data
                    _radio_ref.embed_manager.save_value("voice_channel_id", data)
                    print(f"[ACTION HANDLED] JOIN: Voice channel set to {data}")
                elif action == RadioAction.DISCONNECT:
                    _radio_ref.voice_channel_id = None
                    _radio_ref.embed_manager.save_value("voice_channel_id", None)
                    if _radio_ref.voice:
                        await _radio_ref.voice.disconnect()
                        _radio_ref.voice = None
                    await _update_now_playing_fn(_radio_ref.current_song or {})
                    print(f"[ACTION HANDLED] DISCONNECT: Voice client disconnected")
                elif action == RadioAction.SET_LANGUAGE:
                    _radio_ref.language = data
                    await _refresh_ui_fn()
                    print(f"[ACTION HANDLED] SET_LANGUAGE: Language set to {data}")
                elif action == RadioAction.ADD_TO_QUEUE:
                    _radio_ref.queue.insert(0, data)
                elif action == RadioAction.REMOVE_FROM_QUEUE:
                    if data in _radio_ref.queue:
                        _radio_ref.queue.remove(data)
                elif action == RadioAction.CLEAR_QUEUE:
                    _radio_ref.queue = []
                    await _refresh_ui_fn()
            if _radio_ref.status == RadioStatusEnum.IDLE:
                continue
            if _radio_ref.is_seeking and _radio_ref.current_song:
                song = _radio_ref.current_song
            else:
                if not _radio_ref.queue:
                    await _radio_ref.refresh_queue()
                if _radio_ref.queue:
                    song = _radio_ref.queue.pop(0)
                    if not _radio_ref.is_back_action and not _radio_ref.is_forward_action:
                        _radio_ref.last_history_paths = []
                        _radio_ref.forward_stack = []
                    _radio_ref.is_back_action = False
                    _radio_ref.is_forward_action = False
                    new_song = await _radio_ref.get_random_song_by_genre(_radio_ref.genre)
                    if new_song:
                        _radio_ref.queue.append(new_song)
                else:
                    song = None
                _radio_ref.current_song = song
            _radio_ref.is_seeking = False
            if not song:
                print("There is no track in this:", _radio_ref.genre)
                _radio_ref.status = RadioStatusEnum.IDLE
                await asyncio.sleep(_config_ref.error_retry_seconds)
                continue
            _radio_ref.status = RadioStatusEnum.PLAYING
            print("Playing:", song)
            before_opts = "-nostdin -re"
            if _radio_ref.seek_position is not None:
                before_opts += f" -ss {_radio_ref.seek_position}"
            volume_filter = f"-filter:a volume={_radio_ref.volume}"
            raw_source = discord.FFmpegOpusAudio(
                song["path"],
                executable=_config_ref.ffmpeg_path,
                before_options=before_opts,
                options=f"-vn {volume_filter}"
            )
            _radio_ref.track_start_time = asyncio.get_event_loop().time()
            _radio_ref.track_start_offset = _radio_ref.seek_position or 0.0
            _radio_ref.seek_position = None
            _radio_ref.track_duration = song.get("duration", 0)
            done = asyncio.Event()

            def after_playing(error):
                if error:
                    print("FFMPEG error:", error)
                _bot_ref.loop.call_soon_threadsafe(done.set)
            while voice.is_playing() or voice.is_paused():
                await asyncio.sleep(0.1)
            voice.play(raw_source, after=after_playing)
            while not voice.is_playing() and not voice.is_paused():
                await asyncio.sleep(0.05)
            await _update_now_playing_fn(song)
            song_duration = song.get("duration", 0)
            ten_percent_duration = int(song_duration * _config_ref.play_count_threshold_percent)
            start_time = asyncio.get_event_loop().time()
            history_saved = False
            while not done.is_set():
                if not history_saved and (asyncio.get_event_loop().time() - start_time >= _config_ref.history_save_seconds):
                    user_id = _radio_ref.last_user.id if _radio_ref.last_user else None
                    await _radio_ref.db.add_to_history(song["path"], user_id)
                    history_saved = True
                try:
                    action_task = asyncio.create_task(_radio_ref.action_queue.get())
                    done_task = asyncio.create_task(done.wait())
                    finished, pending = await asyncio.wait(
                        [action_task, done_task],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=1.0
                    )
                    for task in pending:
                        task.cancel()
                    if action_task in finished:
                        action, data = action_task.result()
                        print(f"[PROCESS] Action: {action.name}")
                        if action == RadioAction.SKIP:
                            _radio_ref.is_seeking = False
                            _radio_ref.forward_stack = []
                            _radio_ref.last_history_paths = []
                            await _radio_ref.refresh_queue()
                            voice.stop()
                            break
                        elif action == RadioAction.SEEK:
                            _radio_ref.seek_position = data
                            _radio_ref.is_seeking = True
                            voice.stop()
                            break
                        elif action == RadioAction.SET_VOLUME:
                            _radio_ref.volume = data
                            _radio_ref.is_seeking = True
                            voice.stop()
                            break
                        elif action == RadioAction.REPLAY:
                            if _radio_ref.status == RadioStatusEnum.PAUSED:
                                voice.resume()
                                _radio_ref.track_start_time = asyncio.get_event_loop().time()
                                _radio_ref.status = RadioStatusEnum.PLAYING
                                await _update_now_playing_fn(song)
                            else:
                                _radio_ref.seek_position = 0
                                _radio_ref.is_seeking = True
                                voice.stop()
                                break
                        elif action == RadioAction.PAUSE:
                            if voice.is_playing():
                                voice.pause()
                                if _radio_ref.track_start_time:
                                    _radio_ref.track_start_offset += (asyncio.get_event_loop().time() - _radio_ref.track_start_time)
                                _radio_ref.track_start_time = None
                                _radio_ref.status = RadioStatusEnum.PAUSED
                                await _update_now_playing_fn(song)
                        elif action == RadioAction.STOP:
                            _radio_ref.is_seeking = True
                            _radio_ref.seek_position = 0
                            _radio_ref.track_start_time = None
                            _radio_ref.track_start_offset = 0.0
                            _radio_ref.status = RadioStatusEnum.IDLE
                            voice.stop()
                            await _update_now_playing_fn(song)
                            break
                        elif action == RadioAction.JOIN:
                            _radio_ref.voice_channel_id = data
                            _radio_ref.embed_manager.save_value("voice_channel_id", data)
                            guild = _bot_ref.get_guild(_config_ref.guild_id)
                            channel = guild.get_channel(data)
                            if voice.channel.id != data:
                                await voice.move_to(channel)
                            await _update_now_playing_fn(song)
                        elif action == RadioAction.SET_LANGUAGE:
                            _radio_ref.language = data
                            await _refresh_ui_fn()
                        elif action == RadioAction.DISCONNECT:
                            _radio_ref.voice_channel_id = None
                            _radio_ref.embed_manager.save_value("voice_channel_id", None)
                            _radio_ref.track_start_time = None
                            _radio_ref.status = RadioStatusEnum.IDLE
                            voice.stop()
                            guild = _bot_ref.get_guild(_config_ref.guild_id)
                            if guild and guild.voice_client:
                                await guild.voice_client.disconnect()
                            _radio_ref.voice = None
                            # Clear current song to force standby UI
                            _radio_ref.current_song = None
                            await _update_now_playing_fn({})
                            break
                        elif action == RadioAction.SET_GENRE:
                            _radio_ref.genre = data
                            _radio_ref.is_seeking = False
                            await _radio_ref.refresh_queue()
                            voice.stop()
                            break
                        elif action == RadioAction.ADD_TO_QUEUE:
                            _radio_ref.queue.insert(0, data)
                            _radio_ref.is_seeking = False
                            voice.stop()
                            print(f"[PROCESS] ADD_TO_QUEUE: Instant switch to {data.get('title')}")
                            break
                        elif action == RadioAction.BACK:
                            if _radio_ref.current_song:
                                _radio_ref.forward_stack.append(_radio_ref.current_song)
                            _radio_ref.queue.insert(0, data)
                            _radio_ref.is_seeking = False
                            _radio_ref.is_back_action = True
                            voice.stop()
                            break
                        elif action == RadioAction.FORWARD:
                            _radio_ref.is_seeking = False
                            if _radio_ref.forward_stack:
                                next_song = _radio_ref.forward_stack.pop()
                                _radio_ref.queue.insert(0, next_song)
                                _radio_ref.is_forward_action = True
                                if _radio_ref.last_history_paths:
                                    _radio_ref.last_history_paths.pop()
                            else:
                                _radio_ref.is_forward_action = False
                            voice.stop()
                            break
                        elif action == RadioAction.SHUFFLE:
                            import random
                            random.shuffle(_radio_ref.queue)
                            await _update_now_playing_fn(song)
                        elif action == RadioAction.ADD_TO_QUEUE:
                            _radio_ref.queue.append(data)
                            await _update_now_playing_fn(song)
                        elif action == RadioAction.REMOVE_FROM_QUEUE:
                            if data in _radio_ref.queue:
                                _radio_ref.queue.remove(data)
                                await _update_now_playing_fn(song)
                        elif action == RadioAction.CLEAR_QUEUE:
                            _radio_ref.queue = []
                            await _update_now_playing_fn(song)
                    if done_task in finished:
                        break
                except asyncio.TimeoutError:
                    continue
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time >= ten_percent_duration:
                await _radio_ref.db.update_last_played(song["path"])
                print(f"Play count updated for: {song['path']}")
            _radio_ref.track_start_time = None
            _radio_ref.track_start_offset = 0.0
            raw_source.cleanup()
        except Exception as e:
            print("Radio loop crash:", e)
            import traceback
            traceback.print_exc()
            await asyncio.sleep(_config_ref.error_retry_seconds)
