import discord

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
        pass # Already deleted
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
