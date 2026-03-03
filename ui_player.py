import discord
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Container, Section, TextDisplay, Thumbnail, Separator
from pathlib import Path
from ui_translate import t
from ui_icons import Icons
from ui_utils import fixed, format_duration
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

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        user_role_ids = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
        is_admin = self.radio.config.admin_role_id in user_role_ids

        if channel_id in self.radio.config.restricted_channels and not is_admin:
            required_role_id = self.radio.config.restricted_channels[channel_id]
            if required_role_id not in user_role_ids:
                await interaction.response.send_message(t("no_permission"), ephemeral=True)
                return

        self.radio.dispatch(RadioAction.JOIN, channel_id, user=interaction.user)
        await interaction.response.send_message(t("syncing"), ephemeral=True)

class LanguageSelect(discord.ui.Select):
    def __init__(self, radio):
        self.radio = radio
        options = [
            discord.SelectOption(label="English", value="en", emoji=Icons.LANG_EN),
            discord.SelectOption(label="Magyar", value="hu", emoji=Icons.LANG_HU)
        ]
        super().__init__(
            placeholder=t("placeholder_lang"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="language_select"
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.language = selected
        self.radio.dispatch(RadioAction.SET_LANGUAGE, selected, user=interaction.user)
        msg = "English language selected" if selected == "en" else "Magyar nyelv kiválasztva"
        await interaction.response.send_message(msg, ephemeral=True)

class DisconnectButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('sever_uplink') or 'Sever Uplink',
            emoji=Icons.DISCONNECT,
            style=discord.ButtonStyle.secondary,
            custom_id="disconnect_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await interaction.response.send_message(t("severing"), ephemeral=True)

class GenreSelect(discord.ui.Select):
    def __init__(self, radio, db):
        self.radio = radio
        self.db = db
        genres = db.get_all_genres()
        if "levifav" not in genres:
            genres.append("levifav")
        options = [discord.SelectOption(label=g.upper(), value=g, emoji=Icons.GENRE) for g in genres]
        super().__init__(
            placeholder=t('placeholder_genre'),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="genre_select"
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.dispatch(RadioAction.SET_GENRE, selected, user=interaction.user)
        await interaction.response.send_message(f"{t('switching_genre')} **{selected.upper()}**", ephemeral=True)

class PlayButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('play_label') or 'Play',
            emoji=Icons.PLAY,
            style=discord.ButtonStyle.secondary,
            custom_id="play_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
        await interaction.response.send_message(t("resuming"), ephemeral=True)

class PauseButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('pause_label'),
            emoji=Icons.PAUSE,
            style=discord.ButtonStyle.secondary,
            custom_id="pause_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.status == RadioStatusEnum.IDLE:
            await interaction.response.send_message(t("cannot_pause_stopped"), ephemeral=True)
            return

        if self.radio.status == RadioStatusEnum.PAUSED:
            self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
            await interaction.response.send_message(t("resuming_feedback"), ephemeral=True)
        else:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await interaction.response.send_message(t("pausing"), ephemeral=True)

class StopButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('stop_label'),
            emoji=Icons.STOP,
            style=discord.ButtonStyle.secondary,
            custom_id="stop_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.STOP, user=interaction.user)
        await interaction.response.send_message(t("stopping"), ephemeral=True)

class ForwardButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('forward_label'),
            emoji=Icons.FORWARD,
            style=discord.ButtonStyle.secondary,
            custom_id="forward_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.FORWARD, user=interaction.user)
            await interaction.response.send_message(t("forwarding"), ephemeral=True)
        else:
            await interaction.response.send_message(t("nothing_playing"), ephemeral=True)

class RandomButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('random_label'),
            emoji=Icons.RANDOM,
            style=discord.ButtonStyle.secondary,
            custom_id="random_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.SKIP, user=interaction.user)
            await interaction.response.send_message(t("randomizing"), ephemeral=True)
        else:
            await interaction.response.send_message(t("nothing_playing"), ephemeral=True)

class ShuffleButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('shuffle_label'),
            emoji=Icons.SHUFFLE,
            style=discord.ButtonStyle.secondary,
            custom_id="shuffle_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.SHUFFLE, user=interaction.user)
        await interaction.response.send_message(t("shuffle_feedback"), ephemeral=True)

class BackButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=t('back_label'),
            emoji=Icons.BACK_STEP,
            style=discord.ButtonStyle.secondary,
            custom_id="back_button"
        )
        self.radio = radio
        self.db = db

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
        prev_song = self.db.get_previous_song(self.radio.last_history_paths)
        if prev_song:
            self.radio.dispatch(RadioAction.BACK, prev_song, user=interaction.user)
            await interaction.response.send_message(f"{Icons.BACK_STEP} {t('jumping')} **{prev_song.get('artist')} - {prev_song.get('title')}**", ephemeral=True)
        else:
            await interaction.response.send_message(t("back_error"), ephemeral=True)

class SeekButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('seek_label'),
            emoji=Icons.SEEK,
            style=discord.ButtonStyle.secondary,
            custom_id="seek_button"
        )
        self.radio = radio

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
        await interaction.response.send_message(f"{t('jumping')} {ts}...", ephemeral=True)

class VolumeButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('vol_label'),
            emoji=Icons.VOLUME,
            style=discord.ButtonStyle.secondary,
            custom_id="volume_button"
        )
        self.radio = radio

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
        await interaction.response.send_message(f"{t('vol_set')} {value}%", ephemeral=True)

class LikeButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=t('like_label'),
            emoji=Icons.LIKE,
            style=discord.ButtonStyle.secondary,
            custom_id="like_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_playing_error"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        song_path = self.radio.current_song.get("path")
        try:
            status = self.db.toggle_rating(interaction.user.id, song_path, 'like')
            updated_song = self.db.get_song_by_path(song_path)
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
        except Exception as e:
            print(f"Like error: {e}")
            await interaction.followup.send(t("record_error"), ephemeral=True)

class DislikeButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=t('dislike_label'),
            emoji=Icons.DISLIKE,
            style=discord.ButtonStyle.secondary,
            custom_id="dislike_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_playing_error"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        song_path = self.radio.current_song.get("path")
        try:
            status = self.db.toggle_rating(interaction.user.id, song_path, 'dislike')
            updated_song = self.db.get_song_by_path(song_path)
            if updated_song:
                self.radio.last_user = interaction.user
                self.radio.current_song = updated_song
                if _update_callback: await _update_callback(updated_song)
            artist = updated_song.get("artist") or "Unknown Artist"
            title = updated_song.get("title") or "Unknown Title"
            if status == "added": msg = f"{t('disliked')} **{artist} - {title}**"
            elif status == "removed": msg = f"{t('dislike_withdrawn')} **{artist} - {title}**"
            else: msg = f"{t('disliked_replaced')} **{artist} - {title}**"
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            print(f"Dislike error: {e}")
            await interaction.followup.send(t("record_error"), ephemeral=True)

class DetailsButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('details_btn_label'),
            emoji=Icons.INFO,
            style=discord.ButtonStyle.secondary,
            custom_id="details_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.show_details = not self.radio.show_details
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.followup.send(
            f"{Icons.INFO} {t('info_visibility')}: **{t('shown') if self.radio.show_details else t('hidden')}**",
            ephemeral=True
        )

class QueueToggleButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('queue_label'),
            emoji=Icons.QUEUE,
            style=discord.ButtonStyle.secondary,
            custom_id="queue_toggle"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.show_queue = not self.radio.show_queue
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.followup.send(
            f"{Icons.QUEUE} {t('queue_visibility')}: **{t('shown') if self.radio.show_queue else t('hidden')}**",
            ephemeral=True
        )

class UnifiedStandbyView(LayoutView):
    def __init__(self, radio):
        super().__init__(timeout=None)
        self.radio = radio

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
            station_container.add_item(Separator())
            
            row_studio = ActionRow()
            from ui_studio import PlaylistStudioButton
            row_studio.add_item(PlaylistStudioButton(radio))
            station_container.add_item(row_studio)
        self.add_item(station_container)

        standby_container = Container(accent_color=Theme.BACKGROUND)
        standby_container.add_item(TextDisplay(f"**{t('standby_mode')}**\n{t('standby_subtitle')}"))
        self.add_item(standby_container)

class FrequencyStationView(LayoutView):
    def __init__(self, radio):
        super().__init__(timeout=None)
        self.radio = radio

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
            
            station_container.add_item(Separator())
            row_meta = ActionRow()
            row_meta.add_item(DisconnectButton(radio))
            station_container.add_item(row_meta)
        
        self.add_item(station_container)

class NowPlayingView(LayoutView):
    def __init__(self, radio, db, song=None, cover_path=None):
        super().__init__(timeout=None)
        song = song or radio.current_song or {}

        accent_color = Theme.PLAYING
        status_key = "now_playing"
        status_emoji = Icons.HEADPHONES
        if radio.status == RadioStatusEnum.PAUSED:
            status_key = "paused"
            status_emoji = Icons.PAUSE
            accent_color = Theme.PAUSED
        elif radio.status == RadioStatusEnum.IDLE:
            status_key = "idle"
            status_emoji = Icons.STOP
            accent_color = Theme.IDLE
        status_title = f"{status_emoji} {t(status_key)}"

        master_container = Container(accent_color=accent_color)
        
        # We use the explicitly passed cover_path if available
        if cover_path is None:
            cover_path = db.get_song_cover_path(song.get("path", ""))
            
        thumb = None
        if cover_path and Path(cover_path).exists():
            thumb = Thumbnail(f"attachment://cover.png")

        truncated_artist = fixed(song.get('artist', 'Unknown'), 36).strip()
        truncated_title  = fixed(song.get('title', 'Unknown'), 36).strip()
        truncated_album  = fixed(song.get('album', 'Unknown'), 36).strip()
        channel_mention = f"<#{radio.voice_channel_id}>"

        info_lines = [
            f"**{status_title}**",
            f"**{t('artist')}:** {truncated_artist}",
            f"**{t('title')}:** {truncated_title}",
            f"**{t('album')}:** {truncated_album}",
            f"**{t('genre')}:** {song.get('genre', 'Unknown').upper()}",
            f"**{t('duration')}:** {format_duration(song.get('duration', 0))}",
            f"**{t('likes')}:** {song.get('likes', 0)} | **{t('dislikes')}:** {song.get('dislikes', 0)}"
        ]

        if radio.show_details:
            info_lines.append(f"\n**{Icons.INFO} {t('details_label')}**")
            info_lines.append(f"**{t('year')}:** {song.get('date', 'Unknown')}")
            info_lines.append(f"**{t('label')}:** {song.get('label', 'Unknown')}")
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

        genre_row = ActionRow()
        genre_row.add_item(GenreSelect(radio, db))
        master_container.add_item(genre_row)

        playback_row = ActionRow()
        playback_row.add_item(BackButton(radio, db))
        playback_row.add_item(PlayButton(radio))
        playback_row.add_item(PauseButton(radio))
        playback_row.add_item(StopButton(radio))
        playback_row.add_item(ForwardButton(radio))
        master_container.add_item(playback_row)

        meta_row_1 = ActionRow()
        meta_row_1.add_item(RandomButton(radio))
        meta_row_1.add_item(ShuffleButton(radio))
        meta_row_1.add_item(SeekButton(radio))
        meta_row_1.add_item(LikeButton(radio, db))
        meta_row_1.add_item(DislikeButton(radio, db))
        master_container.add_item(meta_row_1)

        meta_row_2 = ActionRow()
        meta_row_2.add_item(DetailsButton(radio))
        meta_row_2.add_item(QueueToggleButton(radio))
        
        from ui_search import SearchButton
        from ui_studio import PlaylistViewButton, HistoryButton
        
        meta_row_2.add_item(SearchButton(radio, db))
        meta_row_2.add_item(PlaylistViewButton(radio, db))
        meta_row_2.add_item(HistoryButton(radio, db))
        master_container.add_item(meta_row_2)

        tools_row = ActionRow()
        tools_row.add_item(VolumeButton(radio))
        if radio.show_queue:
            from ui_search import QueueViewButton
            tools_row.add_item(QueueViewButton(radio))
        master_container.add_item(tools_row)

        self.add_item(master_container)
