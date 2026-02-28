import discord
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Section, Container, Separator, Thumbnail, TextDisplay
from pathlib import Path
from embed_state import EmbedStateManager
from scanner import get_cover_art, find_and_save_cover
import io

embed_state = EmbedStateManager()

bot = None
config = None
radio = None
db = None

def init_ui(_bot, _config, _radio, _db):
    global bot, config, radio, db
    bot = _bot
    config = _config
    radio = _radio
    db = _db

LOCALES = {
    "en": {
        "system_sync": "💠 SYSTEM SYNC",
        "synchro_subtitle": "Establish synthetic uplink frequency. \"I'm everything you want to hear.\"",
        "standby_mode": "🌌 STANDBY MODE",
        "standby_subtitle": "\"Everything you want to see. Everything you want to hear.\"\nPlease synchronize frequency to begin signal transmission.",
        "now_playing": "NOW PLAYING",
        "paused": "PAUSED",
        "idle": "IDLE",
        "artist": "Artist",
        "title": "Title",
        "album": "Album",
        "genre": "Genre",
        "duration": "Duration",
        "likes": "Likes",
        "dislikes": "Dislikes",
        "year": "Year",
        "label": "Label",
        "catnum": "#CAT",
        "source": "Source",
        "details_label": "Details",
        "up_next": "Up Next",
        "empty": "Empty",
        "tuned_by": "Uplink",
        "location": "Frequency",
        "placeholder_freq": "Select Frequency",
        "placeholder_genre": "Select Genre",
        "placeholder_lang": "Language / Nyelv",
        "syncing": "Syncing with channel frequency...",
        "severing": "Severing synthetic connection. \"Part of me stay with you?\"",
        "switching_genre": "Genre switching to:",
        "resuming": "Resuming/Replaying playback...",
        "cannot_pause_stopped": "Stopped music cannot be paused",
        "resuming_feedback": "Resuming playback...",
        "pausing": "Pausing playback...",
        "stopping": "Stopping playback...",
        "skipping": "Skipping the current track...",
        "nothing_playing": "Nothing is playing right now.",
        "cannot_seek_stopped": "Cannot seek while the radio is stopped",
        "jump_modal_title": "Jump to timestamp",
        "timestamp_input_label": "Enter timestamp (mm:ss)",
        "format_error": "Format must be mm:ss",
        "no_current_track": "There is no current track",
        "too_long": "Timestamp too long",
        "jumping": "Jumping to",
        "vol_modal_title": "Set Volume (0-100%)",
        "vol_input_label": "Volume (%)",
        "invalid_number": "Invalid number!",
        "vol_range_error": "Volume must be between 0 and 100",
        "vol_set": "Volume set to:",
        "details_info_label": "Info",
        "no_playing_error": "No song is currently playing",
        "liked": "Liked:",
        "like_withdrawn": "Like withdrawn:",
        "liked_replaced": "Liked (replaced dislike):",
        "disliked": "Disliked:",
        "dislike_withdrawn": "Dislike withdrawn:",
        "disliked_replaced": "Disliked (replaced like):",
        "record_error": "Failed to record",
        "play_label": "Play",
        "pause_label": "Pause",
        "stop_label": "Stop",
        "skip_label": "Skip",
        "seek_label": "Move To",
        "vol_label": "Vol",
        "like_label": "Like",
        "dislike_label": "Dislike",
        "details_btn_label": "Info",
        "queue_label": "Queue",
        "sever_uplink": "Sever Uplink",
        "info_visibility": "Info visibility",
        "queue_visibility": "Queue visibility",
        "shown": "Shown",
        "hidden": "Hidden"
    },
    "hu": {
        "system_sync": "💠 RENDSZER SZINKRON",
        "synchro_subtitle": "Hozzon létre szintetikus kapcsolatot. \"Én vagyok minden, amit hallani akarsz.\"",
        "standby_mode": "🌌 KÉSZENLÉTI MÓD",
        "standby_subtitle": "\"Minden, amit látni akarsz. Minden, amit hallani akarsz.\"\nKérjük, szinkronizáljon a frekvenciával az adás megkezdéséhez.",
        "now_playing": "MOST SZÓL",
        "paused": "SZÜNETELTETVE",
        "idle": "ÜRESJÁRAT",
        "artist": "Előadó",
        "title": "Cím",
        "album": "Album",
        "genre": "Stílus",
        "duration": "Hossz",
        "likes": "Kedvelések",
        "dislikes": "Nem tetszések",
        "year": "Év",
        "label": "Kiadó",
        "catnum": "Katalógus szám",
        "source": "Forrás",
        "details_label": "Részletek",
        "up_next": "Következik",
        "empty": "Üres",
        "tuned_by": "Uplink",
        "location": "Frekvencia",
        "placeholder_freq": "Válasszon frekvenciát",
        "placeholder_genre": "Válasszon stílust",
        "placeholder_lang": "Language / Nyelv",
        "syncing": "Csatlakozás a csatorna frekvenciájához...",
        "severing": "A szintetikus kapcsolat megszakítva. \"Veled maradhat egy részem?\"",
        "switching_genre": "Stílusváltás folyamatban:",
        "resuming": "Lejátszás folytatása...",
        "cannot_pause_stopped": "Megállított zene nem szüneteltethető",
        "resuming_feedback": "Lejátszás folytatása...",
        "pausing": "Lejátszás szüneteltetése...",
        "stopping": "Lejátszás megállítása...",
        "skipping": "Jelenlegi szám átlépése...",
        "nothing_playing": "Jelenleg semmi sem szól.",
        "cannot_seek_stopped": "Megállított rádiónál nem lehet tekerni",
        "jump_modal_title": "Ugrás időpontra",
        "timestamp_input_label": "Írja be az időpontot (pp:mp)",
        "format_error": "A formátum pp:mp kell legyen",
        "no_current_track": "Nincs aktuális szám az adatbázisban",
        "too_long": "Az időpont hosszabb, mint a szám",
        "jumping": "Ugrás ide",
        "vol_modal_title": "Hangerő beállítása (0-100%)",
        "vol_input_label": "Hangerő (%)",
        "invalid_number": "Érvénytelen szám!",
        "vol_range_error": "A hangerő 0 és 100 között kell legyen",
        "vol_set": "Hangerő beállítva:",
        "details_info_label": "Infó",
        "no_playing_error": "Jelenleg nem szól semmi",
        "liked": "Kedvelem:",
        "like_withdrawn": "Kedvelés visszavonva:",
        "liked_replaced": "Kedvelve (Nem tetszik cserélve):",
        "disliked": "Nem tetszik:",
        "dislike_withdrawn": "Nem tetszik visszavonva:",
        "disliked_replaced": "Nem tetszik (Kedvelve cserélve):",
        "record_error": "Sikertelen rögzítés",
        "play_label": "Lejátszás",
        "pause_label": "Szünet",
        "stop_label": "Leállítás",
        "skip_label": "Kihagyás",
        "seek_label": "Ugrás ide",
        "vol_label": "Hangerő",
        "like_label": "Tetszik",
        "dislike_label": "Nem tetszik",
        "details_btn_label": "Infó",
        "queue_label": "Lista",
        "sever_uplink": "Kapcsolat bontása",
        "info_visibility": "Infó láthatósága",
        "queue_visibility": "Lista láthatósága",
        "shown": "Megjelenítve",
        "hidden": "Elrejtve"
    }
}

def t(key):
    lang = "en"
    if radio:
        lang = radio.language
    return LOCALES.get(lang, LOCALES["en"]).get(key, key)

def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def fixed(text: str, length: int = 42):
    text = str(text)

    if len(text) > length:
        return text[:length - 3] + "..."
    
    return text.ljust(length)

def build_embed(song: dict) -> discord.Embed:
    status_title = "🎧 NOW PLAYING"
    status_color = discord.Color.blurple()

    if radio:
        if radio.status == RadioStatusEnum.PAUSED:
            status_title = "⏸️ PAUSED"
            status_color = discord.Color.gold()
        elif radio.status == RadioStatusEnum.IDLE:
            status_title = "⏹️ IDLE"
            status_color = discord.Color.red()

    embed = discord.Embed(
        title=f"{status_title} - {song.get('genre', 'Unknown').upper()}",
        color=status_color
    )

    embed.description = (
        "```md\n"
        f"{fixed(f'Artist = {song.get('artist', 'Unknown')}')}\n"
        f"{fixed(f'Title  = {song.get('title', 'Unknown')}')}\n"
        f"{fixed(f'Album  = {song.get('album', 'Unknown')}')}\n"
        "```"
    )

    embed.add_field(
        name="Rating",
        value=f"Likes: {song.get('likes', 0)} | Dislikes: {song.get('dislikes', 0)}",
        inline=True
    )

    embed.add_field(
        name="Duration",
        value=f"{format_duration(song.get('duration', 0))}",
        inline=True
    )

    if radio and radio.last_user:
        embed.set_footer(
            text=f"Tuned by {radio.last_user.display_name} • CityRadio",
            icon_url=radio.last_user.display_avatar.url
        )
    else:
        embed.set_footer(text="CityRadio • Stay online. Stay awake.")

    return embed

async def update_now_playing(song: dict):
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return


    if not radio.voice_channel_id:
        
        if radio.now_playing_message:
            try: await radio.now_playing_message.delete()
            except: pass
            radio.now_playing_message = None
            embed_state.save_message_id("player", None)

        view = UnifiedStandbyView(radio)
        if not radio.station_message:
            msg_id = embed_state.load_message_id("station")
            if msg_id:
                try: radio.station_message = await channel.fetch_message(msg_id)
                except: radio.station_message = None

        if radio.station_message:
            try: await radio.station_message.edit(view=view)
            except: radio.station_message = await channel.send(view=view)
        else:
            radio.station_message = await channel.send(view=view)
        embed_state.save_message_id("station", radio.station_message.id)
        return


    station_view = FrequencyStationView(radio)
    if not radio.station_message:
        msg_id = embed_state.load_message_id("station")
        if msg_id:
            try: radio.station_message = await channel.fetch_message(msg_id)
            except: radio.station_message = None

    if radio.station_message:
        try: await radio.station_message.edit(view=station_view)
        except: radio.station_message = await channel.send(view=station_view)
    else:
        radio.station_message = await channel.send(view=station_view)
    embed_state.save_message_id("station", radio.station_message.id)

    player_view = NowPlayingView(radio, db)
    if not radio.now_playing_message:
        msg_id = embed_state.load_message_id("player")
        if msg_id:
            try: radio.now_playing_message = await channel.fetch_message(msg_id)
            except: radio.now_playing_message = None

    file = None
    cover_path = db.get_song_cover_path(song.get("path", ""))
    if cover_path and Path(cover_path).exists():
        file = discord.File(cover_path, filename="cover.png")
    else:
        temp_path = find_and_save_cover(Path(song.get("path", "")), db)
        if temp_path:
            db.save_song_cover_path(song.get("path", ""), temp_path)
            file = discord.File(temp_path, filename="cover.png")

    if radio.now_playing_message:
        try:
            await radio.now_playing_message.edit(
                embed=None,
                view=player_view,
                attachments=[file] if file else []
            )
        except:
            radio.now_playing_message = await channel.send(view=player_view, file=file)
    else:
        radio.now_playing_message = await channel.send(view=player_view, file=file)
    embed_state.save_message_id("player", radio.now_playing_message.id)

    for key in ["queue", "details"]:
        old_id = embed_state.load_message_id(key)
        if old_id:
            try:
                m = await channel.fetch_message(old_id)
                await m.delete()
            except: pass
            embed_state.save_message_id(key, None)

def build_queue_embed(queue: list[dict], current_song: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⏭️ UP NEXT",
        color=discord.Color.dark_grey()
    )
    
    lines = []
    
    if current_song:
        artist = current_song.get("artist", "Unknown")
        title = current_song.get("title", "Unknown")
        lines.append(f"▶️ **{artist} - {title}** *(Now Playing)*")

    for i, song in enumerate(queue[:10], 1):
        artist = song.get("artist", "Unknown")
        title = song.get("title", "Unknown")
        lines.append(f"{i}. {artist} - {title}")
    
    if not lines:
        lines.append("*The queue is currently empty.*")
        
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Total songs in library: {len(db.get_all_genres())} genres")
    
    return embed

async def force_new_embed():
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    for key in ["player", "station", "queue", "details"]:
        msg_id = embed_state.load_message_id(key)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except: pass
            embed_state.save_message_id(key, None)

    radio.now_playing_message = None
    radio.station_message = None
    radio.queue_message = None
    radio.details_message = None

    await update_now_playing(radio.current_song or {})

class UnifiedStandbyView(discord.ui.LayoutView):
    def __init__(self, radio):
        super().__init__(timeout=None)
        self.radio = radio

        station_container = Container(accent_color=0x2b2d31)
        station_container.add_item(TextDisplay(f"## {t('system_sync')}\n{t('synchro_subtitle')}"))
        
        guild = bot.get_guild(config.guild_id)
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
        
        guild = bot.get_guild(config.guild_id)
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

        meta_row = ActionRow()
        meta_row.add_item(VolumeButton(radio))
        meta_row.add_item(LikeButton(radio, db))
        meta_row.add_item(DislikeButton(radio, db))
        meta_row.add_item(DetailsButton(radio))
        meta_row.add_item(QueueToggleButton(radio))
        master_container.add_item(meta_row)

        self.add_item(master_container)

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
        self.radio.dispatch(RadioAction.JOIN, channel_id, user=interaction.user)
        
        await interaction.response.send_message(
            t("syncing"),
            ephemeral=True
        )

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
        await interaction.response.send_message(
            t("severing"),
            ephemeral=True
        )

def build_detailed_embed(song: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📂 {t('details_label').upper()}",
        color=discord.Color.blue()
    )

    date = song.get('date', 'Unknown')
    label = song.get('label', 'Unknown')
    catnum = song.get('catnum', 'Unknown')

    media_type = song.get('mediatype_flac') or song.get('mediatype_mp3') or 'Unknown'

    embed.description = (
        "```md\n"
        f"{fixed(f'{t('artist')} = {song.get('artist', 'Unknown')}')}\n"
        f"{fixed(f'{t('title')}  = {song.get('title', 'Unknown')}')}\n"
        f"{fixed(f'{t('album')}  = {song.get('album', 'Unknown')}')}\n"
        f"{fixed(f'{t('year')}   = {date}')}\n"
        f"{fixed(f'{t('label')}  = {label}')}\n"
        f"{fixed(f'{t('catnum')} = {catnum}')}\n"
        f"{fixed(f'{t('source')} = {media_type}')}\n"
        f"{fixed(f'{t('duration')} = {format_duration(song.get('duration', 0))}')}\n"
        "```"
    )

    embed.set_footer(text="CityRadio Database Explorer")
    return embed

class GenreSelect(discord.ui.Select):
    def __init__(self, radio, db):
        self.radio = radio
        self.db = db

        genres = db.get_all_genres()
        genres.append("levifav")

        options = [
            discord.SelectOption(
                label=g.upper(),
                value=g
            )
            for g in genres
        ]

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

        await interaction.response.send_message(
            f"{t('switching_genre')} **{selected.upper()}**",
            ephemeral=True
        )

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
        await interaction.response.send_message(
            t("resuming"),
            ephemeral=True
        )

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
            await interaction.response.send_message(
                t("cannot_pause_stopped"),
                ephemeral=True
            )
            return

        if self.radio.status == RadioStatusEnum.PAUSED:
            self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
            await interaction.response.send_message(
                t("resuming_feedback"),
                ephemeral=True
            )
        else:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await interaction.response.send_message(
                t("pausing"),
                ephemeral=True
            )

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
        await interaction.response.send_message(
            t("stopping"),
            ephemeral=True
        )

class SkipButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=f"⏭ {t('skip_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="skip_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.SKIP, user=interaction.user)

            await interaction.response.send_message(
                t("skipping"),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t("nothing_playing"),
                ephemeral=True
            )

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
            await interaction.response.send_message(
                t("cannot_seek_stopped"),
                ephemeral=True
            )
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
            await interaction.response.send_message(
                t("format_error"),
                ephemeral=True
            )
            return

        if not self.radio.current_song:
            await interaction.response.send_message(
                t("no_current_track"),
                ephemeral=True
            )
            return

        duration = self.radio.current_song.get("duration", 0)

        if total_seconds >= duration:
            await interaction.response.send_message(
                t("too_long"),
                ephemeral=True
            )
            return

        self.radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)

        await interaction.response.send_message(
            f"{t('jumping')} {ts}...",
            ephemeral=True
        )

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
            await interaction.response.send_message(
                t("invalid_number"),
                ephemeral=True
            )
            return

        if value < 0 or value > 100:
            await interaction.response.send_message(
                t("vol_range_error"),
                ephemeral=True
            )
            return

        self.radio.dispatch(RadioAction.SET_VOLUME, value / 100, user=interaction.user)

        await interaction.response.send_message(
            f"{t('vol_set')} {value}%",
            ephemeral=True
        )

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
            await interaction.response.send_message(
                t("no_playing_error"),
                ephemeral=True
            )
            return

        song_path = self.radio.current_song.get("path")

        song_path = self.radio.current_song.get("path")

        try:
            status = self.db.toggle_rating(interaction.user.id, song_path, 'like')
            
            updated_song = self.db.get_song_by_path(song_path)
            if updated_song:
                self.radio.last_user = interaction.user
                self.radio.current_song = updated_song
                await update_now_playing(updated_song)

            artist = updated_song.get("artist") or "Unknown Artist"
            title = updated_song.get("title") or "Unknown Title"

            if status == "added":
                msg = f"{t('liked')} **{artist} - {title}**"
            elif status == "removed":
                msg = f"{t('like_withdrawn')} **{artist} - {title}**"
            else:
                msg = f"{t('liked_replaced')} **{artist} - {title}**"

            await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            print(f"Like error: {e}")
            await interaction.response.send_message(
                t("record_error"),
                ephemeral=True
            )

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
            await interaction.response.send_message(
                 t("no_playing_error"),
                ephemeral=True
            )
            return

        song_path = self.radio.current_song.get("path")

        try:
            status = self.db.toggle_rating(interaction.user.id, song_path, 'dislike')
            
            updated_song = self.db.get_song_by_path(song_path)
            if updated_song:
                self.radio.last_user = interaction.user
                self.radio.current_song = updated_song
                await update_now_playing(updated_song)

            artist = updated_song.get("artist") or "Unknown Artist"
            title = updated_song.get("title") or "Unknown Title"

            if status == "added":
                msg = f"{t('disliked')} **{artist} - {title}**"
            elif status == "removed":
                msg = f"{t('dislike_withdrawn')} **{artist} - {title}**"
            else:
                msg = f"{t('disliked_replaced')} **{artist} - {title}**"

            await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            print(f"Dislike error: {e}")
            await interaction.response.send_message(
                t("record_error"),
                ephemeral=True
                )

class DetailsButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=f"📂 {t('details_btn_label')}",
            style=discord.ButtonStyle.secondary,
            custom_id="details_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.show_details = not self.radio.show_details
        
        await update_now_playing(self.radio.current_song)
        
        await interaction.response.send_message(
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
        self.radio.show_queue = not self.radio.show_queue
        
        await update_now_playing(self.radio.current_song)
        
        await interaction.response.send_message(
            f"📋 {t('queue_visibility')}: **{t('shown') if self.radio.show_queue else t('hidden')}**",
            ephemeral=True
        )