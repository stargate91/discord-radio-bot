import discord
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, PaginatedView, BaseView
from ui_utils import fixed, format_duration, safe_delete_message, safe_fetch_message, check_editor_lock
from ui_theme import Theme

class PlaylistViewButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('playlists_tab'),
            emoji=Icons.PLAYLIST,
            style=discord.ButtonStyle.secondary,
            custom_id="playlist_view_button"
        )
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        playlists = await self.db.get_all_playlists(interaction.user.id)
        self.radio.active_view_type = "search"
        self.radio.last_search_query = ""
        self.radio.last_search_results = playlists
        self.radio.last_search_user = interaction.user
        self.radio.last_search_page = 0
        self.radio.last_search_type = "playlists"
        user_id = interaction.user.id
        editing_pid = self.radio.get_editing_playlist(user_id)
        existing_paths = set()
        if editing_pid:
             playlist_songs = await self.db.get_playlist_songs(editing_pid)
             existing_paths = {s['path'] for s in playlist_songs}
        all_playlists = await self.db.get_all_playlists(user_id) if editing_pid else []
        from ui_search import SearchResultsView
        view = SearchResultsView(self.radio, playlists, "", interaction.user, search_type="playlists", existing_paths=existing_paths, all_playlists=all_playlists)
        await interaction.followup.send(view=view, ephemeral=True)

class PlaylistStudioButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=t("playlist_studio_label"),
            style=discord.ButtonStyle.secondary,
            emoji=Icons.STUDIO,
            custom_id="playlist_studio_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Remove global lock check as requested, multiple users can use studio
        await interaction.response.defer()
        current_view = self.radio.active_view_type
        # State is now personal, no need to lock the whole studio
        self.radio.active_view_type = "studio"
        playlists = await self.radio.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        view = PlaylistStudioView(self.radio, playlists=playlists)
        
        if current_view in ["search", "history", "stats"]:
            await interaction.edit_original_response(view=view)
        else:
            await interaction.followup.send(view=view, ephemeral=True)

class PlaylistSelect(discord.ui.Select):

    def __init__(self, radio, playlists):
        self.radio = radio
        self.db = radio.db
        options = []
        for p in playlists:
            icon = Icons.FOLDER_HEART if p.get('is_favorite') == 1 else Icons.PLAYLIST
            options.append(discord.SelectOption(
                label=p['name'],
                value=str(p['id']),
                emoji=icon
            ))
        super().__init__(placeholder=t("select_playlist_placeholder"), options=options, custom_id="playlist_select")

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        playlist_id = int(self.values[0])
        # Check if another user is editing this SPECIFIC playlist
        if await check_editor_lock(self.radio, interaction, playlist_id): return

        self.radio.set_editing_playlist(interaction.user.id, playlist_id)
        # We store the user who is editing this specific playlist
        self.radio.playlist_locks[playlist_id] = interaction.user.id
        self.radio.last_editor_page = 0
        songs = await self.db.get_playlist_songs(playlist_id)
        all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, playlist_id, songs=songs, all_playlists=all_playlists))

class NewPlaylistButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=t("new_playlist_label"), style=discord.ButtonStyle.secondary, emoji=Icons.ADD)
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Multiple users can create playlists
        await interaction.response.send_modal(NewPlaylistModal(self.radio))

class NewPlaylistModal(Modal):

    def __init__(self, radio):
        super().__init__(title=t("create_playlist_modal_title"))
        self.radio = radio
        self.db = radio.db
        self.name_input = TextInput(label=t("playlist_name_label"), required=True, min_length=1, max_length=50)
        self.add_item(self.name_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pid = await self.db.create_playlist(self.name_input.value, interaction.user.id)
        self.radio.set_editing_playlist(interaction.user.id, pid)
        self.radio.playlist_locks[pid] = interaction.user.id
        self.radio.last_editor_page = 0
        songs = await self.db.get_playlist_songs(pid)
        all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, pid, songs=songs, all_playlists=all_playlists))

class RemoveFromPlaylistButton(discord.ui.Button):

    def __init__(self, radio, playlist_id, song_path):
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary, custom_id=f"rem_pl_{unique}")
        self.radio = radio
        self.db = radio.db
        self.playlist_id = playlist_id
        self.song_path = song_path

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction, self.playlist_id): return
        await interaction.response.defer()
        await self.db.remove_song_from_playlist(self.playlist_id, self.song_path)
        songs = await self.db.get_playlist_songs(self.playlist_id)
        all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.playlist_id, page=self.radio.last_editor_page, songs=songs, all_playlists=all_playlists))

class DeletePlaylistButton(discord.ui.Button):

    def __init__(self, radio, playlist_id):
        super().__init__(label=t("delete_playlist_label"), style=discord.ButtonStyle.danger, emoji=Icons.WARNING)
        self.radio = radio
        self.db = radio.db
        self.playlist_id = playlist_id

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction, self.playlist_id): return
        await interaction.response.defer(ephemeral=True)
        await self.db.delete_playlist(self.playlist_id)
        self.radio.set_editing_playlist(interaction.user.id, None)
        self.radio.playlist_locks.pop(self.playlist_id, None)
        playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistStudioView(self.radio, playlists=playlists))

class RescanLibraryButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(
            label=t("rescan_label"),
            style=discord.ButtonStyle.secondary,
            emoji=Icons.RESCAN,
            custom_id="rescan_library_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("no_permission_general"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from scanner import scan_music_library
        await scan_music_library(self.radio.config, self.radio.db, force=True)
        try: await interaction.delete_original_response()
        except: pass

class AddGenreModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("add_genre_modal_title"))
        self.radio = radio
        self.genre_input = TextInput(
            label=t("genre_name_label"),
            placeholder="e.g. Synthwave",
            required=True,
            min_length=2,
            max_length=50
        )
        self.paths_input = TextInput(
            label=t("folder_paths_label"),
            placeholder="C:/Music/Genre1, D:/Music/Genre2",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=3
        )
        self.add_item(self.genre_input)
        self.add_item(self.paths_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("admin_only"), ephemeral=True)
            return
        genre_name = self.genre_input.value.strip()
        # Clean paths: strip whitespace and replace backslashes (Windows) with forward slashes
        paths = [p.strip().replace("\\", "/") for p in self.paths_input.value.split(",") if p.strip()]
        
        if not genre_name or not paths:
            await interaction.response.send_message(t("invalid_input"), ephemeral=True)
            return
            
        current_genres = self.radio.config.genres.copy()
        current_genres[genre_name] = paths
        self.radio.config.save_genres(current_genres)
        
        await interaction.response.defer(ephemeral=True)
        try: await interaction.delete_original_response()
        except: pass
        
        from scanner import scan_music_library
        await scan_music_library(self.radio.config, self.radio.db)

class AddGenreButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("add_genre_label"),
            style=discord.ButtonStyle.secondary,
            emoji=Icons.FOLDER_ADD,
            custom_id="add_genre_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("admin_only"), ephemeral=True)
            return

        await interaction.response.send_modal(AddGenreModal(self.radio))


class PathUpdateButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("path_update_label") or "Path Update",
            style=discord.ButtonStyle.secondary,
            emoji=Icons.INFO,
            custom_id="path_update_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("no_permission_general"), ephemeral=True)
            return
        await interaction.response.send_modal(PathUpdateModal(self.radio))

class PathUpdateModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("path_update_modal_title") or "Update Tags by Path")
        self.radio = radio
        self.path_input = TextInput(
            label=t("path_input_label") or "Directory Path",
            placeholder="F:\\music\\labels\\audio_swarm",
            required=True
        )
        self.add_item(self.path_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("no_permission_general"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(t("updating_tags") or "Updating tags, please wait...", ephemeral=True)
        
        from scanner import scan_specific_path
        inserted, skipped, error = await scan_specific_path(self.path_input.value, self.radio.config, self.radio.db, force=True)
        
        if error:
            error_msg = t(error) if error in ["unauthorized_path"] else error
            await interaction.followup.send(f"{Icons.WARNING} **Error:** {error_msg}", ephemeral=True)
        else:
            try: await interaction.delete_original_response()
            except: pass

class ExitStudioButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=t("save_exit_label"), style=discord.ButtonStyle.secondary, emoji=Icons.EXIT)
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        current_pid = self.radio.get_editing_playlist(interaction.user.id)
        if current_pid:
            # If leaving the specific playlist back to studio selection
            if await check_editor_lock(self.radio, interaction, current_pid): return
            await interaction.response.defer()
            # Clear user-specific editing ID but keep the studio session
            self.radio.set_editing_playlist(interaction.user.id, None)
            self.radio.playlist_locks.pop(current_pid, None)
            playlists = await self.radio.db.get_all_playlists(interaction.user.id, strictly_personal=True)
            await interaction.edit_original_response(view=PlaylistStudioView(self.radio, playlists=playlists))
        else:
            # Full Exit from Studio
            await interaction.response.defer()
            self.radio.active_view_type = None
            self.radio.embed_manager.save_message_id("search", None)
            try: await interaction.delete_original_response()
            except: pass

class RenamePlaylistButton(discord.ui.Button):

    def __init__(self, radio, playlist_id):
        super().__init__(label=t("rename_playlist_label"), style=discord.ButtonStyle.secondary, emoji=Icons.RENAME)
        self.radio = radio
        self.db = radio.db
        self.playlist_id = playlist_id

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction, self.playlist_id): return
        await interaction.response.send_modal(RenamePlaylistModal(self.radio, self.playlist_id))

class RenamePlaylistModal(Modal):

    def __init__(self, radio, playlist_id):
        super().__init__(title=t("rename_playlist_modal_title") or "Rename Playlist")
        self.radio = radio
        self.db = radio.db
        self.playlist_id = playlist_id
        self.name_input = TextInput(label=t("playlist_name_label"), required=True, min_length=1, max_length=50)
        self.add_item(self.name_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.db.rename_playlist(self.playlist_id, self.name_input.value)
        songs = await self.db.get_playlist_songs(self.playlist_id)
        all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.playlist_id, page=self.radio.last_editor_page, songs=songs, all_playlists=all_playlists))

class MoveSongInPlaylistButton(discord.ui.Button):

    def __init__(self, radio, playlist_id, song_path, direction, emoji):
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"move_pl_{unique}")
        self.radio = radio
        self.db = radio.db
        self.playlist_id = playlist_id
        self.song_path = song_path
        self.direction = direction

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        await self.db.move_song_in_playlist(self.playlist_id, self.song_path, self.direction)
        songs = await self.db.get_playlist_songs(self.playlist_id)
        all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.playlist_id, page=self.radio.last_editor_page, songs=songs, all_playlists=all_playlists))

class BackToEditorButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=t("back_label") or "Back", style=discord.ButtonStyle.secondary, emoji=Icons.BACK)
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        editing_pid = self.radio.get_editing_playlist(interaction.user.id)
        if editing_pid:
            if await check_editor_lock(self.radio, interaction, editing_pid): return
        await interaction.response.defer()
        songs = await self.radio.db.get_playlist_songs(editing_pid)
        all_playlists = await self.radio.db.get_all_playlists(interaction.user.id, strictly_personal=True)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, editing_pid, page=self.radio.last_editor_page, songs=songs, all_playlists=all_playlists))

class HistoryButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=None if radio.is_compact else t("history_label"), emoji=Icons.HISTORY, style=discord.ButtonStyle.secondary, custom_id="history_button")
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        limit = self.radio.config.history_items_per_page
        history = await self.db.get_full_history(limit=limit, offset=0)
        total_count = await self.db.get_history_count()
        current_view = self.radio.active_view_type
        self.radio.active_view_type = "history"
        self.radio.last_history_page = 0
        self.radio.filter_from = None
        self.radio.filter_to = None
        view = HistoryView(self.radio, history, total_count, page=0, user=interaction.user)
        if current_view in ["search", "studio", "playlist_editor", "stats"]:
            await interaction.edit_original_response(view=view)
        else:
            await interaction.followup.send(view=view, ephemeral=True)

class HistoryFilterButton(discord.ui.Button):

    def __init__(self, radio):
        label = t("filter_label")
        emoji = Icons.CALENDAR
        if radio.filter_from or radio.filter_to:
            emoji = Icons.SWEEP
            label = t("clear_filter_label")
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id="history_filter_button")
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.filter_from or self.radio.filter_to:
            self.radio.filter_from = None
            self.radio.filter_to = None
            limit = self.radio.config.history_items_per_page
            history = await self.db.get_full_history(limit=limit, offset=0)
            total_count = await self.db.get_history_count()
            view = HistoryView(self.radio, history, total_count, page=0, user=interaction.user)
            await interaction.response.edit_message(view=view)
        else:
            await interaction.response.send_modal(HistoryFilterModal(self.radio))

class HistoryFilterModal(discord.ui.Modal):

    def __init__(self, radio):
        super().__init__(title=t("filter_modal_title"))
        self.radio = radio
        self.db = radio.db
        from datetime import datetime
        year_str = datetime.now().strftime("%Y.%m.%d")
        self.from_input = TextInput(label=t("filter_from_label"), placeholder=year_str, required=False, max_length=12)
        self.to_input = TextInput(label=t("filter_to_label"), placeholder=year_str, required=False, max_length=12)
        self.add_item(self.from_input)
        self.add_item(self.to_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        from datetime import datetime

        def parse_date(ds):
            if not ds: return None
            clean = ds.strip().rstrip('.').replace('.', '-').replace(',', '-').replace('/', '-')
            try: return datetime.strptime(clean, '%Y-%m-%d').strftime('%Y.%m.%d')
            except Exception as e:
                print(f"[HISTORY FILTER] Failed to parse date '{ds}': {e}")
                return None
        f_from = parse_date(self.from_input.value)
        f_to = parse_date(self.to_input.value)
        if (self.from_input.value and not f_from) or (self.to_input.value and not f_to):
            await interaction.response.send_message(t("date_invalid_error"), ephemeral=True); return
        self.radio.filter_from = f_from
        self.radio.filter_to = f_to
        await interaction.response.defer()
        limit = self.radio.config.history_items_per_page
        history = await self.db.get_full_history(limit=limit, offset=0, filter_from=f_from, filter_to=f_to)
        total_count = await self.db.get_history_count(filter_from=f_from, filter_to=f_to)
        view = HistoryView(self.radio, history, total_count, page=0, user=interaction.user)
        await interaction.edit_original_response(view=view)

class DeleteHistoryButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=t("delete_history_label"), style=discord.ButtonStyle.danger, emoji=Icons.REMOVE, custom_id="delete_history_button")
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(t("no_permission_general"), ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        await self.db.clear_history()
        limit = self.radio.config.history_items_per_page
        history = await self.db.get_full_history(limit=limit, offset=0)
        total_count = await self.db.get_history_count()
        view = HistoryView(self.radio, history, total_count, page=0, user=interaction.user)
        await interaction.edit_original_response(view=view)

class StatsButton(discord.ui.Button):

    def __init__(self, radio):
        super().__init__(label=None if radio.is_compact else t('stats_label'), emoji=Icons.STATS, style=discord.ButtonStyle.secondary, custom_id="stats_button")
        self.radio = radio
        self.db = radio.db

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.active_view_type = "stats"
        days = 7
        top_artists = await self.db.get_top_artists(days=days)
        top_songs = await self.db.get_top_songs(days=days)
        top_users = await self.db.get_top_users(days=days)
        current_view = self.radio.active_view_type
        self.radio.active_view_type = "stats"
        view = StatsView(self.radio, interaction.user, period="weekly", guild=interaction.guild, top_artists=top_artists, top_songs=top_songs, top_users=top_users)
        if current_view in ["search", "studio", "playlist_editor", "history"]:
            await interaction.edit_original_response(view=view)
        else:
            await interaction.followup.send(view=view, ephemeral=True)

class StatsTabButton(discord.ui.Button):

    def __init__(self, radio, label, period, user, active=False):
        style = discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, disabled=active)
        self.radio = radio
        self.db = radio.db
        self.period = period
        self.user = user

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        days = 7
        if self.period == "monthly": days = 30
        elif self.period == "all_time": days = None
        top_artists = await self.db.get_top_artists(days=days)
        top_songs = await self.db.get_top_songs(days=days)
        top_users = await self.db.get_top_users(days=days)
        view = StatsView(self.radio, self.user, period=self.period, guild=interaction.guild, top_artists=top_artists, top_songs=top_songs, top_users=top_users)
        await interaction.edit_original_response(view=view)

class StatsView(BaseView):

    def __init__(self, radio, user=None, period="weekly", guild=None, top_artists=None, top_songs=None, top_users=None):
        super().__init__(radio)
        self.db = radio.db
        self.user = user or radio.last_user
        self.period = period
        self.guild = guild
        self.top_artists = top_artists or []
        self.top_songs = top_songs or []
        self.top_users = top_users or []
        days = 7
        period_key = "stats_weekly"
        if period == "monthly":
            days = 30
            period_key = "stats_monthly"
        elif period == "all_time":
            days = None
            period_key = "stats_all_time"
        container = Container(accent_color=Theme.PRIMARY)
        tab_row = ActionRow()
        tab_row.add_item(StatsTabButton(radio, t("stats_weekly"), "weekly", self.user, active=(period == "weekly")))
        tab_row.add_item(StatsTabButton(radio, t("stats_monthly"), "monthly", self.user, active=(period == "monthly")))
        tab_row.add_item(StatsTabButton(radio, t("stats_all_time"), "all_time", self.user, active=(period == "all_time")))
        close_btn = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)

        @handle_ui_error
        async def close_callback(interaction):
            await interaction.response.defer()
            self.radio.active_view_type = None
            try: await interaction.delete_original_response()
            except: pass
        close_btn.callback = close_callback
        tab_row.add_item(close_btn)
        container.add_item(tab_row)
        container.add_item(Separator())
        container.add_item(TextDisplay(f"{Icons.STATUS} **{t(period_key)}**"))
        container.add_item(Separator())
        artist_text = f"**{t('top_artists')}**\n"
        if self.top_artists:
            artist_text += "\n".join([f"{i+1}. {a['artist']} ({a['count']})" for i, a in enumerate(self.top_artists)])
        else:
            artist_text += f"*{t('empty')}*"
        container.add_item(TextDisplay(artist_text))
        container.add_item(Separator())
        songs_text = f"**{t('top_songs')}**\n"
        if self.top_songs:
            songs_text += "\n".join([f"{i+1}. {s['artist']} - {s['title']} ({s['count']})" for i, s in enumerate(self.top_songs)])
        else:
            songs_text += f"*{t('empty')}*"
        container.add_item(TextDisplay(songs_text))
        container.add_item(Separator())
        users_text = f"**{t('top_listeners')}**\n"
        if self.top_users:
            from ui import bot
            user_list = []
            for i, u in enumerate(self.top_users):
                user_id = int(u['user_id'])
                name = None
                if self.guild:
                    member = self.guild.get_member(user_id)
                    if member: name = member.display_name
                if not name:
                    user_obj = bot.get_user(user_id)
                    if user_obj: name = user_obj.display_name
                if not name:
                    name = f"User {user_id}"
                user_list.append(f"{i+1}. {name} ({u['count']})")
            users_text += "\n".join(user_list)
        else:
            users_text += f"*{t('empty')}*"
        container.add_item(TextDisplay(users_text))
        self.add_item(container)

class PlaylistStudioView(BaseView):

    def __init__(self, radio, playlists=None):
        super().__init__(radio)
        self.db = radio.db
        self.playlists = playlists or []
        self.radio.active_view_type = "studio"
        container = Container(accent_color=Theme.BACKGROUND)
        container.add_item(TextDisplay(f"**{t('playlist_studio_title')}**\n{t('playlist_studio_subtitle')}"))
        if self.playlists:
            row_select = ActionRow()
            row_select.add_item(PlaylistSelect(radio, self.playlists))
            container.add_item(row_select)
        row_btns = ActionRow()
        row_btns.add_item(NewPlaylistButton(radio))
        row_btns.add_item(ExitStudioButton(radio))
        container.add_item(row_btns)
        self.add_item(container)

class PlaylistEditorView(PaginatedView):

    def __init__(self, radio, playlist_id, page=0, songs=None, all_playlists=None):
        super().__init__(radio, songs or [], items_per_page=radio.config.playlist_items_per_page, page=page)
        self.db = radio.db
        self.playlist_id = playlist_id
        self.all_playlists = all_playlists or []
        self.radio.active_view_type = "playlist_editor"
        total_duration = sum(s.get('duration', 0) for s in self.data_list)
        duration_str = format_duration(total_duration)
        container = Container(accent_color=Theme.PRIMARY)
        current_pl = next((p for p in self.all_playlists if p['id'] == playlist_id), None)
        is_fav = (current_pl.get('is_favorite') == 1) if current_pl else False
        
        playlist_name = current_pl['name'] if current_pl else "Unknown"
        container.add_item(TextDisplay(f"**{t('list_editor_title')}: {playlist_name}**"))
        ctrl_row = ActionRow()
        from ui_search import LibraryButton, SearchButton
        ctrl_row.add_item(LibraryButton(radio))
        ctrl_row.add_item(SearchButton(radio))
        
        if not is_fav:
            ctrl_row.add_item(RenamePlaylistButton(radio, playlist_id))
            
        ctrl_row.add_item(DeletePlaylistButton(radio, playlist_id))
        ctrl_row.add_item(ExitStudioButton(radio))
        container.add_item(ctrl_row)
        container.add_item(Separator())
        if not self.data_list:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            page_songs = self.get_page_items()
            for i, song in enumerate(page_songs, self.current_page * self.items_per_page + 1):
                info = f"**{i}. {song['artist']} - {song['title']}**"
                controls = ActionRow()
                controls.add_item(MoveSongInPlaylistButton(radio, playlist_id, song['path'], -1, Icons.MOVE_UP))
                controls.add_item(MoveSongInPlaylistButton(radio, playlist_id, song['path'], 1, Icons.MOVE_DOWN))
                controls.add_item(RemoveFromPlaylistButton(radio, playlist_id, song['path']))
                container.add_item(TextDisplay(info))
                container.add_item(controls)
        container.add_item(Separator())
        footer = f"{self.pagination_info} • {duration_str}"
        container.add_item(TextDisplay(footer))
        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev_btn, next_btn)

        @handle_ui_error
        async def prev_callback(interaction):
            if await check_editor_lock(self.radio, interaction, playlist_id): return
            await interaction.response.defer()
            self.current_page -= 1
            songs = await self.db.get_playlist_songs(playlist_id)
            all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
            await interaction.edit_original_response(view=PlaylistEditorView(self.radio, playlist_id, page=self.current_page, songs=songs, all_playlists=all_playlists))
        prev_btn.callback = prev_callback

        @handle_ui_error
        async def next_callback(interaction):
            if await check_editor_lock(self.radio, interaction, playlist_id): return
            await interaction.response.defer()
            self.current_page += 1
            songs = await self.db.get_playlist_songs(playlist_id)
            all_playlists = await self.db.get_all_playlists(interaction.user.id, strictly_personal=True)
            await interaction.edit_original_response(view=PlaylistEditorView(self.radio, playlist_id, page=self.current_page, songs=songs, all_playlists=all_playlists))
        next_btn.callback = next_callback
        nav_row.add_item(prev_btn)
        nav_row.add_item(next_btn)
        container.add_item(nav_row)
        self.add_item(container)

class HistoryView(PaginatedView):

    def __init__(self, radio, history, total_count, page=0, user=None):
        super().__init__(radio, history, items_per_page=radio.config.history_items_per_page, page=page)
        self.db = radio.db
        self.history = history
        self.total_count = total_count
        self.user = user or radio.last_user
        self.items_per_page = radio.config.history_items_per_page
        self.total_pages = (total_count + self.items_per_page - 1) // self.items_per_page
        self.update_view_all()

    def update_view_all(self):
        self.clear_items()
        container = Container(accent_color=Theme.BACKGROUND)
        close_btn = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)

        @handle_ui_error
        async def close_callback(interaction):
            await interaction.response.defer()
            self.radio.active_view_type = None
            try: await interaction.delete_original_response()
            except: pass
        close_btn.callback = close_callback
        ctrl_row = ActionRow()
        ctrl_row.add_item(HistoryFilterButton(self.radio))
        ctrl_row.add_item(DeleteHistoryButton(self.radio))
        ctrl_row.add_item(close_btn)
        container.add_item(ctrl_row)
        container.add_item(Separator())
        if self.radio.filter_from or self.radio.filter_to:
            filter_text = f"{Icons.LOCATION} {t('filter_label')}: "
            if self.radio.filter_from: filter_text += f"{t('filter_from_label').split(' ')[0]} {self.radio.filter_from} "
            if self.radio.filter_to: filter_text += f"{t('filter_to_label').split(' ')[0]} {self.radio.filter_to}"
            container.add_item(TextDisplay(f"*{filter_text}*"))
            container.add_item(Separator())
        if not self.history:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            from datetime import datetime
            date_fmt = t("date_format")
            from ui_search import AddSongButton
            start_idx = self.current_page * self.items_per_page
            page_history = self.history
            if len(self.history) > self.items_per_page:
                page_history = self.history[0:self.items_per_page]
            for i, item in enumerate(page_history, start_idx + 1):
                timestamp = item.get('played_at', '')
                try:
                    if isinstance(timestamp, (int, float)): time_str = datetime.fromtimestamp(timestamp).strftime(date_fmt)
                    else:
                        dt = datetime.fromisoformat(str(timestamp))
                        time_str = dt.strftime(date_fmt)
                except Exception as e:
                    print(f"[HISTORY] Failed to format timestamp '{timestamp}': {e}")
                    time_str = str(timestamp)
                song_info = f"**{i}. {item['title']}** {item['artist']}\n*({t('played_at')} {time_str})*"
                container.add_item(Section(song_info, accessory=AddSongButton(self.radio, item)))
        container.add_item(Separator())
        footer_text = f"{t('page')} {self.current_page + 1}/{self.total_pages} • {self.total_count} {t('results')}"
        if self.user:
            footer_text += f" • {t('initiated_by')} {self.user.mention}"
        container.add_item(TextDisplay(footer_text))
        container.add_item(Separator())
        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary, disabled=(self.current_page == 0))

        @handle_ui_error
        async def prev_callback(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_data(interaction)
        prev_btn.callback = prev_callback
        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary, disabled=(self.current_page >= self.total_pages - 1))

        @handle_ui_error
        async def next_callback(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_data(interaction)
        next_btn.callback = next_callback
        last_btn = discord.ui.Button(label=t("last_label"), style=discord.ButtonStyle.secondary, disabled=(self.current_page >= self.total_pages - 1))

        @handle_ui_error
        async def last_callback(interaction):
            await interaction.response.defer()
            self.current_page = self.total_pages - 1
            await self.refresh_data(interaction)
        last_btn.callback = last_callback
        nav_row.add_item(prev_btn)
        nav_row.add_item(next_btn)
        nav_row.add_item(last_btn)
        container.add_item(nav_row)
        self.add_item(container)
    async def refresh_data(self, interaction):
        self.radio.last_history_page = self.current_page
        self.history = await self.db.get_full_history(limit=self.items_per_page, offset=self.current_page * self.items_per_page, filter_from=self.radio.filter_from, filter_to=self.radio.filter_to)
        self.update_view_all()
        await interaction.edit_original_response(view=self)
