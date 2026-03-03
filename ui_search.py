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

class SearchButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label=None if radio.is_compact else t('search_label'),
            emoji=Icons.SEARCH,
            style=discord.ButtonStyle.secondary,
            custom_id="search_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if self.radio.editing_playlist_id:
            if await check_editor_lock(self.radio, interaction): return
        modal = SearchModal(self.radio, self.db)
        await interaction.response.send_modal(modal)

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
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(
            emoji=Icons.ADD,
            style=discord.ButtonStyle.secondary,
            custom_id=f"add_song_{song['id']}_{unique}"
        )
        self.radio = radio
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        if self.radio.editing_playlist_id:
            if await check_editor_lock(self.radio, interaction): return
            await interaction.response.defer(ephemeral=True)
            from database import DatabaseManager
            db = DatabaseManager()
            db.add_song_to_playlist(self.radio.editing_playlist_id, self.song['path'])
            await interaction.followup.send(f"{t('song_added_to_playlist')} **{self.song['artist']} - {self.song['title']}**", ephemeral=True)
            
            search_id = self.radio.embed_manager.load_message_id("search")
            if search_id:
                try:
                    msg = await interaction.channel.fetch_message(search_id)
                    if self.radio.active_view_type == "search":
                        view = SearchResultsView(self.radio, db, self.radio.last_search_results, self.radio.last_search_query, self.radio.last_search_user, page=self.radio.last_search_page, search_type=self.radio.last_search_type)
                        await msg.edit(view=view)
                    elif self.radio.active_view_type in ["playlist_editor", "studio"]:
                        from ui_studio import PlaylistEditorView
                        view = PlaylistEditorView(self.radio, db, self.radio.editing_playlist_id, page=self.radio.last_editor_page)
                        await msg.edit(view=view)
                except Exception as e:
                    print(f"DEBUG: Refresh failed: {e}")
        else:
            await interaction.response.defer(ephemeral=True)
            self.radio.dispatch(RadioAction.ADD_TO_QUEUE, self.song, user=interaction.user)
            await interaction.followup.send(f"{t('add_to_queue')} **{self.song['artist']} - {self.song['title']}**", ephemeral=True)

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
        if self.radio.editing_playlist_id:
            if await check_editor_lock(self.radio, interaction): return
        from ui import init_translate
        init_translate(self.radio)
        await interaction.response.defer()
        
        results = []
        if self.search_type == "songs": results = self.db.search_songs(self.query)
        elif self.search_type == "artists": results = self.db.search_artists(self.query)
        elif self.search_type == "albums": results = self.db.search_albums(self.query)
        elif self.search_type == "playlists": results = self.db.get_all_playlists(self.user.id)
            
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
        if self.radio.editing_playlist_id:
            if await check_editor_lock(self.radio, interaction): return
        from ui import init_translate
        init_translate(self.radio)
        await interaction.response.defer()
        
        results = []
        new_search_type = "songs"
        if self.search_type == "artist_songs": results = self.db.search_by_artist(self.value)
        elif self.search_type == "artist_albums":
            results = self.db.get_albums_by_artist(self.value)
            new_search_type = "albums"
        elif self.search_type == "album_songs": results = self.db.search_by_album(self.value[0], self.value[1])
        elif self.search_type == "playlist_songs":
            results = self.db.get_playlist_songs(self.value)
            new_search_type = "songs"
            
        view = SearchResultsView(self.radio, self.db, results, str(self.value), self.user, search_type=new_search_type, original_query=self.original_query)
        await interaction.edit_original_response(view=view)

class QueueAllButton(discord.ui.Button):
    def __init__(self, radio, songs):
        label = t("add_all") if radio.editing_playlist_id else t("queue_all")
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id="queue_all_button")
        self.radio = radio
        self.songs = songs

    async def callback(self, interaction: discord.Interaction):
        from ui import init_translate
        init_translate(self.radio)
        if self.radio.editing_playlist_id:
            if await check_editor_lock(self.radio, interaction): return
            await interaction.response.defer(ephemeral=True)
            from database import DatabaseManager
            db = DatabaseManager()
            for song in self.songs:
                db.add_song_to_playlist(self.radio.editing_playlist_id, song['path'])
            await interaction.followup.send(t('bulk_added_to_playlist').format(count=len(self.songs)), ephemeral=True)
            
            search_id = self.radio.embed_manager.load_message_id("search")
            if search_id:
                try:
                    msg = await interaction.channel.fetch_message(search_id)
                    if self.radio.active_view_type == "search":
                        view = SearchResultsView(self.radio, db, self.radio.last_search_results, self.radio.last_search_query, self.radio.last_search_user, page=self.radio.last_search_page, search_type=self.radio.last_search_type)
                        await msg.edit(view=view)
                    elif self.radio.active_view_type in ["playlist_editor", "studio"]:
                        from ui_studio import PlaylistEditorView
                        view = PlaylistEditorView(self.radio, db, self.radio.editing_playlist_id, page=self.radio.last_editor_page)
                        await msg.edit(view=view)
                except: pass
        else:
            await interaction.response.defer(ephemeral=True)
            for song in self.songs:
                self.radio.dispatch(RadioAction.ADD_TO_QUEUE, song, user=interaction.user)
            await interaction.followup.send(t('bulk_added_to_queue').format(count=len(self.songs)), ephemeral=True)

class QueueViewButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(label=None if radio.is_compact else t('full_queue_label'), emoji=Icons.FULL_LIST, style=discord.ButtonStyle.secondary, custom_id="full_queue_view")
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.active_view_type = "queue"
        self.radio.last_queue_page = 0
        view = FullQueueView(self.radio, page=0)
        from ui import embed_state
        search_id = embed_state.load_message_id("search")
        if search_id:
            try:
                msg = await interaction.channel.fetch_message(search_id)
                await msg.delete()
            except: pass
        msg = await interaction.followup.send(view=view, wait=True)
        embed_state.save_message_id("search", msg.id)

class RemoveFromQueueButton(discord.ui.Button):
    def __init__(self, radio, song):
        import random, string
        unique = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary, custom_id=f"remove_q_{song.get('id', 0)}_{unique}")
        self.radio = radio
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.REMOVE_FROM_QUEUE, self.song, user=interaction.user)
        await interaction.response.send_message(t("song_removed_feedback"), ephemeral=True)

# Views
class SearchResultsView(LayoutView):
    def __init__(self, radio, db, results, query, user, page=0, search_type="songs", original_query=None):
        super().__init__(timeout=None)
        self.radio = radio
        self.db = db
        self.results = results
        self.query = query
        self.original_query = original_query or query
        self.user = user
        self.page = page
        self.search_type = search_type
        self.items_per_page = radio.config.search_items_per_page
        self.total_pages = (len(results) - 1) // self.items_per_page + 1 if results else 1
        
        self.existing_paths = set()
        if self.radio.editing_playlist_id:
            playlist_songs = self.db.get_playlist_songs(self.radio.editing_playlist_id)
            self.existing_paths = {s['path'] for s in playlist_songs}

        self.radio.active_view_type = "search"
        container = Container(accent_color=Theme.BACKGROUND)
        
        tab_row = ActionRow()
        tab_row.add_item(TabButton(radio, db, t("songs_tab"), "songs", self.original_query, user, active=(search_type == "songs")))
        tab_row.add_item(TabButton(radio, db, t("artists_tab"), "artists", self.original_query, user, active=(search_type == "artists")))
        tab_row.add_item(TabButton(radio, db, t("albums_tab"), "albums", self.original_query, user, active=(search_type == "albums")))
        tab_row.add_item(TabButton(radio, db, t("playlists_tab"), "playlists", self.original_query, user, active=(search_type == "playlists")))
        
        close_btn = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)
        async def close_callback(interaction):
             if self.radio.editing_playlist_id:
                 if await check_editor_lock(self.radio, interaction): return
             await interaction.response.defer()
             from ui import embed_state
             embed_state.save_message_id("search", None)
             await interaction.message.delete()
        close_btn.callback = close_callback
        tab_row.add_item(close_btn)
        container.add_item(tab_row)

        if self.radio.editing_playlist_id:
            playlists = self.db.get_all_playlists()
            playlist_name = next((p['name'] for p in playlists if p['id'] == self.radio.editing_playlist_id), "...")
            container.add_item(TextDisplay(f"{Icons.STATUS} **{playlist_name}** ({len(self.existing_paths)} {t('songs')})"))
            container.add_item(Separator())

        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_results = self.results[start:end]

        if not page_results:
            container.add_item(TextDisplay(f"*{t('search_no_results')}*"))
        else:
            for i, item in enumerate(page_results, start + 1):
                if self.search_type == "songs":
                    is_added = item['path'] in self.existing_paths
                    song_info = f"**{i}. {item['title']}** {item['artist']} • {format_duration(item['duration'])}"
                    btn = AddSongButton(radio, item)
                    if is_added:
                        btn.emoji = Icons.SUCCESS
                        btn.style = discord.ButtonStyle.success
                    container.add_item(Section(song_info, accessory=btn))
                elif self.search_type == "artists":
                    container.add_item(TextDisplay(f"**{i}. {item}**"))
                    row = ActionRow()
                    row.add_item(SearchBySelectionButton(radio, db, t("songs_tab"), "artist_songs", item, user, original_query=self.original_query))
                    row.add_item(SearchBySelectionButton(radio, db, t("albums_tab"), "artist_albums", item, user, original_query=self.original_query))
                    container.add_item(row)
                elif self.search_type == "albums":
                    album_info = f"**{i}. {item['album']}** {item['artist']}"
                    container.add_item(Section(album_info, accessory=SearchBySelectionButton(radio, db, t("songs_tab"), "album_songs", (item['artist'], item['album']), user, original_query=self.original_query)))
                elif self.search_type == "playlists":
                    is_owned = item.get('user_id') == self.user.id
                    prefix = f"{Icons.USER} " if is_owned else ""
                    playlist_info = f"**{i}. {prefix}{item['name']}**"
                    container.add_item(Section(playlist_info, accessory=SearchBySelectionButton(radio, db, t("songs_tab"), "playlist_songs", item['id'], user, original_query=self.original_query)))

        container.add_item(Separator())
        footer_text = f"{t('page')} {self.page + 1}/{self.total_pages} • {len(results)} {t('results')} • {t('initiated_by')} {user.mention}"
        container.add_item(TextDisplay(footer_text))

        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        async def prev_callback(interaction):
            await interaction.response.defer()
            self.page -= 1
            await self.update_view(interaction)
        prev_btn.callback = prev_callback
        nav_row.add_item(prev_btn)

        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def next_callback(interaction):
            await interaction.response.defer()
            self.page += 1
            await self.update_view(interaction)
        next_btn.callback = next_callback
        nav_row.add_item(next_btn)
        
        nav_row.add_item(QueueAllButton(radio, results))
        
        if self.radio.editing_playlist_id:
            from ui_studio import BackToEditorButton
            nav_row.add_item(BackToEditorButton(radio))

        container.add_item(nav_row)
        self.add_item(container)

    async def update_view(self, interaction):
        self.radio.last_search_page = self.page
        self.radio.last_search_type = self.search_type
        new_view = SearchResultsView(self.radio, self.db, self.results, self.query, self.user, self.page, self.search_type, original_query=self.original_query)
        await interaction.edit_original_response(view=new_view)

class FullQueueView(LayoutView):
    def __init__(self, radio, page=0):
        super().__init__(timeout=None)
        self.radio = radio
        self.page = page
        self.items_per_page = radio.config.queue_items_per_page
        self.queue_list = radio.queue
        self.total_pages = (len(self.queue_list) - 1) // self.items_per_page + 1 if self.queue_list else 1
        
        container = Container(accent_color=Theme.PRIMARY)
        if not self.queue_list:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            start = self.page * self.items_per_page
            end = start + self.items_per_page
            page_results = self.queue_list[start:end]
            for i, song in enumerate(page_results, start + 1):
                song_info = f"**{i}. {song['artist']} - {song['title']}**"
                container.add_item(Section(song_info, accessory=RemoveFromQueueButton(radio, song)))
        
        container.add_item(Separator())
        footer = f"{t('page')} {self.page + 1}/{self.total_pages} • {len(self.queue_list)} {t('songs')}"
        container.add_item(TextDisplay(footer))
        
        nav_row = ActionRow()
        prev_btn = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        async def prev_callback(interaction):
            await interaction.response.defer()
            self.page -= 1
            await self.refresh_view(interaction)
        prev_btn.callback = prev_callback
        
        next_btn = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def next_callback(interaction):
            await interaction.response.defer()
            self.page += 1
            await self.refresh_view(interaction)
        next_btn.callback = next_callback
        
        close_btn = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)
        async def close_callback(interaction):
            await interaction.response.defer()
            from ui import embed_state
            embed_state.save_message_id("search", None)
            self.radio.active_view_type = None
            try: await interaction.message.delete()
            except: pass
        close_btn.callback = close_callback
        
        nav_row.add_item(prev_btn)
        nav_row.add_item(next_btn)
        nav_row.add_item(close_btn)
        container.add_item(nav_row)
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = FullQueueView(self.radio, page=self.page)
        await interaction.edit_original_response(view=new_view)
