"""
Lost Island: 15 Boys Survival RPG Engine
Core types, enumerations, and data models.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time

class GameMode(str, Enum):
    OFFLINE_SINGLEPLAYER = "OFFLINE_SINGLEPLAYER"
    ONLINE_MULTIPLAYER = "ONLINE_MULTIPLAYER"

class StormStation(str, Enum):
    IDLE = "IDLE"
    HELM = "HELM"               # Steering against rogue waves
    BILGE = "BILGE"             # Bailing water from lower decks
    CARPENTRY = "CARPENTRY"     # Patching hull fractures & leaks
    RIGGING = "RIGGING"         # Reefing sails & securing halyards
    BRACE = "BRACE"             # Bracing against catastrophic swells

class AIState(str, Enum):
    IDLE = "IDLE"
    MANNING_STATION = "MANNING_STATION" # Storm duty
    FOLLOWING_LEADER = "FOLLOWING_LEADER"
    FORAGING = "FORAGING"
    BUILDING_SHELTER = "BUILDING_SHELTER"
    DEFENDING_CAMP = "DEFENDING_CAMP"
    TENDING_FIRE = "TENDING_FIRE"
    RESTING = "RESTING"
    RETREATING_TO_SHELTER = "RETREATING_TO_SHELTER"

class TimeOfDay(str, Enum):
    DAWN = "DAWN"
    DAY = "DAY"
    DUSK = "DUSK"
    NIGHT = "NIGHT"

class WeatherType(str, Enum):
    TEMPEST = "TEMPEST"
    CLEAR = "CLEAR"
    OVERCAST = "OVERCAST"
    RAIN = "RAIN"
    GALE = "GALE"

class RoomState(str, Enum):
    WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
    COUNTDOWN = "COUNTDOWN"
    IN_PROLOGUE_STORM = "IN_PROLOGUE_STORM"
    IN_ISLAND_SURVIVAL = "IN_ISLAND_SURVIVAL"
    FINISHED = "FINISHED"

@dataclass
class CharacterStats:
    health: float = 100.0       # 0 - 100
    stamina: float = 100.0      # 0 - 100
    hunger: float = 0.0         # 0 (sated) - 100 (starving)
    morale: float = 100.0       # 0 (panicked) - 100 (heroic)
    warmth: float = 100.0       # 0 (hypothermic) - 100 (cozy)
    is_injured: bool = False
    injury_desc: Optional[str] = None

@dataclass
class BoyProfile:
    id: str
    name: str
    age: int
    nationality: str
    archetype: str
    leadership: int             # 1 - 10
    seamanship: int             # 1 - 10
    carpentry: int              # 1 - 10
    hunting: int                # 1 - 10
    foraging: int               # 1 - 10
    cooking: int                # 1 - 10
    morale_influence: int       # 1 - 10
    description: str
    stats: CharacterStats = field(default_factory=CharacterStats)
    current_action: str = "Awaiting orders"
    ai_state: AIState = AIState.IDLE
    target_station: StormStation = StormStation.IDLE

