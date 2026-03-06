import discord
import os
from PIL import Image

def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def fixed(text: str, length: int = 42):
    text = str(text)
    if len(text) > length:
        return text[:length - 3] + "..."
    return text.ljust(length)
async def safe_delete_message(message: discord.Message | None):
    """Safely delete a message without crashing on common errors."""
    if not message:
        return
    try:
        await message.delete()
    except discord.NotFound:
        pass
    except discord.Forbidden:
        print(f"[UI] Warning: Permission denied to delete message {message.id}")
    except Exception as e:
        print(f"[UI] Error deleting message {message.id}: {e}")
async def check_editor_lock(radio, interaction):
    """Check if the playlist editor is locked by another user."""
    if radio.playlist_editor_user and radio.playlist_editor_user != interaction.user.id:
        try:
            member = await interaction.guild.fetch_member(radio.playlist_editor_user)
            name = member.display_name
        except Exception as e:
            print(f"[LOCK CHECK] Failed to fetch member: {e}")
            name = "Someone"
        from ui_translate import t
        await interaction.response.send_message(t("studio_locked_message").format(user=name), ephemeral=True)
        return True
    return False
async def safe_fetch_message(channel, message_id: int | None):
    """Safely fetch a message from a channel without crashing."""
    if not message_id:
        return None
    try:
        return await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden):
        return None
    except Exception as e:
        print(f"[UI] Unexpected error fetching message {message_id}: {e}")
        return None

def get_dominant_color(image_path):
    """Extracts the most dominant color from an image file."""
    try:
        if not image_path or not os.path.exists(image_path):
            return None
            
        with Image.open(image_path) as img:
            # Convert to RGB and resize to speed up processing
            img = img.convert("RGB")
            img = img.resize((100, 100))
            
            # Quantize the image to find dominant colors
            # Using 8 colors gives a good balance between speed and quality
            quantized = img.quantize(colors=8, method=Image.Quantize.MAXCOVERAGE)
            
            # Get the colors in the quantized image
            palette = quantized.getpalette()
            color_counts = quantized.getcolors()
            
            if not color_counts:
                return None
                
            # Sort by count (frequency)
            # Filter out extreme blacks/whites if possible, but for simplicity we'll take the most frequent
            most_frequent = max(color_counts, key=lambda x: x[0])[1]
            
            # Extract RGB from the palette
            r = palette[most_frequent * 3]
            g = palette[most_frequent * 3 + 1]
            b = palette[most_frequent * 3 + 2]
            
            return (r << 16) | (g << 8) | b
    except Exception as e:
        print(f"[UI] Error extracting dominant color: {e}")
        return None
