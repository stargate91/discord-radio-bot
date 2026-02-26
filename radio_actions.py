from enum import Enum, auto

class RadioAction(Enum):
    SKIP = auto()
    SEEK = auto()
    SET_VOLUME = auto()
    SET_GENRE = auto()
