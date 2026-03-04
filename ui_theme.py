class Theme:



    PRIMARY = 0x5865F2

    SECONDARY = 0x2b2d31

    SUCCESS = 0x5865F2

    WARNING = 0xFEE75C

    DANGER = 0xED4245





    IDLE = 0xED4245

    PAUSED = 0xFEE75C

    PLAYING = 0x5865F2





    BACKGROUND = 0x2b2d31

    ACCENT = 0x5865F2



    @classmethod

    def init_theme(cls, config):

        cls.PRIMARY = config.theme_primary

        cls.SECONDARY = config.theme_secondary

        cls.SUCCESS = config.theme_success

        cls.WARNING = config.theme_warning

        cls.DANGER = config.theme_danger

        cls.IDLE = config.theme_idle

        cls.PAUSED = config.theme_paused

        cls.PLAYING = config.theme_playing

        cls.BACKGROUND = config.theme_background

        cls.ACCENT = config.theme_accent
