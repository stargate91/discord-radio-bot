import discord
from ui_translate import t
from ui_utils import format_duration, fixed
from radio_actions import RadioState as RadioStatusEnum

_radio_ref = None
_db_ref = None

def init_embeds(radio, db):
    global _radio_ref, _db_ref
    _radio_ref = radio
    _db_ref = db

def build_embed(song: dict) -> discord.Embed:
    status_title = "🎧 NOW PLAYING"
    status_color = discord.Color.blurple()

    if _radio_ref:
        if _radio_ref.status == RadioStatusEnum.PAUSED:
            status_title = "⏸️ PAUSED"
            status_color = discord.Color.gold()
        elif _radio_ref.status == RadioStatusEnum.IDLE:
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

    if _radio_ref and _radio_ref.last_user:
        embed.set_footer(
            text=f"Tuned by {_radio_ref.last_user.display_name} • CityRadio",
            icon_url=_radio_ref.last_user.display_avatar.url
        )
    else:
        embed.set_footer(text="CityRadio • Stay online. Stay awake.")

    return embed

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
    
    footer_text = "CityRadio Queue"
    if _db_ref:
         footer_text = f"Total songs in library: {len(_db_ref.get_all_genres())} genres"
    
    embed.set_footer(text=footer_text)
    
    return embed
