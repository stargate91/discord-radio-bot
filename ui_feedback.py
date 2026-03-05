import discord
from discord.ui import Modal, TextInput, View, Button, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, BaseView
import time

class FeedbackModal(Modal):
    def __init__(self, radio, feedback_type):
        self.radio = radio
        self.feedback_type = feedback_type
        
        type_key = f"feedback_type_{feedback_type}"
        content_key = "feedback_music_content_label" if feedback_type == "music" else "feedback_content_label"
        
        super().__init__(title=f"{t('feedback_modal_title')}: {t(type_key)}")
        
        self.details = TextInput(
            label=t(content_key),
            style=discord.TextStyle.paragraph,
            placeholder="...",
            required=True,
            min_length=5 if feedback_type == "music" else 10,
            max_length=2000
        )
        self.add_item(self.details)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        await self.radio.db.save_feedback(interaction.user.id, self.feedback_type, self.details.value or "")
        
        channel_id = self.radio.config.feedback_channel_id
        if channel_id:
            feedback_channel = interaction.client.get_channel(channel_id)
            if not feedback_channel:
                try:
                    feedback_channel = await interaction.client.fetch_channel(channel_id)
                except:
                    pass
            
            if feedback_channel:
                if self.feedback_type == "bug":
                    color = self.radio.config.theme_danger
                    emoji = Icons.FEEDBACK_BUG
                elif self.feedback_type == "music":
                    color = self.radio.config.theme_success
                    emoji = Icons.FEEDBACK_MUSIC
                else:
                    color = self.radio.config.theme_primary
                    emoji = Icons.FEEDBACK_FEATURE
                
                type_name = t(f"feedback_type_{self.feedback_type}")
                
                embed = discord.Embed(
                    title=f"{emoji} {type_name.upper()}",
                    description=self.details.value,
                    color=color,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                embed.add_field(name=t("initiated_by"), value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                embed.add_field(name=t("feedback_type_label"), value=type_name, inline=True)
                
                if interaction.guild:
                    embed.set_footer(text=f"Server: {interaction.guild.name} | ID: {interaction.guild.id}")
                
                await feedback_channel.send(embed=embed)
            
        await interaction.response.send_message(t("feedback_sent"), ephemeral=True)

class FeedbackTypeView(discord.ui.View):
    def __init__(self, radio):
        super().__init__(timeout=60)
        self.radio = radio
        
        self.btn_bug = Button(label=t("feedback_type_bug"), emoji=Icons.FEEDBACK_BUG, style=discord.ButtonStyle.danger)
        self.btn_bug.callback = self.bug_report_callback
        self.add_item(self.btn_bug)
        
        self.btn_feat = Button(label=t("feedback_type_feature"), emoji=Icons.FEEDBACK_FEATURE, style=discord.ButtonStyle.primary)
        self.btn_feat.callback = self.feature_request_callback
        self.add_item(self.btn_feat)
        
        self.btn_music = Button(label=t("feedback_type_music"), emoji=Icons.FEEDBACK_MUSIC, style=discord.ButtonStyle.success)
        self.btn_music.callback = self.music_request_callback
        self.add_item(self.btn_music)

    async def bug_report_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeedbackModal(self.radio, "bug"))

    async def feature_request_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeedbackModal(self.radio, "feature"))
        
    async def music_request_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeedbackModal(self.radio, "music"))

class FeedbackButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("feedback_label"),
            emoji=Icons.FEEDBACK, 
            style=discord.ButtonStyle.secondary,
            custom_id="feedback_main"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        view = FeedbackTypeView(self.radio)
        await interaction.response.send_message(
            content=f"**{t('feedback_modal_title')}**",
            view=view,
            ephemeral=True
        )
