import asyncio
import discord
from radio_actions import RadioState as RadioStatusEnum, RadioAction
from embed_state import EmbedStateManager

class RadioState:
    def is_admin(self, user: discord.Member | discord.User) -> bool:
        if not isinstance(user, discord.Member):
            return False
        
        if user.guild_permissions.administrator:
            return True

        if user.id == user.guild.owner_id:
            return True

        user_role_ids = [role.id for role in user.roles]
        if self.config.admin_role_id > 0 and self.config.admin_role_id in user_role_ids:
            return True
        if self.config.sysadmin_role_id > 0 and self.config.sysadmin_role_id in user_role_ids:
            return True
        
        return False

    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.embed_manager = EmbedStateManager()
        self.voice: discord.VoiceClient | None = None
        self.voice_channel_id: int | None = None
        self.genre: str = config.default_genre
        self.task: asyncio.Task | None = None
        self.current_song: dict | None = None
        self.seek_position: int | None = None
        self.is_seeking: bool = False
        self.volume: float = config.default_volume
        self.now_playing_message: discord.Message | None = None
        self.station_message: discord.Message | None = None
        self.queue: list[dict] = []
        self.show_queue: bool = False
        self.show_details: bool = False
        self.last_search_query: str = None
        self.last_search_results: list[dict] = None
        self.last_search_user: discord.User | None = None
        self.active_view_type: str = None
        self.last_search_page: int = 0
        self.last_search_type: str = "songs"
        self.last_history_page: int = 0
        self.filter_from: str = None
        self.filter_to: str = None
        self.status = RadioStatusEnum.IDLE
        self.is_back_action: bool = False
        self.is_forward_action: bool = False
        self.action_queue = asyncio.Queue()
        self.last_user: discord.Member | discord.User | None = None
        self.language: str = config.default_language
        self.last_history_paths: list[str] = []
        self.last_back_time: float = 0.0
        self.forward_stack: list[dict] = []
        self.editing_playlist_id: int | None = None
        self.playlist_editor_user: int | None = None
        self.last_editor_page: int = 0
        self.is_compact: bool = (config.default_ui_mode == "compact")
        self.track_start_time: float | None = None
        self.track_start_offset: float = 0.0
        self.track_duration: int = 0
    async def refresh_queue(self):
        self.queue = []
        for _ in range(self.config.queue_refresh_limit):
            song = await self.get_random_song_by_genre(self.genre)
            if song:
                self.queue.append(song)

    def dispatch(self, action: RadioAction, data=None, user: discord.Member | discord.User | None = None):
        print(f"[ACTION] Dispatching: {action.name} with data: {data} by user: {user}")
        if user:
            self.last_user = user
        self.action_queue.put_nowait((action, data))
    async def get_random_song_by_genre(self, genre: str):
        if genre.lower() == "levifav":
            return await self.db.get_random_song_by_rating(min_rating=self.config.levifav_min_rating)
        return await self.db.get_random_song_by_genre(genre)

    def get_display_queue(self):
        return list(reversed(self.forward_stack)) + self.queue
