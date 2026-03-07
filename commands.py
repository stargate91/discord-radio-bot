import discord
from discord import app_commands
from radio_actions import RadioAction
from ui_utils import safe_fetch_message, safe_delete_message

def setup_commands(tree, radio):
    db = radio.db

    @tree.command(name="play", description="Search and play a song immediately")
    @app_commands.describe(query="Artist or Title of the song")
    async def play(interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
            return
        song = await db.get_song_by_id(int(query)) if query.isdigit() else None
        if not song:
            song = await db.get_song_by_path(query)
        if not song:
            results = await db.search_songs(query)
            if results:
                song = results[0]
        if not song:
            await interaction.response.send_message(f"No results found for: `{query}`", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        if radio.voice_channel_id is None:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        radio.dispatch(RadioAction.ADD_TO_QUEUE, song, user=interaction.user)
        try: await interaction.delete_original_response()
        except: pass

    @tree.command(name="stats", description="Show playback statistics")
    async def stats(interaction: discord.Interaction):
        from ui_studio import StatsView
        await interaction.response.defer()
        days = 7
        top_artists = await db.get_top_artists(days=days)
        top_songs = await db.get_top_songs(days=days)
        top_users = await db.get_top_users(days=days)
        view = StatsView(radio, interaction.user, guild=interaction.guild, top_artists=top_artists, top_songs=top_songs, top_users=top_users)
        await interaction.followup.send(view=view, ephemeral=True)

    @play.autocomplete('query')
    async def play_autocomplete(interaction: discord.Interaction, current: str):
        if not current or len(current) < 2:
            return []
        results = await db.search_songs(current)
        choices = []
        for s in results[:radio.config.autocomplete_limit]:
            label = f"{s['artist']} - {s['title']}"
            if len(label) > 100: label = label[:97] + "..."
            choices.append(app_commands.Choice(name=label, value=str(s['id'])))
        return choices
