"""
Lost Island: 15 Boys Survival RPG Engine
Multiplayer Matchmaking & Lobby Engine.
Room allocation, atomic 15-character slot locking, and match orchestration.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from lost_island.core.types import RoomState, StormStation, BoyProfile
from lost_island.core.roster import CANONICAL_ROSTER, create_fresh_roster
from lost_island.simulation.storm import StormSimulation
from lost_island.simulation.island import IslandSimulation

@dataclass
class PlayerSlot:
    character_id: str
    player_id: str
    player_name: str
    is_ready: bool = False
    is_bot: bool = False
    connection_ref: Any = None # WebSocket handle

class LobbyRoom:
    """Represents a dedicated 15-character multiplayer game room."""
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.state: RoomState = RoomState.WAITING_FOR_PLAYERS
        self.created_at = time.time()
        
        # 15 distinct character slots mapped by character ID
        self.slots: Dict[str, Optional[PlayerSlot]] = {
            char_id: None for char_id in CANONICAL_ROSTER.keys()
        }
        
        # Game simulation state
        self.roster: Dict[str, BoyProfile] = create_fresh_roster()
        self.storm_sim: Optional[StormSimulation] = None
        self.island_sim: Optional[IslandSimulation] = None
        
        self.countdown_seconds: int = 5
        self.countdown_task: Optional[asyncio.Task] = None

    def get_occupied_count(self) -> int:
        return sum(1 for slot in self.slots.values() if slot is not None)

    def is_fully_locked(self) -> bool:
        """Returns True if all 15 character slots are uniquely occupied."""
        return self.get_occupied_count() == 15

    def get_available_characters(self) -> List[str]:
        """List character IDs that have not yet been locked."""
        return [cid for cid, slot in self.slots.items() if slot is None]

    def lock_character(self, player_id: str, player_name: str, character_id: str, conn_ref: Any = None) -> Tuple[bool, str]:
        """
        Server-side atomic slot lock.
        Validates character existence, room capacity, and locks slot uniquely.
        """
        if self.state not in (RoomState.WAITING_FOR_PLAYERS, RoomState.COUNTDOWN):
            return False, "Room is already in an active match."

        if character_id not in self.slots:
            return False, f"Unknown character ID: {character_id}"

        # If player already holds a slot in this room, unlock the old one first
        for cid, slot in list(self.slots.items()):
            if slot and slot.player_id == player_id:
                if cid == character_id:
                    return True, "Slot already locked by you."
                self.slots[cid] = None

        # Check if requested character slot is already taken by someone else
        current_occupant = self.slots[character_id]
        if current_occupant is not None:
            return False, f"Character {CANONICAL_ROSTER[character_id].name} is already locked by {current_occupant.player_name}."

        # Lock the slot
        self.slots[character_id] = PlayerSlot(
            character_id=character_id,
            player_id=player_id,
            player_name=player_name,
            is_ready=True,
            is_bot=False,
            connection_ref=conn_ref
        )
        return True, f"Locked character {CANONICAL_ROSTER[character_id].name} successfully."

    def release_player(self, player_id: str) -> Optional[str]:
        """Release slot when a player disconnects or leaves room."""
        for cid, slot in list(self.slots.items()):
            if slot and slot.player_id == player_id:
                self.slots[cid] = None
                if self.state == RoomState.COUNTDOWN:
                    self.state = RoomState.WAITING_FOR_PLAYERS
                return cid
        return None

    def fill_remaining_with_ai(self) -> int:
        """Helper to fill unassigned slots with bot players for testing or mixed play."""
        filled = 0
        for cid, slot in self.slots.items():
            if slot is None:
                bot_name = f"AI_{CANONICAL_ROSTER[cid].name}"
                self.slots[cid] = PlayerSlot(
                    character_id=cid,
                    player_id=f"bot_{cid}",
                    player_name=bot_name,
                    is_ready=True,
                    is_bot=True
                )
                filled += 1
        return filled

    def start_storm_prologue(self):
        """Transition room into Prologue Sea Storm sequence."""
        self.state = RoomState.IN_PROLOGUE_STORM
        self.storm_sim = StormSimulation(self.roster, storm_duration_ticks=35)

    def transition_to_island(self):
        """Transition room from Prologue Storm to Island Survival."""
        self.state = RoomState.IN_ISLAND_SURVIVAL
        self.island_sim = IslandSimulation(self.roster)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize room state for client broadcasts."""
        return {
            "room_id": self.room_id,
            "state": self.state.value,
            "occupied_count": self.get_occupied_count(),
            "max_slots": 15,
            "all_filled": self.is_fully_locked(),
            "slots": {
                cid: {
                    "character_name": CANONICAL_ROSTER[cid].name,
                    "occupied": slot is not None,
                    "player_id": slot.player_id if slot else None,
                    "player_name": slot.player_name if slot else None,
                    "is_ready": slot.is_ready if slot else False,
                    "is_bot": slot.is_bot if slot else False
                }
                for cid, slot in self.slots.items()
            }
        }

class MatchmakingEngine:
    """Allocates incoming players to available 15-player survival rooms."""
    def __init__(self):
        self.rooms: Dict[str, LobbyRoom] = {}
        self._room_counter = 1

    def find_or_create_room(self, preferred_room_id: Optional[str] = None) -> LobbyRoom:
        """Find an available waiting room with open slots, or create a new one."""
        if preferred_room_id and preferred_room_id in self.rooms:
            target = self.rooms[preferred_room_id]
            if target.state == RoomState.WAITING_FOR_PLAYERS and not target.is_fully_locked():
                return target

        # Find first waiting room with space
        for room in self.rooms.values():
            if room.state == RoomState.WAITING_FOR_PLAYERS and not room.is_fully_locked():
                return room

        # Create new room
        new_id = f"storm_room_{self._room_counter:03d}"
        self._room_counter += 1
        room = LobbyRoom(new_id)
        self.rooms[new_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[LobbyRoom]:
        return self.rooms.get(room_id)

    def get_all_rooms_summary(self) -> List[Dict[str, Any]]:
        return [
            {
                "room_id": r.room_id,
                "state": r.state.value,
                "occupied": r.get_occupied_count(),
                "max": 15
            }
            for r in self.rooms.values()
        ]

