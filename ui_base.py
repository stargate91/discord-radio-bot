import discord
import traceback
from discord.ui import LayoutView
from ui_icons import Icons
from ui_translate import t

def handle_ui_error(func):
    """Decorator to handle errors in UI callbacks gracefully."""
    async def wrapper(*args, **kwargs):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            print(f"[UI ERROR] in {func.__name__}: {e}")
            traceback.print_exc()
            error_msg = t('error_generic') or "An error occurred while processing your request."
            if interaction:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"{Icons.WARNING} {error_msg}", ephemeral=True)
                else:
                    try:
                        await interaction.followup.send(f"{Icons.WARNING} {error_msg}", ephemeral=True)
                    except:
                        pass
    return wrapper

class BaseView(LayoutView):
    """Base class for all Radio Bot views with shared logic."""

    def __init__(self, radio, timeout=None):
        super().__init__(timeout=timeout)
        self.radio = radio
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        print(f"[VIEW ERROR] {error} in {item}")
        traceback.print_exc()
        error_msg = t('error_generic') or "An error occurred."
        if not interaction.response.is_done():
            await interaction.response.send_message(f"{Icons.WARNING} {error_msg}", ephemeral=True)
        else:
            try:
                await interaction.followup.send(f"{Icons.WARNING} {error_msg}", ephemeral=True)
            except:
                pass

class PaginatedView(BaseView):
    """Base class for views requiring pagination (Search, History, Playlists)."""

    def __init__(self, radio, data_list, items_per_page=5, timeout=None, page=0):
        super().__init__(radio, timeout=timeout)
        self.data_list = data_list
        self.items_per_page = items_per_page
        self.current_page = page
        self.total_pages = max(1, (len(data_list) + items_per_page - 1) // items_per_page)

    def get_page_items(self):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        return self.data_list[start:end]

    def update_pagination_buttons(self, prev_button, next_button):
        """Helper to update state of Prev/Next buttons."""
        if prev_button:
            prev_button.disabled = (self.current_page == 0)
        if next_button:
            next_button.disabled = (self.current_page >= self.total_pages - 1)

    @property
    def pagination_info(self):
        return f"{t('page')} {self.current_page + 1} / {self.total_pages} ({len(self.data_list)} total)"
