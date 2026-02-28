from enum import Enum, auto

class RadioState(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()

class RadioAction(Enum):
    SKIP = auto()
    SEEK = auto()
    SET_VOLUME = auto()
    SET_GENRE = auto()
    REPLAY = auto()
    STOP = auto()
    PAUSE = auto()
    JOIN = auto()
    DISCONNECT = auto()
    SET_LANGUAGE = auto()
