import discord
from discord.ui import LayoutView, ActionRow, Container, Section, TextDisplay, Thumbnail, Separator
from pathlib import Path
from ui_translate import t
from ui_utils import format_duration, fixed
from radio_actions import RadioState as RadioStatusEnum, RadioAction
from ui_components import (
    StationSelect, LanguageSelect, DisconnectButton, GenreSelect, 
    PlayButton, PauseButton, StopButton, ForwardButton, RandomButton, BackButton, SeekButton, 
    VolumeButton, LikeButton, DislikeButton, DetailsButton, 
    QueueToggleButton, SearchButton, AddSongButton, QueueAllButton,
    TabButton, SearchBySelectionButton
)

_bot_ref = None
_config_ref = None

def init_views(bot, config):
    global _bot_ref, _config_ref
    _bot_ref = bot
    _config_ref = config

class UnifiedStandbyView(discord.ui.LayoutView):
    def __init__(self, radio):
        super().__init__(timeout=None)
        self.radio = radio

        station_container = Container(accent_color=0x2b2d31)
        station_container.add_item(TextDisplay(f"## {t('system_sync')}\n{t('synchro_subtitle')}"))
        
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if guild:
            afk_id = 1275929869703970876
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row = ActionRow()
            row.add_item(StationSelect(radio, v_channels))
            station_container.add_item(row)
            
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio))
            station_container.add_item(row_lang)
        self.add_item(station_container)

        standby_container = Container(accent_color=0x2b2d31)
        standby_container.add_item(TextDisplay(f"## {t('standby_mode')}\n{t('standby_subtitle')}"))
        self.add_item(standby_container)

class FrequencyStationView(discord.ui.LayoutView):
    def __init__(self, radio):
        super().__init__(timeout=None)
        self.radio = radio

        station_container = Container(accent_color=0x2b2d31)
        station_container.add_item(TextDisplay(f"## {t('system_sync')}\n{t('synchro_subtitle')}"))
        
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if guild:
            afk_id = 1275929869703970876
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row = ActionRow()
            row.add_item(StationSelect(radio, v_channels))
            station_container.add_item(row)
            
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio))
            station_container.add_item(row_lang)
            
            row_meta = ActionRow()
            row_meta.add_item(DisconnectButton(radio))
            station_container.add_item(row_meta)
        
        self.add_item(station_container)

class NowPlayingView(discord.ui.LayoutView):
    def __init__(self, radio, db):
        super().__init__(timeout=None)
        song = radio.current_song or {}

        accent_color = 0x5865F2
        status_key = "now_playing"
        status_emoji = "🎧"
        if radio.status == RadioStatusEnum.PAUSED:
            status_key = "paused"
            status_emoji = "⏸️"
            accent_color = 0xFEE75C
        elif radio.status == RadioStatusEnum.IDLE:
            status_key = "idle"
            status_emoji = "⏹️"
            accent_color = 0xED4245
        status_title = f"{status_emoji} {t(status_key)}"

        master_container = Container(accent_color=accent_color)
        
        cover_path = db.get_song_cover_path(song.get("path", ""))
        thumb = None
        if cover_path and Path(cover_path).exists():
            thumb = Thumbnail(f"attachment://cover.png")

        truncated_artist = fixed(song.get('artist', 'Unknown'), 36).strip()
        truncated_title  = fixed(song.get('title', 'Unknown'), 36).strip()
        truncated_album  = fixed(song.get('album', 'Unknown'), 36).strip()
        channel_mention = f"<#{radio.voice_channel_id}>"

        info_lines = [
            f"## {status_title}",
            f"**{t('artist')}:** {truncated_artist}",
            f"**{t('title')}:** {truncated_title}",
            f"**{t('album')}:** {truncated_album}",
            f"**{t('genre')}:** {song.get('genre', 'Unknown').upper()}",
            f"**{t('duration')}:** {format_duration(song.get('duration', 0))}",
            f"**{t('likes')}:** {song.get('likes', 0)} | **{t('dislikes')}:** {song.get('dislikes', 0)}"
        ]

        if radio.show_details:
            info_lines.append(f"\n**📂 {t('details_label')}**")
            info_lines.append(f"**{t('year')}:** {song.get('date', 'Unknown')}")
            info_lines.append(f"**{t('label')}:** {song.get('label', 'Unknown')}")
            info_lines.append(f"**{t('catnum')}:** {song.get('catnum', 'Unknown')}")
            info_lines.append(f"**{t('source')}:** {song.get('mediatype_flac') or song.get('mediatype_mp3') or 'Unknown'}")

        if radio.show_queue:
            info_lines.append(f"\n**📋 {t('up_next')}**")
            q_list = []
            display_queue = radio.get_display_queue()
            for i, q_song in enumerate(display_queue[:5], 1):
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
        meta_row_1.add_item(SeekButton(radio))
        meta_row_1.add_item(LikeButton(radio, db))
        meta_row_1.add_item(DislikeButton(radio, db))
        meta_row_1.add_item(SearchButton(radio, db))
        master_container.add_item(meta_row_1)

        meta_row_2 = ActionRow()
        meta_row_2.add_item(VolumeButton(radio))
        meta_row_2.add_item(DetailsButton(radio))
        meta_row_2.add_item(QueueToggleButton(radio))
        master_container.add_item(meta_row_2)

        self.add_item(master_container)

class SearchResultsView(discord.ui.LayoutView):
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
        self.language = radio.language
        self.items_per_page = 5
        self.total_pages = (len(results) - 1) // self.items_per_page + 1 if results else 1

        print(f"[SEARCH VIEW] Initializing. Radio lang: {self.radio.language}, Translation test ('songs_tab'): {t('songs_tab')}")

        container = Container(accent_color=0x2b2d31)
        
        tab_row = ActionRow()
        tab_row.add_item(TabButton(radio, db, t("songs_tab"), "songs", self.original_query, user, active=(search_type == "songs" and query == self.original_query)))
        tab_row.add_item(TabButton(radio, db, t("artists_tab"), "artists", self.original_query, user, active=(search_type == "artists" and query == self.original_query)))
        tab_row.add_item(TabButton(radio, db, t("albums_tab"), "albums", self.original_query, user, active=(search_type == "albums" and query == self.original_query)))
        tab_row.add_item(discord.ui.Button(label=t("playlists_tab"), style=discord.ButtonStyle.secondary, disabled=True))
        
        close_btn = discord.ui.Button(emoji="❌", style=discord.ButtonStyle.secondary, custom_id="close_search")
        async def close_callback(interaction):
             await interaction.response.defer()
             from ui import embed_state
             embed_state.save_message_id("search", None)
             await interaction.message.delete()
        close_btn.callback = close_callback
        tab_row.add_item(close_btn)
        container.add_item(tab_row)
        container.add_item(Separator())

        if not self.results:
            container.add_item(TextDisplay(f"*{t('search_no_results')}*"))
        else:
            start = self.page * self.items_per_page
            end = start + self.items_per_page
            page_results = self.results[start:end]

            for i, item in enumerate(page_results, start + 1):
                if self.search_type == "songs":
                    song_info = f"**{i}. {item['title']}** {item['artist']} • {format_duration(item['duration'])}"
                    section = Section(song_info, accessory=AddSongButton(radio, item))
                    container.add_item(section)
                elif self.search_type == "artists":
                    container.add_item(TextDisplay(f"**{i}. {item}**"))
                    row = ActionRow()
                    row.add_item(SearchBySelectionButton(radio, db, t("songs_tab"), "artist_songs", item, user, original_query=self.original_query))
                    row.add_item(SearchBySelectionButton(radio, db, t("albums_tab"), "artist_albums", item, user, original_query=self.original_query))
                    container.add_item(row)
                elif self.search_type == "albums":
                    album_info = f"**{i}. {item['album']}** {item['artist']}"
                    section = Section(album_info, accessory=SearchBySelectionButton(radio, db, t("songs_tab"), "album_songs", (item['artist'], item['album']), user, original_query=self.original_query))
                    container.add_item(section)

        container.add_item(Separator())
        
        footer_text = f"{t('page')} {self.page + 1}/{self.total_pages} • {len(results)} {t('results')} • {t('initiated_by')} {user.mention}"
        container.add_item(TextDisplay(footer_text))

        nav_row = ActionRow()
        
        prev_btn = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        async def prev_callback(interaction):
            await interaction.response.defer()
            self.page -= 1
            await self.update_view(interaction, use_followup=True)
        prev_btn.callback = prev_callback
        nav_row.add_item(prev_btn)

        next_btn = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def next_callback(interaction):
            await interaction.response.defer()
            self.page += 1
            await self.update_view(interaction, use_followup=True)
        next_btn.callback = next_callback
        nav_row.add_item(next_btn)
        
        last_btn = discord.ui.Button(label=t("last_label"), style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def last_callback(interaction):
            await interaction.response.defer()
            self.page = self.total_pages - 1
            await self.update_view(interaction, use_followup=True)
        last_btn.callback = last_callback
        nav_row.add_item(last_btn)

        nav_row.add_item(QueueAllButton(radio, results))
        
        reset_btn = discord.ui.Button(label=t("reset_radio_label"), emoji="🔄", style=discord.ButtonStyle.secondary)
        async def reset_callback(interaction):
             await interaction.response.defer(ephemeral=True)
             self.radio.queue = []
             self.radio.dispatch(RadioAction.SKIP, user=interaction.user)
             await interaction.followup.send(t("radio_reset_feedback"), ephemeral=True)
        reset_btn.callback = reset_callback
        nav_row.add_item(reset_btn)

        container.add_item(nav_row)
        self.add_item(container)

    async def update_view(self, interaction, use_followup=False):
        new_view = SearchResultsView(self.radio, self.db, self.results, self.query, self.user, self.page, self.search_type, original_query=self.original_query)
        if use_followup:
            await interaction.edit_original_response(view=new_view)
        else:
            await interaction.response.edit_message(view=new_view)
