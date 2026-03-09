import discord
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Container, Section, TextDisplay, Thumbnail, Separator
from pathlib import Path
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, BaseView
from ui_utils import fixed, format_duration, get_dominant_color
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_theme import Theme
_update_callback = None
_bot_ref = None
_config_ref = None

def init_player_ui(bot, config, update_fn):
    global _bot_ref, _config_ref, _update_callback
    _bot_ref = bot
    _config_ref = config
    _update_callback = update_fn

class StationSelect(discord.ui.Select):

    def __init__(self, radio, channels):
        self.radio = radio
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                emoji=Icons.UPLINK
            ) for c in channels
        ]
        super().__init__(
            placeholder=t("placeholder_freq"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="station_select"
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        is_admin = self.radio.is_admin(interaction.user)
        if channel_id in self.radio.config.restricted_channels and not is_admin:
            required_role_id = self.radio.config.restricted_channels[channel_id]
            user_role_ids = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            if required_role_id not in user_role_ids:
                await interaction.response.send_message(t("no_permission"), ephemeral=True)
                return
        self.radio.dispatch(RadioAction.JOIN, channel_id, user=interaction.user)
        await interaction.response.defer()

class LanguageSelect(discord.ui.Select):

    def __init__(self, radio):
        self.radio = radio
        options = [
            discord.SelectOption(
                label=lang["label"], 
                value=lang["code"], 
                emoji=lang.get("emoji")
            ) for lang in radio.config.languages
        ]
        super().__init__(
            placeholder=t("placeholder_lang"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="language_select"
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.language = selected
        self.radio.dispatch(RadioAction.SET_LANGUAGE, selected, user=interaction.user)
        selected_lang = next((l for l in self.radio.config.languages if l["code"] == selected), None)
        label = selected_lang["label"] if selected_lang else selected
        await interaction.response.defer(ephemeral=True)
        try: await interaction.delete_original_response()
        except: pass

class UIModeSelect(discord.ui.Select):

    def __init__(self, radio):
        self.radio = radio
        options = [
            discord.SelectOption(label=t("ui_mode_full"), value="full"),
            discord.SelectOption(label=t("ui_mode_compact"), value="compact")
        ]
        super().__init__(
            placeholder=t("placeholder_ui"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ui_mode_select"
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.is_compact = (selected == "compact")
        await interaction.response.defer(ephemeral=True)
        try: await interaction.delete_original_response()
        except: pass
        if _update_callback:
            await _update_callback(self.radio.current_song or {})

class DisconnectButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=t('sever_uplink') or 'Sever Uplink',
            emoji=Icons.DISCONNECT,
            style=discord.ButtonStyle.secondary,
            custom_id="disconnect_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await interaction.response.defer()

class GenreSelect(discord.ui.Select):

    def __init__(self, radio, genres):
        self.radio = radio
        self.db = radio.db
        limited_genres = genres[:25]
        if len(genres) > 25:
            print(f"[UI] Warning: Too many genres ({len(genres)}), capping to 25 for select menu.")
        options = [discord.SelectOption(label=g.upper(), value=g, emoji=Icons.GENRE) for g in limited_genres]
        super().__init__(
            placeholder=t('placeholder_genre'),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="genre_select"
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.dispatch(RadioAction.SET_GENRE, selected, user=interaction.user)
        await interaction.response.defer()

class FallbackModeButton(discord.ui.Button):

    def __init__(self, radio):
        label = t("online_mode_off") if not radio.is_fallback_mode else t("online_mode_on")
        style = discord.ButtonStyle.secondary if not radio.is_fallback_mode else discord.ButtonStyle.primary
        super().__init__(
            label=label,
            emoji=Icons.GLOBE,
            style=style,
            custom_id="toggle_fallback_mode"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.is_fallback_mode = not self.radio.is_fallback_mode
        self.radio.is_auto_mode = not self.radio.is_fallback_mode
        if self.radio.is_fallback_mode:
            self.radio.status = RadioStatusEnum.IDLE
            self.radio.queue = []
            self.radio.current_song = None
        
        await interaction.response.defer(ephemeral=True)
        try: await interaction.delete_original_response()
        except: pass
        if _update_callback: await _update_callback(self.radio.current_song or {})

class PlayPauseButton(discord.ui.Button):

    def __init__(self, radio):
        is_paused = radio.status in [RadioStatusEnum.PAUSED, RadioStatusEnum.STOPPED, RadioStatusEnum.IDLE]
        label = None if radio.is_compact else (t('play_label') if is_paused else t('pause_label'))
        emoji = Icons.PLAY if is_paused else Icons.PAUSE
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id="play_pause_toggle"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.status in [RadioStatusEnum.PAUSED, RadioStatusEnum.STOPPED, RadioStatusEnum.IDLE]:
            self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
        else:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)
        await interaction.response.defer()

class StopButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('stop_label'),
            emoji=Icons.STOP,
            style=discord.ButtonStyle.secondary,
            custom_id="stop_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.STOP, user=interaction.user)
        await interaction.response.defer()

class ForwardButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('forward_label'),
            emoji=Icons.FORWARD,
            style=discord.ButtonStyle.secondary,
            custom_id="forward_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.FORWARD, user=interaction.user)
            await interaction.response.defer()
        else:
            await interaction.response.send_message(t("nothing_playing"), ephemeral=True)

class RandomButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('random_label'),
            emoji=Icons.RANDOM,
            style=discord.ButtonStyle.secondary,
            custom_id="random_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.SKIP, user=interaction.user)
            await interaction.response.defer()
        else:
            await interaction.response.send_message(t("nothing_playing"), ephemeral=True)

class ShuffleButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('shuffle_label'),
            emoji=Icons.SHUFFLE,
            style=discord.ButtonStyle.secondary,
            custom_id="shuffle_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.SHUFFLE, user=interaction.user)
        await interaction.response.defer()

class BackButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('back_label'),
            emoji=Icons.BACK_STEP,
            style=discord.ButtonStyle.secondary,
            custom_id="back_button"
        )
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        import time
        now = time.time()
        if now - self.radio.last_back_time < 2.0:
            await interaction.response.send_message(t("cooldown_error"), ephemeral=True)
            return
        self.radio.last_back_time = now
        if self.radio.current_song:
            current_path = self.radio.current_song.get("path")
            if current_path not in self.radio.last_history_paths:
                self.radio.last_history_paths.append(current_path)
        prev_song = await self.db.get_previous_song(self.radio.last_history_paths)
        if prev_song:
            self.radio.dispatch(RadioAction.BACK, prev_song, user=interaction.user)
            await interaction.response.defer()
        else:
            await interaction.response.send_message(t("back_error"), ephemeral=True)

class SeekButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('seek_label'),
            emoji=Icons.SEEK,
            style=discord.ButtonStyle.secondary,
            custom_id="seek_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.status == RadioStatusEnum.IDLE:
            await interaction.response.send_message(t("cannot_seek_stopped"), ephemeral=True)
            return
        modal = SeekModal(self.radio)
        await interaction.response.send_modal(modal)

class SeekModal(Modal):

    def __init__(self, radio):
        super().__init__(title=t("jump_modal_title"))
        self.radio = radio
        self.timestamp_input = TextInput(
            label=t("timestamp_input_label"),
            placeholder="01:30",
            style=discord.TextStyle.short,
            required=True,
            max_length=5
        )
        self.add_item(self.timestamp_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        ts = self.timestamp_input.value
        try:
            minutes, seconds = map(int, ts.split(":"))
            total_seconds = minutes * 60 + seconds
        except:
            await interaction.response.send_message(t("format_error"), ephemeral=True)
            return
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_current_track"), ephemeral=True)
            return
        if total_seconds >= self.radio.current_song.get("duration", 0):
            await interaction.response.send_message(t("too_long"), ephemeral=True)
            return
        self.radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        await interaction.response.defer()

class VolumeButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('vol_label'),
            emoji=Icons.VOLUME,
            style=discord.ButtonStyle.secondary,
            custom_id="volume_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        modal = VolumeModal(self.radio)
        await interaction.response.send_modal(modal)

class VolumeModal(Modal):

    def __init__(self, radio):
        super().__init__(title=t("vol_modal_title"))
        self.radio = radio
        self.volume_input = TextInput(
            label=t("vol_input_label"),
            placeholder="15",
            style=discord.TextStyle.short,
            required=True,
            max_length=3
        )
        self.add_item(self.volume_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.volume_input.value)
        except ValueError:
            await interaction.response.send_message(t("invalid_number"), ephemeral=True)
            return
        if value < 0 or value > 100:
            await interaction.response.send_message(t("vol_range_error"), ephemeral=True)
            return
        self.radio.dispatch(RadioAction.SET_VOLUME, value / 100, user=interaction.user)
        await interaction.response.defer()

class LikeButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('like_label'),
            emoji=Icons.LIKE,
            style=discord.ButtonStyle.secondary,
            custom_id="like_button"
        )
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_playing_error"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        song_path = self.radio.current_song.get("path")
        status = await self.db.toggle_rating(interaction.user.id, song_path, 'like')
        updated_song = await self.db.get_song_by_path(song_path)
        if updated_song:
            self.radio.last_user = interaction.user
            self.radio.current_song = updated_song
            if _update_callback: await _update_callback(updated_song)
        artist = updated_song.get("artist") or "Unknown Artist"
        title = updated_song.get("title") or "Unknown Title"
        if status == "added": msg = f"{t('liked')} **{artist} - {title}**"
        elif status == "removed": msg = f"{t('like_withdrawn')} **{artist} - {title}**"
        else: msg = f"{t('liked_replaced')} **{artist} - {title}**"
        await interaction.followup.send(msg, ephemeral=True)

class DislikeButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('dislike_label'),
            emoji=Icons.DISLIKE,
            style=discord.ButtonStyle.secondary,
            custom_id="dislike_button"
        )
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_playing_error"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        song_path = self.radio.current_song.get("path")
        status = await self.db.toggle_rating(interaction.user.id, song_path, 'dislike')
        updated_song = await self.db.get_song_by_path(song_path)
        if updated_song:
            self.radio.last_user = interaction.user
            self.radio.current_song = updated_song
            if _update_callback: await _update_callback(updated_song)
        artist = updated_song.get("artist") or "Unknown Artist"
        title = updated_song.get("title") or "Unknown Title"
        try: await interaction.delete_original_response()
        except: pass

class FavoriteButton(discord.ui.Button):
    def __init__(self, radio, is_favorited=False):
        emoji = Icons.HEART_MINUS if is_favorited else Icons.HEART_PLUS
        label = None
        if not radio.is_compact:
            label = t("fav_rem_label") if is_favorited else t("fav_add_label")
            
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id="favorite_toggle"
        )
        self.radio = radio
        self.is_favorited = is_favorited

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_playing_error"), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        song_path = self.radio.current_song.get("path")
        status = await self.radio.db.toggle_favorite(interaction.user.id, interaction.user.display_name, song_path)
        
        song = self.radio.current_song
        artist = song.get("artist") or "Unknown Artist"
        title = song.get("title") or "Unknown Title"
        
        if status == "added":
            msg = f"{t('added_to_favs')} **{artist} - {title}**"
        else:
            msg = f"{t('removed_from_favs')} **{artist} - {title}**"
            
        if _update_callback:
            await _update_callback(self.radio.current_song)
            
        await interaction.followup.send(msg, ephemeral=True)

class DetailsButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('details_btn_label'),
            emoji=Icons.INFO,
            style=discord.ButtonStyle.secondary,
            custom_id="details_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.show_details = not self.radio.show_details
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.response.defer()

class QueueToggleButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('queue_label'),
            emoji=Icons.QUEUE,
            style=discord.ButtonStyle.secondary,
            custom_id="queue_toggle"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.show_queue = not self.radio.show_queue
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.response.defer()

class UnifiedStandbyView(BaseView):

    def __init__(self, radio):
        super().__init__(radio)
        station_container = Container(accent_color=Theme.BACKGROUND)
        station_container.add_item(TextDisplay(f"**{t('system_sync')}**\n{t('synchro_subtitle')}"))
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if guild:
            afk_id = _config_ref.afk_channel_id
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row = ActionRow()
            row.add_item(StationSelect(radio, v_channels))
            station_container.add_item(row)
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio))
            station_container.add_item(row_lang)
            row_ui = ActionRow()
            row_ui.add_item(UIModeSelect(radio))
            station_container.add_item(row_ui)
            station_container.add_item(Separator())
            from ui_studio import PlaylistStudioButton, RescanLibraryButton, PathUpdateButton, AddGenreButton
            from ui_feedback import FeedbackButton
            
            row_main = ActionRow()
            if not radio.is_fallback_mode:
                row_main.add_item(PlaylistStudioButton(radio))
            row_main.add_item(FeedbackButton(radio))
            row_main.add_item(FallbackModeButton(radio))
            station_container.add_item(row_main)
            
            if not radio.is_fallback_mode:
                row_admin = ActionRow()
                row_admin.add_item(RescanLibraryButton(radio))
                row_admin.add_item(AddGenreButton(radio))
                row_admin.add_item(PathUpdateButton(radio))
                station_container.add_item(row_admin)
        self.add_item(station_container)
        standby_container = Container(accent_color=Theme.BACKGROUND)
        standby_container.add_item(TextDisplay(f"**{t('standby_mode')}**\n{t('standby_subtitle')}"))
        self.add_item(standby_container)

class FrequencyStationView(BaseView):

    def __init__(self, radio):
        super().__init__(radio)
        station_container = Container(accent_color=Theme.BACKGROUND)
        station_container.add_item(TextDisplay(f"**{t('system_sync')}**\n{t('synchro_subtitle')}"))
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if guild:
            afk_id = _config_ref.afk_channel_id
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row = ActionRow()
            row.add_item(StationSelect(radio, v_channels))
            station_container.add_item(row)
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio))
            station_container.add_item(row_lang)
            row_ui = ActionRow()
            row_ui.add_item(UIModeSelect(radio))
            station_container.add_item(row_ui)
            station_container.add_item(Separator())
            row_meta = ActionRow()
            from ui_feedback import FeedbackButton
            from ui_studio import PlaylistStudioButton
            from ui_search import WebLinkButton
            row_meta.add_item(DisconnectButton(radio))
            if not radio.is_fallback_mode:
                row_meta.add_item(PlaylistStudioButton(radio))
            row_meta.add_item(FeedbackButton(radio))
            station_container.add_item(row_meta)
        self.add_item(station_container)

class NowPlayingView(BaseView):

    def __init__(self, radio, genres=None, song=None, cover_path=None, is_favorited=False):
        super().__init__(radio)
        db = radio.db
        genres = genres or []
        song = song or radio.current_song or {}
        self.is_favorited = is_favorited
        accent_color = Theme.PLAYING
        status_key = "now_playing"
        status_emoji = Icons.HEADPHONES
        if radio.status == RadioStatusEnum.PAUSED:
            status_key = "paused"
            status_emoji = Icons.PAUSE
            accent_color = Theme.PAUSED
        elif radio.status == RadioStatusEnum.STOPPED:
            status_key = "stopped"
            status_emoji = Icons.STOP
            accent_color = Theme.IDLE
        elif radio.status == RadioStatusEnum.IDLE:
            status_key = "idle"
            status_emoji = Icons.STANDBY # Use standby icon for pure idle if ever shown
            accent_color = Theme.BACKGROUND
        
        if cover_path:
            dominant = get_dominant_color(cover_path)
            if dominant:
                accent_color = dominant

        channel_mention = f"<#{radio.voice_channel_id}>" if radio.voice_channel_id else "???"
        master_container = Container(accent_color=accent_color)

        thumb = None
        if cover_path:
            thumb = Thumbnail("attachment://cover.png")
        elif song.get("thumbnail_url"):
            thumb = Thumbnail(song["thumbnail_url"])
            
        elapsed = int(radio.track_start_offset)
        if radio.track_start_time and radio.status == RadioStatusEnum.PLAYING:
            import asyncio
            elapsed += int(asyncio.get_event_loop().time() - radio.track_start_time)
        duration = song.get('duration', 0)
        elapsed = min(elapsed, duration)
        
        status_title = f"{status_emoji} {t(status_key).upper()}"
        if radio.is_fallback_mode and not song:
            status_title = t("online_mode_title")
            truncated_artist = "---"
            truncated_title = t("online_mode_subtitle")
            truncated_album = "OFFLINE"
        else:
            truncated_artist = fixed(song.get('artist', 'Unknown'), 32).strip()
            truncated_title = fixed(song.get('title', 'Unknown'), 32).strip()
            truncated_album = fixed(song.get('album', 'Unknown'), 32).strip()
        is_external = song.get('is_external', False) or radio.is_fallback_mode

        def create_progress_bar(current, total, width=18):
            if total <= 0:
                return f"{Icons.PB_START}{str(Icons.PB_EMPTY) * (width-2)}{Icons.PB_RIGHT}"
            
            progress = min(1.0, max(0.0, current / total))
            filled_count = int(progress * (width - 1))
            
            parts = []
            for i in range(width):
                if i == 0:
                    parts.append(Icons.PB_START if filled_count == 0 else Icons.PB_LEFT)
                elif i == width - 1:
                    parts.append(Icons.PB_END if progress >= 1.0 else Icons.PB_RIGHT)
                elif i == filled_count:
                    parts.append(Icons.PB_KNOB)
                elif i < filled_count:
                    parts.append(Icons.PB_FULL)
                else:
                    parts.append(Icons.PB_EMPTY)
            
            return "".join(map(str, parts))

        time_readout = f"`{format_duration(elapsed)} / {format_duration(duration)}`"
        progress_bar = create_progress_bar(elapsed, duration)

        info_lines = [
            f"**{status_title}**",
            f"**{t('artist') if not is_external else t('uploader')}:** {truncated_artist}",
            f"**{t('title')}:** {truncated_title}",
            f"**{t('album') if not is_external else t('platform')}:** {truncated_album}"
        ]
        
        if not is_external and not radio.is_fallback_mode:
            info_lines.append(f"**{t('genre')}:** {song.get('genre', 'Unknown').upper()}")
            info_lines.append(f"**{t('likes')}:** {song.get('likes', 0)} | **{t('dislikes')}:** {song.get('dislikes', 0)}")
        elif radio.is_fallback_mode and not song:
            pass # Skip extra info lines in empty online mode
            
        if song or not radio.is_fallback_mode:
            info_lines.extend([
                f"\n{time_readout}\n",
                f"{progress_bar}"
            ])
        if radio.show_details:
            info_lines.append(f"\n**{Icons.INFO} {t('details_label')}**")
            info_lines.append(f"**{t('year')}:** {song.get('date', 'Unknown')}")
            info_lines.append(f"**{t('label')}:** {song.get('label', 'Unknown')}")
            if not is_external:
                info_lines.append(f"**{t('catnum')}:** {song.get('catnum', 'Unknown') or 'Unknown'}")
                info_lines.append(f"**{t('source')}:** {song.get('mediatype_flac') or song.get('mediatype_mp3') or 'Unknown'}")
            info_lines.append(f"**{t('play_count_label')}:** {song.get('play_count', 0)}")
            last_played = song.get('last_played')
            if last_played:
                info_lines.append(f"**{t('last_played_label')}:** {str(last_played)[:16].replace('-', '.')}")
            else:
                info_lines.append(f"**{t('last_played_label')}:** ---")
        if radio.show_queue:
            info_lines.append(f"\n**{Icons.QUEUE} {t('up_next')}**")
            q_list = []
            display_queue = radio.get_display_queue()
            for i, q_song in enumerate(display_queue[:radio.config.player_upcoming_limit], 1):
                q_artist = fixed(q_song.get('artist', 'Unknown'), 22).strip()
                q_title = fixed(q_song.get('title', 'Unknown'), 22).strip()
                q_list.append(f"{i}. {q_artist} - {q_title}")
            info_lines.append("\n".join(q_list) if q_list else f"*{t('empty')}*")
        if radio.last_user:
            info_lines.append(f"\n{t('tuned_by')}: {radio.last_user.mention} @ {channel_mention}")
        else:
            info_lines.append(f"\n{t('location')}: {channel_mention}")
        info_text = "\n".join(info_lines)
        if thumb:
            master_container.add_item(Section(info_text, accessory=thumb))
        else:
            master_container.add_item(TextDisplay(info_text))
        if not radio.is_fallback_mode:
            master_container.add_item(Separator())
            genre_row = ActionRow()
            genre_row.add_item(GenreSelect(radio, genres))
            master_container.add_item(genre_row)
        master_container.add_item(Separator())
        
        from ui_search import LibraryButton, SearchButton, QueueViewButton, WebLinkButton
        from ui_studio import StatsButton, HistoryButton
        
        all_buttons = [
            BackButton(radio), PlayPauseButton(radio), StopButton(radio),
            ForwardButton(radio)
        ]
        
        if not radio.is_fallback_mode:
            all_buttons.append(RandomButton(radio))
            all_buttons.append(ShuffleButton(radio))
            
        all_buttons.extend([
            SeekButton(radio), VolumeButton(radio)
        ])
        
        if not is_external:
            all_buttons.append(DetailsButton(radio))
            
        all_buttons.append(QueueToggleButton(radio))
        
        if not is_external:
            all_buttons.extend([
                LikeButton(radio), DislikeButton(radio), 
                FavoriteButton(radio, is_favorited=self.is_favorited)
            ])
            
        if not radio.is_fallback_mode:
            all_buttons.extend([
                LibraryButton(radio), SearchButton(radio),
                QueueViewButton(radio), WebLinkButton(radio),
                StatsButton(radio), HistoryButton(radio)
            ])
        else:
            all_buttons.append(WebLinkButton(radio))
            all_buttons.append(QueueViewButton(radio))
        
        # 2. Chunk into rows of 5
        for i in range(0, len(all_buttons), 5):
            chunk = all_buttons[i : i + 5]
            row = ActionRow()
            for btn in chunk:
                row.add_item(btn)
            master_container.add_item(row)
            
        self.add_item(master_container)
