import discord
from discord.ui import LayoutView, ActionRow, Container, Section, TextDisplay, Thumbnail, Separator
from pathlib import Path
from ui_translate import t
from ui_utils import format_duration, fixed
from radio_actions import RadioState as RadioStatusEnum, RadioAction
from ui_components import (
    StationSelect, LanguageSelect, DisconnectButton, GenreSelect, 
    PlayButton, PauseButton, StopButton, SkipButton, SeekButton, 
    VolumeButton, LikeButton, DislikeButton, DetailsButton, 
    QueueToggleButton, SearchButton, AddSongButton, QueueAllButton
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
            for i, q_song in enumerate(radio.queue[:5], 1):
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
        playback_row.add_item(PlayButton(radio))
        playback_row.add_item(PauseButton(radio))
        playback_row.add_item(StopButton(radio))
        playback_row.add_item(SkipButton(radio))
        playback_row.add_item(SeekButton(radio))
        master_container.add_item(playback_row)

        meta_row_1 = ActionRow()
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
    def __init__(self, radio, db, results, query, user, page=0):
        super().__init__(timeout=180)
        self.radio = radio
        self.db = db
        self.results = results
        self.query = query
        self.user = user
        self.page = page
        self.language = radio.language
        self.items_per_page = 5
        self.total_pages = (len(results) - 1) // self.items_per_page + 1

        print(f"[SEARCH VIEW] Initializing. Radio lang: {self.radio.language}, Translation test ('songs_tab'): {t('songs_tab')}")

        container = Container(accent_color=0x2b2d31)
        
        tab_row = ActionRow()
        tab_row.add_item(discord.ui.Button(label=t("songs_tab"), style=discord.ButtonStyle.primary, custom_id="songs_tab", disabled=True))
        tab_row.add_item(discord.ui.Button(label=t("artists_tab"), style=discord.ButtonStyle.secondary, custom_id="artists_tab", disabled=True))
        tab_row.add_item(discord.ui.Button(label=t("albums_tab"), style=discord.ButtonStyle.secondary, custom_id="albums_tab", disabled=True))
        tab_row.add_item(discord.ui.Button(label=t("playlists_tab"), style=discord.ButtonStyle.secondary, custom_id="playlists_tab", disabled=True))
        
        close_btn = discord.ui.Button(emoji="❌", style=discord.ButtonStyle.secondary, custom_id="close_search")
        async def close_callback(interaction):
             from ui import embed_state
             embed_state.save_message_id("search", None)
             await interaction.message.delete()
        close_btn.callback = close_callback
        tab_row.add_item(close_btn)
        container.add_item(tab_row)
        container.add_item(Separator())

        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_results = self.results[start:end]

        for i, song in enumerate(page_results, start + 1):
            song_info = f"**{i}. {song['title']}**{song['artist']} • {format_duration(song['duration'])}"
            section = Section(song_info, accessory=AddSongButton(radio, song))
            container.add_item(section)

        container.add_item(Separator())
        
        footer_text = f"{t('page')} {self.page + 1}/{self.total_pages} • {len(results)} {t('results')} • {t('initiated_by')} {user.mention}"
        container.add_item(TextDisplay(footer_text))

        nav_row = ActionRow()
        
        prev_btn = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
        async def prev_callback(interaction):
            self.page -= 1
            await self.update_view(interaction)
        prev_btn.callback = prev_callback
        nav_row.add_item(prev_btn)

        next_btn = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def next_callback(interaction):
            self.page += 1
            await self.update_view(interaction)
        next_btn.callback = next_callback
        nav_row.add_item(next_btn)
        
        last_btn = discord.ui.Button(label=t("last_label"), style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        async def last_callback(interaction):
            self.page = self.total_pages - 1
            await self.update_view(interaction)
        last_btn.callback = last_callback
        nav_row.add_item(last_btn)

        nav_row.add_item(QueueAllButton(radio, results))
        
        reset_btn = discord.ui.Button(label=t("reset_radio_label"), emoji="🔄", style=discord.ButtonStyle.secondary)
        async def reset_callback(interaction):
             self.radio.queue = []
             self.radio.dispatch(RadioAction.SKIP, user=interaction.user)
             await interaction.response.send_message(t("radio_reset_feedback"), ephemeral=True)
        reset_btn.callback = reset_callback
        nav_row.add_item(reset_btn)

        container.add_item(nav_row)
        self.add_item(container)

    async def update_view(self, interaction):
        new_view = SearchResultsView(self.radio, self.db, self.results, self.query, self.user, self.page)
        await interaction.response.edit_message(view=new_view)
