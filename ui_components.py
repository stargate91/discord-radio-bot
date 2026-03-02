import discord
from discord.ui import Modal, TextInput
from pathlib import Path
from ui_translate import t
from ui_utils import fixed
from radio_actions import RadioAction, RadioState as RadioStatusEnum

_update_callback = None

def init_components(update_fn):
    global _update_callback
    _update_callback = update_fn

class StationSelect(discord.ui.Select):
    def __init__(self, radio, channels):
        self.radio = radio
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                emoji="📡"
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
        
        restricted_channels = {
            1442881688043524228: 1423540338374479914,
            1455966091950952582: 1455966276982669332
        }

        if channel_id in restricted_channels:
            required_role_id = restricted_channels[channel_id]
            user_roles = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
            
            if required_role_id not in user_roles:
                await interaction.response.send_message(t("no_permission"), ephemeral=True)
                return

        self.radio.dispatch(RadioAction.JOIN, channel_id, user=interaction.user)
        await interaction.response.send_message(t("syncing"), ephemeral=True)

class LanguageSelect(discord.ui.Select):
    def __init__(self, radio):
        self.radio = radio
        options = [
            discord.SelectOption(label="English", value="en", emoji="🇺🇸"),
            discord.SelectOption(label="Magyar", value="hu", emoji="🇭🇺")
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
            label=f"🌌 {t('sever_uplink') or 'Sever Uplink'}",
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
        options = [discord.SelectOption(label=g.upper(), value=g) for g in genres]
        super().__init__(
            placeholder=f"🎼 {t('placeholder_genre')}",
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
            label=f"▶ {t('play_label') or 'Play'}",
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
            label=f"⏸ {t('pause_label')}",
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
            label=f"⏹ {t('stop_label')}",
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
            label=f"⏭ {t('forward_label')}",
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
            label=f"🔀 {t('random_label')}",
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

class BackButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=f"⏮ {t('back_label')}",
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
            await interaction.response.send_message(f"⏮ {t('jumping')} **{prev_song.get('artist')} - {prev_song.get('title')}**", ephemeral=True)
        else:
            await interaction.response.send_message(t("back_error"), ephemeral=True)

class SeekButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=f"⏩ {t('seek_label')}",
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
            label=f"🔊 {t('vol_label')}",
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
            label=f"❤️ {t('like_label')}",
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
            label=f"👎 {t('dislike_label')}",
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
            label=f"📂 {t('details_btn_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="details_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.show_details = not self.radio.show_details
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.followup.send(
            f"📂 {t('info_visibility')}: **{t('shown') if self.radio.show_details else t('hidden')}**",
            ephemeral=True
        )

class QueueToggleButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=f"📋 {t('queue_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="queue_toggle"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.show_queue = not self.radio.show_queue
        if _update_callback: await _update_callback(self.radio.current_song)
        await interaction.followup.send(
            f"📋 {t('queue_visibility')}: **{t('shown') if self.radio.show_queue else t('hidden')}**",
            ephemeral=True
        )

class SearchButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=f"🔍 {t('search_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="search_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        modal = SearchModal(self.radio, self.db)
        await interaction.response.send_modal(modal)

class HistoryButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=f"📜 {t('history_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="history_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        from ui_views import HistoryView
        from ui import embed_state
        
        await interaction.response.defer()
        
        history = self.db.get_full_history(limit=10, offset=0)
        total_count = self.db.get_history_count()
        
        self.radio.active_view_type = "history"
        self.radio.last_history_page = 0
        self.radio.filter_from = None
        self.radio.filter_to = None
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        
        search_id = embed_state.load_message_id("search")
        if search_id:
            try:
                channel = interaction.channel
                msg = await channel.fetch_message(search_id)
                await msg.delete()
            except: pass
            
        msg = await interaction.followup.send(view=view, ephemeral=False, wait=True)
        embed_state.save_message_id("search", msg.id)

class SearchModal(Modal):
    def __init__(self, radio, db):
        super().__init__(title=t("search_modal_title"))
        self.radio = radio
        self.db = db
        self.query_input = TextInput(
            label=t("search_input_label"),
            placeholder="Search...",
            style=discord.TextStyle.short,
            required=True,
            min_length=2
        )
        self.add_item(self.query_input)

    async def on_submit(self, interaction: discord.Interaction):
        from ui_views import SearchResultsView
        from ui import embed_state, init_translate
        
        init_translate(self.radio)
        
        await interaction.response.defer(ephemeral=True)
        
        query = self.query_input.value
        results = self.db.search_songs(query)
        
        if not results:
            await interaction.followup.send(f"{t('search_no_results')} `{query}`", ephemeral=True)
            return

        old_id = embed_state.load_message_id("search")
        if old_id:
            try:
                msg = await interaction.channel.fetch_message(old_id)
                await msg.delete()
            except: pass

        self.radio.last_search_query = query
        self.radio.last_search_results = results
        self.radio.last_search_user = interaction.user

        self.radio.active_view_type = "search"
        view = SearchResultsView(self.radio, self.db, results, query, interaction.user)
        msg = await interaction.channel.send(view=view)
        embed_state.save_message_id("search", msg.id)
        
        await interaction.followup.send("Search results posted.", ephemeral=True)

class AddSongButton(discord.ui.Button):
    def __init__(self, radio, song):
        import random
        import string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(
            emoji="➕",
            style=discord.ButtonStyle.secondary,
            custom_id=f"add_song_{song['id']}_{unique}"
        )
        self.radio = radio
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.dispatch(RadioAction.ADD_TO_QUEUE, self.song, user=interaction.user)
        await interaction.followup.send(
            f"{t('add_to_queue')} **{self.song['artist']} - {self.song['title']}**",
            ephemeral=True
        )

class TabButton(discord.ui.Button):
    def __init__(self, radio, db, label, search_type, query, user, active=False):
        style = discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, disabled=active)
        self.radio = radio
        self.db = db
        self.search_type = search_type
        self.query = query
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        from ui_views import SearchResultsView
        from ui import init_translate
        
        init_translate(self.radio)
        await interaction.response.defer()
        
        results = []
        if self.search_type == "songs":
            results = self.db.search_songs(self.query)
        elif self.search_type == "artists":
            results = self.db.search_artists(self.query)
        elif self.search_type == "albums":
            results = self.db.search_albums(self.query)
            
        view = SearchResultsView(self.radio, self.db, results, self.query, self.user, search_type=self.search_type)
        await interaction.edit_original_response(view=view)

class SearchBySelectionButton(discord.ui.Button):
    def __init__(self, radio, db, label, search_type, value, user, original_query=None):
        super().__init__(label=fixed(label, 20).strip(), style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.db = db
        self.search_type = search_type
        self.value = value
        self.user = user
        self.original_query = original_query

    async def callback(self, interaction: discord.Interaction):
        from ui_views import SearchResultsView
        from ui import init_translate
        
        init_translate(self.radio)
        await interaction.response.defer()
        
        results = []
        new_search_type = "songs"
        if self.search_type == "artist_songs":
            results = self.db.search_by_artist(self.value)
        elif self.search_type == "artist_albums":
            results = self.db.get_albums_by_artist(self.value)
            new_search_type = "albums"
        elif self.search_type == "album_songs":
            results = self.db.search_by_album(self.value[0], self.value[1])
            
        view = SearchResultsView(self.radio, self.db, results, str(self.value), self.user, search_type=new_search_type, original_query=self.original_query)
        await interaction.edit_original_response(view=view)

class QueueAllButton(discord.ui.Button):
    def __init__(self, radio, songs):
        super().__init__(
            label=t("queue_all"),
            style=discord.ButtonStyle.secondary,
            custom_id="queue_all_button"
        )
        self.radio = radio
        self.songs = songs

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        for song in reversed(self.songs):
            self.radio.dispatch(RadioAction.ADD_TO_QUEUE, song, user=interaction.user)
        await interaction.followup.send(
            f"{t('queue_all')}: {len(self.songs)} {t('results')}",
            ephemeral=True
        )

class HistoryFilterButton(discord.ui.Button):
    def __init__(self, radio, db):
        label = t("filter_label")
        emoji = "📅"
        if radio.filter_from or radio.filter_to:
            emoji = "🧹"
            label = t("clear_filter_label")
            
        super().__init__(
            label=f"{emoji} {label}",
            style=discord.ButtonStyle.secondary,
            custom_id="history_filter_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if self.radio.filter_from or self.radio.filter_to:
            self.radio.filter_from = None
            self.radio.filter_to = None
            from ui_views import HistoryView
            history = self.db.get_full_history(limit=10, offset=0)
            total_count = self.db.get_history_count()
            view = HistoryView(self.radio, self.db, history, total_count, page=0)
            await interaction.response.edit_message(view=view)
        else:
            modal = HistoryFilterModal(self.radio, self.db)
            await interaction.response.send_modal(modal)

class HistoryFilterModal(discord.ui.Modal):
    def __init__(self, radio, db):
        super().__init__(title=t("filter_modal_title"))
        self.radio = radio
        self.db = db
        
        from datetime import datetime
        now = datetime.now()
        year_str = now.strftime("%Y.%m.%d")
        
        self.from_input = discord.ui.TextInput(
            label=t("filter_from_label"),
            placeholder=year_str,
            style=discord.TextStyle.short,
            required=False,
            max_length=12
        )
        self.to_input = discord.ui.TextInput(
            label=t("filter_to_label"),
            placeholder=year_str,
            style=discord.TextStyle.short,
            required=False,
            max_length=12
        )
        self.add_item(self.from_input)
        self.add_item(self.to_input)

    async def on_submit(self, interaction: discord.Interaction):
        from ui_views import HistoryView
        from datetime import datetime
        
        def parse_date(ds):
            if not ds: return None
            clean = ds.strip().rstrip('.').replace('.', '-').replace(',', '-').replace('/', '-')
            try:
                return datetime.strptime(clean, '%Y-%m-%d').strftime('%Y.%m.%d')
            except:
                return None

        f_from = parse_date(self.from_input.value)
        f_to = parse_date(self.to_input.value)
        
        if (self.from_input.value and not f_from) or (self.to_input.value and not f_to):
            await interaction.response.send_message(t("date_invalid_error"), ephemeral=True)
            return

        self.radio.filter_from = f_from
        self.radio.filter_to = f_to
        
        await interaction.response.defer()
        
        history = self.db.get_full_history(limit=10, offset=0, filter_from=f_from, filter_to=f_to)
        total_count = self.db.get_history_count(filter_from=f_from, filter_to=f_to)
        
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        await interaction.edit_original_response(view=view)

class DeleteHistoryButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=t("delete_history_label"),
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            custom_id="delete_history_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.db.clear_history()
        from ui_views import HistoryView
        history = self.db.get_full_history(limit=10, offset=0)
        total_count = self.db.get_history_count()
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        await interaction.edit_original_response(view=view)
        await interaction.followup.send(t("history_cleared"), ephemeral=True)
