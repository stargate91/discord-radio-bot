import discord
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_utils import fixed, format_duration
from radio_actions import RadioAction
from ui_theme import Theme

async def check_editor_lock(radio, interaction):
    if radio.playlist_editor_user and radio.playlist_editor_user != interaction.user.id:
        try:
            member = await interaction.guild.fetch_member(radio.playlist_editor_user)
            name = member.display_name
        except: name = "Someone"
        await interaction.response.send_message(t("studio_locked_message").format(user=name), ephemeral=True)
        return True
    return False

class PlaylistViewButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=t('playlists_tab'),
            emoji=Icons.PLAYLIST,
            style=discord.ButtonStyle.secondary,
            custom_id="playlist_view_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        from ui_search import SearchResultsView
        from ui import embed_state
        await interaction.response.defer()
        
        playlists = self.db.get_all_playlists(interaction.user.id)
        self.radio.active_view_type = "search"
        self.radio.last_search_query = ""
        self.radio.last_search_results = playlists
        self.radio.last_search_user = interaction.user
        self.radio.last_search_page = 0
        self.radio.last_search_type = "playlists"
        
        view = SearchResultsView(self.radio, self.db, playlists, "", interaction.user, search_type="playlists")
        old_id = embed_state.load_message_id("search")
        if old_id:
            try:
                msg = await interaction.channel.fetch_message(old_id)
                await msg.delete()
            except: pass
            
        msg = await interaction.followup.send(view=view, wait=True)
        embed_state.save_message_id("search", msg.id)

class PlaylistStudioButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("playlist_studio_label"), 
            style=discord.ButtonStyle.secondary, 
            emoji=Icons.STUDIO,
            custom_id="playlist_studio_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.playlist_editor_user and self.radio.playlist_editor_user != interaction.user.id:
            try:
                member = await interaction.guild.fetch_member(self.radio.playlist_editor_user)
                name = member.display_name
            except: name = "Someone"
            await interaction.response.send_message(t("studio_locked_message").format(user=name), ephemeral=True)
            return

        await interaction.response.defer()
        self.radio.playlist_editor_user = interaction.user.id
        from database import DatabaseManager
        from ui import embed_state
        self.radio.active_view_type = "studio"
        db = DatabaseManager()
        view = PlaylistStudioView(self.radio, db)
        
        old_id = embed_state.load_message_id("search")
        if old_id:
            try:
                msg = await interaction.channel.fetch_message(old_id)
                await msg.delete()
            except: pass
            embed_state.save_message_id("search", None)

        msg = await interaction.followup.send(view=view, wait=True)
        embed_state.save_message_id("search", msg.id)

class PlaylistSelect(discord.ui.Select):
    def __init__(self, radio, db, playlists):
        self.radio = radio
        self.db = db
        options = []
        for p in playlists:
            options.append(discord.SelectOption(
                label=p['name'], 
                value=str(p['id']), 
                emoji=Icons.PLAYLIST
            ))
        super().__init__(placeholder=t("select_playlist_placeholder"), options=options, custom_id="playlist_select")

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        playlist_id = int(self.values[0])
        self.radio.editing_playlist_id = playlist_id
        self.radio.last_editor_page = 0
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.db, playlist_id))

class NewPlaylistButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(label=t("new_playlist_label"), style=discord.ButtonStyle.secondary, emoji=Icons.ADD)
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.send_modal(NewPlaylistModal(self.radio, self.db))

class NewPlaylistModal(Modal):
    def __init__(self, radio, db):
        super().__init__(title=t("create_playlist_modal_title"))
        self.radio = radio
        self.db = db
        self.name_input = TextInput(label=t("playlist_name_label"), required=True, min_length=1, max_length=50)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pid = self.db.create_playlist(self.name_input.value, interaction.user.id)
        self.radio.editing_playlist_id = pid
        self.radio.last_editor_page = 0
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.db, pid))

class RemoveFromPlaylistButton(discord.ui.Button):
    def __init__(self, radio, db, playlist_id, song_path):
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary, custom_id=f"rem_pl_{unique}")
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id
        self.song_path = song_path

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        self.db.remove_song_from_playlist(self.playlist_id, self.song_path)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.db, self.playlist_id, page=self.radio.last_editor_page))

class DeletePlaylistButton(discord.ui.Button):
    def __init__(self, radio, db, playlist_id):
        super().__init__(label=t("delete_playlist_label"), style=discord.ButtonStyle.danger, emoji=Icons.WARNING)
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer(ephemeral=True)
        self.db.delete_playlist(self.playlist_id)
        self.radio.editing_playlist_id = None
        await interaction.edit_original_response(view=PlaylistStudioView(self.radio, self.db))
        await interaction.followup.send(t("playlist_deleted"), ephemeral=True)

class ExitStudioButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(label=t("save_exit_label"), style=discord.ButtonStyle.secondary, emoji=Icons.EXIT)
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        self.radio.editing_playlist_id = None
        self.radio.playlist_editor_user = None
        from ui import embed_state
        embed_state.save_message_id("search", None)
        await interaction.delete_original_response()

class RenamePlaylistButton(discord.ui.Button):
    def __init__(self, radio, db, playlist_id):
        super().__init__(label=t("rename_playlist_label") or "Rename", style=discord.ButtonStyle.secondary, emoji=Icons.RENAME)
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.send_modal(RenamePlaylistModal(self.radio, self.db, self.playlist_id))

class RenamePlaylistModal(Modal):
    def __init__(self, radio, db, playlist_id):
        super().__init__(title=t("rename_playlist_modal_title") or "Rename Playlist")
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id
        self.name_input = TextInput(label=t("playlist_name_label"), required=True, min_length=1, max_length=50)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.db.rename_playlist(self.playlist_id, self.name_input.value)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.db, self.playlist_id, page=self.radio.last_editor_page))

class MoveSongInPlaylistButton(discord.ui.Button):
    def __init__(self, radio, db, playlist_id, song_path, direction, emoji):
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"move_{direction}_{unique}")
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id
        self.song_path = song_path
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        self.db.move_song_in_playlist(self.playlist_id, self.song_path, self.direction)
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, self.db, self.playlist_id, page=self.radio.last_editor_page))

class BackToEditorButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(label=t("back_label") or "Back", style=discord.ButtonStyle.secondary, emoji=Icons.BACK)
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if await check_editor_lock(self.radio, interaction): return
        await interaction.response.defer()
        from database import DatabaseManager
        db = DatabaseManager()
        await interaction.edit_original_response(view=PlaylistEditorView(self.radio, db, self.radio.editing_playlist_id, page=self.radio.last_editor_page))

class HistoryButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(label=t('history_label'), emoji=Icons.HISTORY, style=discord.ButtonStyle.secondary, custom_id="history_button")
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        from ui import embed_state
        await interaction.response.defer()
        history = self.db.get_full_history(limit=self.radio.config.history_items_per_page, offset=0)
        total_count = self.db.get_history_count()
        self.radio.active_view_type = "history"
        self.radio.last_history_page = 0
        self.radio.filter_from = None
        self.radio.filter_to = None
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        search_id = embed_state.load_message_id("search")
        if search_id:
            try:
                msg = await interaction.channel.fetch_message(search_id)
                await msg.delete()
            except: pass
        msg = await interaction.followup.send(view=view, wait=True)
        embed_state.save_message_id("search", msg.id)

class HistoryFilterButton(discord.ui.Button):
    def __init__(self, radio, db):
        label = t("filter_label")
        emoji = Icons.CALENDAR
        if radio.filter_from or radio.filter_to:
            emoji = Icons.SWEEP
            label = t("clear_filter_label")
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id="history_filter_button")
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if self.radio.filter_from or self.radio.filter_to:
            self.radio.filter_from = None
            self.radio.filter_to = None
            history = self.db.get_full_history(limit=self.radio.config.history_items_per_page, offset=0)
            total_count = self.db.get_history_count()
            view = HistoryView(self.radio, self.db, history, total_count, page=0)
            await interaction.response.edit_message(view=view)
        else:
            await interaction.response.send_modal(HistoryFilterModal(self.radio, self.db))

class HistoryFilterModal(discord.ui.Modal):
    def __init__(self, radio, db):
        super().__init__(title=t("filter_modal_title"))
        self.radio = radio
        self.db = db
        from datetime import datetime
        year_str = datetime.now().strftime("%Y.%m.%d")
        self.from_input = TextInput(label=t("filter_from_label"), placeholder=year_str, required=False, max_length=12)
        self.to_input = TextInput(label=t("filter_to_label"), placeholder=year_str, required=False, max_length=12)
        self.add_item(self.from_input)
        self.add_item(self.to_input)

    async def on_submit(self, interaction: discord.Interaction):
        from datetime import datetime
        def parse_date(ds):
            if not ds: return None
            clean = ds.strip().rstrip('.').replace('.', '-').replace(',', '-').replace('/', '-')
            try: return datetime.strptime(clean, '%Y-%m-%d').strftime('%Y.%m.%d')
            except: return None
        f_from = parse_date(self.from_input.value)
        f_to = parse_date(self.to_input.value)
        if (self.from_input.value and not f_from) or (self.to_input.value and not f_to):
            await interaction.response.send_message(t("date_invalid_error"), ephemeral=True); return
        self.radio.filter_from = f_from
        self.radio.filter_to = f_to
        await interaction.response.defer()
        history = self.db.get_full_history(limit=self.radio.config.history_items_per_page, offset=0, filter_from=f_from, filter_to=f_to)
        total_count = self.db.get_history_count(filter_from=f_from, filter_to=f_to)
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        await interaction.edit_original_response(view=view)

class DeleteHistoryButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(label=t("delete_history_label"), style=discord.ButtonStyle.danger, emoji=Icons.REMOVE, custom_id="delete_history_button")
        self.radio = radio
        self.db = db
    async def callback(self, interaction: discord.Interaction):
        user_role_ids = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
        if self.radio.config.admin_role_id not in user_role_ids:
            await interaction.response.send_message(t("no_permission_general"), ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        self.db.clear_history()
        history = self.db.get_full_history(limit=self.radio.config.history_items_per_page, offset=0)
        total_count = self.db.get_history_count()
        view = HistoryView(self.radio, self.db, history, total_count, page=0)
        await interaction.edit_original_response(view=view)
        await interaction.followup.send(t("history_cleared"), ephemeral=True)

# Views
class PlaylistStudioView(LayoutView):
    def __init__(self, radio, db):
        super().__init__(timeout=None)
        self.radio = radio
        self.db = db
        container = Container(accent_color=Theme.BACKGROUND)
        container.add_item(TextDisplay(f"**{t('playlist_studio_title')}**\n{t('playlist_studio_subtitle')}"))
        playlists = db.get_all_playlists(self.radio.playlist_editor_user, strictly_personal=True)
        if playlists:
            row_select = ActionRow()
            row_select.add_item(PlaylistSelect(radio, db, playlists))
            container.add_item(row_select)
        row_btns = ActionRow()
        row_btns.add_item(NewPlaylistButton(radio, db))
        row_btns.add_item(ExitStudioButton(radio))
        container.add_item(row_btns)
        self.add_item(container)

class PlaylistEditorView(LayoutView):
    def __init__(self, radio, db, playlist_id, page=0):
        super().__init__(timeout=None)
        self.radio = radio
        self.db = db
        self.playlist_id = playlist_id
        self.page = page
        self.items_per_page = radio.config.playlist_items_per_page
        self.radio.active_view_type = "playlist_editor"
        songs = db.get_playlist_songs(playlist_id)
        total_pages = (len(songs) - 1) // self.items_per_page + 1 if songs else 1
        total_duration = sum(s.get('duration', 0) for s in songs)
        duration_str = format_duration(total_duration)
        container = Container(accent_color=Theme.PRIMARY)
        playlists = db.get_all_playlists(self.radio.playlist_editor_user, strictly_personal=True)
        playlist_name = next((p['name'] for p in playlists if p['id'] == playlist_id), "Unknown")
        container.add_item(TextDisplay(f"**{t('playlist_editor_title')}: {playlist_name}**"))
        if not songs:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            start = page * self.items_per_page
            end = start + self.items_per_page
            page_songs = songs[start:end]
            for i, song in enumerate(page_songs, start + 1):
                info = f"**{i}. {song['artist']} - {song['title']}**"
                controls = ActionRow()
                controls.add_item(MoveSongInPlaylistButton(radio, db, playlist_id, song['path'], -1, Icons.MOVE_UP))
                controls.add_item(MoveSongInPlaylistButton(radio, db, playlist_id, song['path'], 1, Icons.MOVE_DOWN))
                controls.add_item(RemoveFromPlaylistButton(radio, db, playlist_id, song['path']))
                container.add_item(TextDisplay(info))
                container.add_item(controls)
        container.add_item(Separator())
        footer = f"{t('page')} {page + 1}/{total_pages} • {len(songs)} {t('songs')} • {duration_str}"
        container.add_item(TextDisplay(footer))
        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary, disabled=(page == 0))
        async def prev_callback(interaction):
            if await check_editor_lock(self.radio, interaction): return
            await interaction.response.defer()
            self.radio.last_editor_page -= 1
            await interaction.edit_original_response(view=PlaylistEditorView(radio, db, playlist_id, page=self.radio.last_editor_page))
        prev_btn.callback = prev_callback
        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary, disabled=(page >= total_pages - 1))
        async def next_callback(interaction):
            if await check_editor_lock(self.radio, interaction): return
            await interaction.response.defer()
            self.radio.last_editor_page += 1
            await interaction.edit_original_response(view=PlaylistEditorView(radio, db, playlist_id, page=self.radio.last_editor_page))
        next_btn.callback = next_callback
        nav_row.add_item(prev_btn)
        nav_row.add_item(next_btn)
        ctrl_row = ActionRow()
        from ui_search import SearchButton
        ctrl_row.add_item(SearchButton(radio, db))
        ctrl_row.add_item(RenamePlaylistButton(radio, db, playlist_id))
        ctrl_row.add_item(DeletePlaylistButton(radio, db, playlist_id))
        ctrl_row.add_item(ExitStudioButton(radio))
        container.add_item(nav_row)
        container.add_item(ctrl_row)
        self.add_item(container)

class HistoryView(LayoutView):
    def __init__(self, radio, db, history, total_count, page=0):
        super().__init__(timeout=None)
        self.radio = radio
        self.db = db
        self.history = history
        self.total_count = total_count
        self.page = page
        self.items_per_page = radio.config.history_items_per_page
        self.total_pages = (total_count + self.items_per_page - 1) // self.items_per_page
        self.update_view_all()

    def update_view_all(self):
        self.clear_items()
        container = Container(accent_color=Theme.BACKGROUND)
        if not self.history:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            from datetime import datetime
            date_fmt = t("date_format")
            from ui_search import AddSongButton
            for i, item in enumerate(self.history, (self.page * self.items_per_page) + 1):
                timestamp = item.get('played_at', '')
                try:
                    if isinstance(timestamp, (int, float)): time_str = datetime.fromtimestamp(timestamp).strftime(date_fmt)
                    else:
                        dt = datetime.fromisoformat(str(timestamp))
                        time_str = dt.strftime(date_fmt)
                except: time_str = str(timestamp)
                song_info = f"**{i}. {item['title']}** {item['artist']}\n*({t('played_at')} {time_str})*"
                container.add_item(Section(song_info, accessory=AddSongButton(self.radio, item)))
        container.add_item(Separator())
        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        async def prev_callback(interaction):
            await interaction.response.defer()
            self.page -= 1
            await self.refresh_data(interaction)
        prev_btn.callback = prev_callback
        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def next_callback(interaction):
            await interaction.response.defer()
            self.page += 1
            await self.refresh_data(interaction)
        next_btn.callback = next_callback
        last_btn = discord.ui.Button(label=t("last_label"), style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def last_callback(interaction):
            await interaction.response.defer()
            self.page = self.total_pages - 1
            await self.refresh_data(interaction)
        last_btn.callback = last_callback
        close_btn = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)
        async def close_callback(interaction):
            await interaction.response.defer()
            from ui import embed_state
            embed_state.save_message_id("search", None)
            self.radio.active_view_type = None
            try: await interaction.delete_original_response()
            except:
                try: await interaction.message.delete()
                except: pass
        close_btn.callback = close_callback
        nav_row.add_item(prev_btn)
        nav_row.add_item(next_btn)
        nav_row.add_item(last_btn)
        container.add_item(nav_row)
        ctrl_row = ActionRow()
        ctrl_row.add_item(HistoryFilterButton(self.radio, self.db))
        ctrl_row.add_item(DeleteHistoryButton(self.radio, self.db))
        ctrl_row.add_item(close_btn)
        container.add_item(ctrl_row)
        if self.radio.filter_from or self.radio.filter_to:
            filter_text = f"{Icons.LOCATION} {t('filter_label')}: "
            if self.radio.filter_from: filter_text += f"{t('filter_from_label').split(' ')[0]} {self.radio.filter_from} "
            if self.radio.filter_to: filter_text += f"{t('filter_to_label').split(' ')[0]} {self.radio.filter_to}"
            container.add_item(TextDisplay(f"*{filter_text}*"))
        self.add_item(container)

    async def refresh_data(self, interaction):
        self.radio.last_history_page = self.page
        self.history = self.db.get_full_history(limit=self.items_per_page, offset=self.page * self.items_per_page, filter_from=self.radio.filter_from, filter_to=self.radio.filter_to)
        self.update_view_all()
        await interaction.edit_original_response(view=self)
