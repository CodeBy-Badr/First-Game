"""
Lost Island: 15 Boys Survival RPG Engine
Multiplayer Network Protocol Definitions.
Standardized packet types and serialization helpers.
"""

import json
import time
from typing import Dict, Any, Optional, Tuple

class PacketType:
    # Client -> Server
    AUTH = "AUTH"
    LIST_ROOMS = "LIST_ROOMS"
    JOIN_ROOM = "JOIN_ROOM"
    LEAVE_ROOM = "LEAVE_ROOM"
    SELECT_CHARACTER = "SELECT_CHARACTER"
    SET_READY = "SET_READY"
    STORM_ACTION = "STORM_ACTION"
    SURVIVAL_ACTION = "SURVIVAL_ACTION"
    FILL_AI_SLOTS = "FILL_AI_SLOTS" # Admin/Testing trigger to simulate 15 players
    CHAT = "CHAT"

    # Server -> Client
    AUTH_RESULT = "AUTH_RESULT"
    ROOM_LIST = "ROOM_LIST"
    ROOM_JOINED = "ROOM_JOINED"
    ROOM_UPDATE = "ROOM_UPDATE"
    COUNTDOWN = "COUNTDOWN"
    GAME_START = "GAME_START"
    STORM_TICK = "STORM_TICK"
    ISLAND_TICK = "ISLAND_TICK"
    CHAT_MSG = "CHAT_MSG"
    ERROR = "ERROR"

def create_packet(packet_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Serialize outbound message into JSON string."""
    return json.dumps({
        "type": packet_type,
        "payload": payload or {},
        "timestamp": time.time()
    })

def parse_packet(raw_text: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """Safely parse incoming packet payload."""
    try:
        data = json.loads(raw_text)
        return data.get("type"), data.get("payload", {})
    except Exception:
        return None, {}
