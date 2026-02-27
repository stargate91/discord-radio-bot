import discord
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from discord.ui import Modal, TextInput
from pathlib import Path
from embed_state import EmbedStateManager

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
    status_title = "NOW PLAYING"
    status_color = discord.Color.blurple()

    if radio:
        if radio.status == RadioStatusEnum.PAUSED:
            status_title = "PAUSED"
            status_color = discord.Color.gold()
        elif radio.status == RadioStatusEnum.IDLE:
            status_title = "IDLE"
            status_color = discord.Color.red()

    embed = discord.Embed(
        title=f"🎧 {status_title} - {song.get('genre', 'Unknown').upper()}",
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

    embed.set_footer(text="CityRadio • Stay online. Stay awake.")

    return embed

async def update_now_playing(song: dict):
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    embed = build_embed(song)

    if not radio.now_playing_message:
        message_id = embed_state.load_message_id()
        if message_id:
            try:
                radio.now_playing_message = await channel.fetch_message(message_id)
            except:
                radio.now_playing_message = None

    if radio.now_playing_message:
        try:
            await radio.now_playing_message.edit(
                embed=embed,
                view=RadioControlView(radio, db)
            )
            return
        except:
            radio.now_playing_message = None

    view = RadioControlView(radio, db)
    msg = await channel.send(embed=embed, view=view)
    radio.now_playing_message = msg
    embed_state.save_message_id(msg.id)

async def force_new_embed():
    channel = bot.get_channel(config.radio_text_channel_id)
    if not channel:
        return

    old_id = embed_state.load_message_id()

    if old_id:
        try:
            old_msg = await channel.fetch_message(old_id)
            await old_msg.delete()
        except:
            pass

    radio.now_playing_message = None

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
        self.radio.dispatch(RadioAction.SET_GENRE, selected)

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
        self.radio.dispatch(RadioAction.REPLAY)
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
        self.radio.dispatch(RadioAction.PAUSE)
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
        self.radio.dispatch(RadioAction.STOP)
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
            self.radio.dispatch(RadioAction.SKIP)

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
            label="⏩ Go To",
            style=discord.ButtonStyle.secondary,
            custom_id="seek_button"
        )
        self.radio = radio

    async def callback(self, interaction: discord.Interaction):
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

        self.radio.dispatch(RadioAction.SEEK, total_seconds)

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

        self.radio.dispatch(RadioAction.SET_VOLUME, value / 100)

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

        try:
            with self.db._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE songs SET likes = likes + 1 WHERE path = ?",
                    (song_path,)
                )
                conn.commit()

            updated_song = self.db.get_song_by_path(song_path)

            if updated_song:
                self.radio.current_song = updated_song
                await update_now_playing(updated_song)

            artist = updated_song.get("artist") or "Unknown Artist"
            title = updated_song.get("title") or "Unknown Title"

            await interaction.response.send_message(
                f"❤️ Liked: **{artist} - {title}**",
                ephemeral=True
            )

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
            with self.db._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE songs SET dislikes = dislikes + 1 WHERE path = ?",
                    (song_path,)
                )
                conn.commit()

            updated_song = self.db.get_song_by_path(song_path)

            if updated_song:
                self.radio.current_song = updated_song
                await update_now_playing(updated_song)

            artist = updated_song.get("artist") or "Unknown Artist"
            title = updated_song.get("title") or "Unknown Title"

            await interaction.response.send_message(
                f"👎 Disliked: **{artist} - {title}**",
                ephemeral=True
            )

        except Exception as e:
            print(f"Dislike error: {e}")
            await interaction.response.send_message(
                "❌ Failed to record dislike",
                ephemeral=True
                )