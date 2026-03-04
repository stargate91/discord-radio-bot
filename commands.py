import discord
from discord import app_commands
from radio_actions import RadioAction

def setup_commands(tree, radio, db):

    @tree.command(name="play", description="Search and play a song immediately")
    @app_commands.describe(query="Artist or Title of the song")
    async def play(interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)
            return

        song = db.get_song_by_id(int(query)) if query.isdigit() else None
        if not song:
            song = db.get_song_by_path(query)
        if not song:
            results = db.search_songs(query)
            if results:
                song = results[0]
        if not song:
            await interaction.response.send_message(f"No results found for: `{query}`", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if not radio.voice:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)

        radio.dispatch(RadioAction.ADD_TO_QUEUE, song, user=interaction.user)
        radio.dispatch(RadioAction.SKIP, user=interaction.user)

        await interaction.followup.send(f"Broadcasting: **{song['artist']} - {song['title']}**", ephemeral=True)

    @play.autocomplete('query')
    async def play_autocomplete(interaction: discord.Interaction, current: str):
        if not current or len(current) < 2:
            return []

        results = db.search_songs(current)
        choices = []
        for s in results[:25]:
            label = f"{s['artist']} - {s['title']}"
            if len(label) > 100: label = label[:97] + "..."


            choices.append(app_commands.Choice(name=label, value=str(s['id'])))
        return choices
