import discord
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from discord.ui import Modal, TextInput
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

    player_embed = build_embed(song)
    queue_embed = build_queue_embed(radio.queue, song)

    if not radio.now_playing_message:
        message_id = embed_state.load_message_id("player")
        if message_id:
            try:
                radio.now_playing_message = await channel.fetch_message(message_id)
            except:
                radio.now_playing_message = None

    if radio.now_playing_message:
        try:
            await radio.now_playing_message.edit(
                embed=player_embed,
                view=RadioControlView(radio, db)
            )
        except:
            radio.now_playing_message = None
            
    if not radio.now_playing_message:
        view = RadioControlView(radio, db)
        msg = await channel.send(embed=player_embed, view=view)
        radio.now_playing_message = msg
        embed_state.save_message_id("player", msg.id)

    if radio.show_queue:
        if not radio.queue_message:
            message_id = embed_state.load_message_id("queue")
            if message_id:
                try:
                    radio.queue_message = await channel.fetch_message(message_id)
                except:
                    radio.queue_message = None

        if radio.queue_message:
            try:
                await radio.queue_message.edit(embed=queue_embed)
            except:
                radio.queue_message = None

        if not radio.queue_message:
            msg = await channel.send(embed=queue_embed)
            radio.queue_message = msg
            embed_state.save_message_id("queue", msg.id)
    else:
        if radio.queue_message:
            try:
                await radio.queue_message.delete()
            except:
                pass
            radio.queue_message = None
            
        old_queue_id = embed_state.load_message_id("queue")
        if old_queue_id:
            try:
                m = await channel.fetch_message(old_queue_id)
                await m.delete()
            except:
                pass

    if radio.show_details:
        detailed_embed = build_detailed_embed(song)
        
        cover_path = db.get_song_cover_path(song["path"])
        file = None
        if cover_path and Path(cover_path).exists():
            file = discord.File(cover_path, filename="cover.png")
            detailed_embed.set_image(url="attachment://cover.png")
        else:
            temp_path = find_and_save_cover(Path(song["path"]), db)
            if temp_path:
                db.save_song_cover_path(song["path"], temp_path)
                file = discord.File(temp_path, filename="cover.png")
                detailed_embed.set_image(url="attachment://cover.png")

        if not radio.details_message:
            message_id = embed_state.load_message_id("details")
            if message_id:
                try:
                    radio.details_message = await channel.fetch_message(message_id)
                except:
                    radio.details_message = None

        if radio.details_message:
            try:
                await radio.details_message.edit(embed=detailed_embed, attachments=[file] if file else [])
            except:
                radio.details_message = None

        if not radio.details_message:
            msg = await channel.send(embed=detailed_embed, file=file)
            radio.details_message = msg
            embed_state.save_message_id("details", msg.id)
    else:
        if radio.details_message:
            try:
                await radio.details_message.delete()
            except:
                pass
            radio.details_message = None
            
        old_details_id = embed_state.load_message_id("details")
        if old_details_id:
            try:
                m = await channel.fetch_message(old_details_id)
                await m.delete()
            except:
                pass

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

    old_player_id = embed_state.load_message_id("player")
    if old_player_id:
        try:
            old_msg = await channel.fetch_message(old_player_id)
            await old_msg.delete()
        except:
            pass
    
    old_queue_id = embed_state.load_message_id("queue")
    if old_queue_id:
        try:
            old_msg = await channel.fetch_message(old_queue_id)
            await old_msg.delete()
        except:
            pass

    old_details_id = embed_state.load_message_id("details")
    if old_details_id:
        try:
            old_msg = await channel.fetch_message(old_details_id)
            await old_msg.delete()
        except:
            pass

    radio.now_playing_message = None
    radio.queue_message = None
    radio.details_message = None

    if radio.current_song:
        await update_now_playing(radio.current_song)

class RadioControlView(discord.ui.View):
    def __init__(self, radio, db):
        super().__init__(timeout=None)
        self.add_item(GenreSelect(radio, db))
        self.add_item(PlayButton(radio))
        self.add_item(PauseButton(radio))
        self.add_item(StopButton(radio))
        self.add_item(SkipButton(radio))
        self.add_item(SeekButton(radio))
        self.add_item(VolumeButton(radio))
        self.add_item(LikeButton(radio, db))
        self.add_item(DislikeButton(radio, db))
        self.add_item(DetailsButton(radio))
        self.add_item(QueueToggleButton(radio))

def build_detailed_embed(song: dict) -> discord.Embed:
    embed = discord.Embed(
        title="📂 SONG DETAILS",
        color=discord.Color.blue()
    )

    date = song.get('date', 'Unknown')
    label = song.get('label', 'Unknown')
    catnum = song.get('catnum', 'Unknown')

    media_type = song.get('mediatype_flac') or song.get('mediatype_mp3') or 'Unknown'

    embed.description = (
        "```md\n"
        f"{fixed(f'Artist = {song.get('artist', 'Unknown')}')}\n"
        f"{fixed(f'Title  = {song.get('title', 'Unknown')}')}\n"
        f"{fixed(f'Album  = {song.get('album', 'Unknown')}')}\n"
        f"{fixed(f'Year   = {date}')}\n"
        f"{fixed(f'Label  = {label}')}\n"
        f"{fixed(f'CATNUM = {catnum}')}\n"
        f"{fixed(f'Source = {media_type}')}\n"
        f"{fixed(f'Length = {format_duration(song.get('duration', 0))}')}\n"
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
            placeholder="🎼 Select Genre",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="genre_select"
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.dispatch(RadioAction.SET_GENRE, selected, user=interaction.user)

        await interaction.response.send_message(
            f"🎧 Genre switching to: **{selected.upper()}**",
            ephemeral=True
        )

class PlayButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="▶ Play",
            style=discord.ButtonStyle.secondary,
            custom_id="play_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
        await interaction.response.send_message(
            "▶ Resuming/Replaying playback...",
            ephemeral=True
        )

class PauseButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="⏸ Pause",
            style=discord.ButtonStyle.secondary,
            custom_id="pause_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.status == RadioStatusEnum.IDLE:
            await interaction.response.send_message(
                "❌ Stopped music cannot be paused",
                ephemeral=True
            )
            return

        if self.radio.status == RadioStatusEnum.PAUSED:
            self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
            await interaction.response.send_message(
                "▶ Resuming playback...",
                ephemeral=True
            )
        else:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await interaction.response.send_message(
                "⏸ Pausing playback...",
                ephemeral=True
            )

class StopButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="⏹ Stop",
            style=discord.ButtonStyle.secondary,
            custom_id="stop_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.STOP, user=interaction.user)
        await interaction.response.send_message(
            "⏹ Stopping playback...",
            ephemeral=True
        )

class SkipButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="⏭ Skip",
            style=discord.ButtonStyle.secondary,
            custom_id="skip_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.voice and (self.radio.voice.is_playing() or self.radio.voice.is_paused()):
            self.radio.dispatch(RadioAction.SKIP, user=interaction.user)

            await interaction.response.send_message(
                "⏭ Skipping the current track...",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Nothing is playing right now.",
                ephemeral=True
            )

class SeekButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="⏩ Move To",
            style=discord.ButtonStyle.secondary,
            custom_id="seek_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        if self.radio.status == RadioStatusEnum.IDLE:
            await interaction.response.send_message(
                "❌ Cannot seek while the radio is stopped",
                ephemeral=True
            )
            return

        modal = SeekModal(self.radio)
        await interaction.response.send_modal(modal)

class SeekModal(Modal):
    def __init__(self, radio):
        super().__init__(title="Jump to timestamp")
        self.radio = radio

        self.timestamp_input = TextInput(
            label="Enter timestamp (mm:ss)",
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
                "❌ Format must be mm:ss",
                ephemeral=True
            )
            return

        if not self.radio.current_song:
            await interaction.response.send_message(
                "❌ There is no current track",
                ephemeral=True
            )
            return

        duration = self.radio.current_song.get("duration", 0)

        if total_seconds >= duration:
            await interaction.response.send_message(
                "❌ Timestamp too long",
                ephemeral=True
            )
            return

        self.radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)

        await interaction.response.send_message(
            f"⏩ Jumping to {ts}...",
            ephemeral=True
        )

class VolumeButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="🔊 Vol",
            style=discord.ButtonStyle.secondary,
            custom_id="volume_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        modal = VolumeModal(self.radio)
        await interaction.response.send_modal(modal)

class VolumeModal(Modal):
    def __init__(self, radio):
        super().__init__(title="Set Volume (0-100%)")
        self.radio = radio

        self.volume_input = TextInput(
            label="Volume (%)",
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
                "❌ Invalid number!",
                ephemeral=True
            )
            return

        if value < 0 or value > 100:
            await interaction.response.send_message(
                "❌ Volume must be between 0 and 100",
                ephemeral=True
            )
            return

        self.radio.dispatch(RadioAction.SET_VOLUME, value / 100, user=interaction.user)

        await interaction.response.send_message(
            f"🔊 Volume set to: {value}%",
            ephemeral=True
        )

class LikeButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label="❤️ Like",
            style=discord.ButtonStyle.secondary,
            custom_id="like_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(
                "❌ No song is currently playing",
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
                msg = f"❤️ Liked: **{artist} - {title}**"
            elif status == "removed":
                msg = f"❤️ Like withdrawn: **{artist} - {title}**"
            else:
                msg = f"❤️ Liked (replaced dislike): **{artist} - {title}**"

            await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            print(f"Like error: {e}")
            await interaction.response.send_message(
                "❌ Failed to record like",
                ephemeral=True
            )

class DislikeButton(discord.ui.Button):
    def __init__(self, radio, db):
        super().__init__(
            label="👎 Dislike",
            style=discord.ButtonStyle.secondary,
            custom_id="dislike_button"
        )
        self.radio = radio
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if not self.radio.current_song:
            await interaction.response.send_message(
                "❌ No song is currently playing",
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
                msg = f"👎 Disliked: **{artist} - {title}**"
            elif status == "removed":
                msg = f"👎 Dislike withdrawn: **{artist} - {title}**"
            else:
                msg = f"👎 Disliked (replaced like): **{artist} - {title}**"

            await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            print(f"Dislike error: {e}")
            await interaction.response.send_message(
                "❌ Failed to record dislike",
                ephemeral=True
                )

class DetailsButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="📂 Info",
            style=discord.ButtonStyle.secondary,
            custom_id="details_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.show_details = not self.radio.show_details
        
        await update_now_playing(self.radio.current_song)
        
        await interaction.response.send_message(
            f"📂 Info visibility: **{'Shown' if self.radio.show_details else 'Hidden'}**",
            ephemeral=True
        )

class QueueToggleButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label="📋 Queue",
            style=discord.ButtonStyle.secondary,
            custom_id="queue_toggle_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
        self.radio.show_queue = not self.radio.show_queue
        
        await update_now_playing(self.radio.current_song)
        
        await interaction.response.send_message(
            f"📋 Queue visibility: **{'Shown' if self.radio.show_queue else 'Hidden'}**",
            ephemeral=True
        )