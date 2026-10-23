#!/usr/bin/env python3
# ==============================================================================
# FILE:    matchmaking_server.py
# PATH:    Assets/Backend/matchmaking_server.py
# PURPOSE: Production-ready asynchronous matchmaking backend for
#          "Lost Island: 15 Boys Survival".
#
#  ARCHITECTURE
#  ─────────────────────────────────────────────────────────────────────────────
#  Transport:   asyncio StreamReader/StreamWriter over raw TCP.
#  Protocol:    Newline-delimited JSON — one message per line.
#               Simple, human-readable, debuggable with netcat or telnet.
#
#  Message flow (CLIENT → SERVER):
#    {"action": "register", "display_name": "Alex", "boy_id": 3}
#
#  Message flow (SERVER → CLIENT):
#    {"status": "ok",    "slot": "Baxter", "room_id": "uuid"}
#    {"status": "error", "reason": "slot_taken"}
#    {"status": "launch","room_id": "uuid", "players": [...]}   ← broadcast
#
#  Room lifecycle:
#    WAITING  → all 15 slots claimed → LAUNCHING → clients receive launch packet
#
#  CONCURRENCY MODEL
#  ─────────────────────────────────────────────────────────────────────────────
#  • Single asyncio event loop — no threads, no thread-pool overhead.
#  • All shared state (rooms, slot maps) is mutated exclusively inside
#    coroutines awaited on the event loop. Python's GIL plus the single-event-
#    loop model makes this inherently race-condition-free without explicit locks.
#  • asyncio.Lock used defensively for the room allocation path to keep the
#    code correct if the server is ever ported to a multi-loop architecture.
#
#  SCALABILITY NOTE
#  ─────────────────────────────────────────────────────────────────────────────
#  This server handles one game server instance (up to N concurrent rooms,
#  each with 15 players). For horizontal scaling, place a load balancer in
#  front and use Redis pub/sub for cross-instance room state. That is outside
#  the scope of Step 1.
# ==============================================================================

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# Logging Setup
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("MatchmakingServer")

# ==============================================================================
# Constants
# ==============================================================================

HOST: str = "0.0.0.0"
PORT: int = 9090
MAX_ROOM_SIZE: int = 15       # Strict roster size — never changes
READ_LIMIT: int = 4096        # Max bytes per inbound message
IDLE_TIMEOUT: float = 120.0   # Seconds before an idle connection is dropped

# Canonical boy name list — index matches BoyId enum in Unity BoyRoster.cs
BOY_NAMES: Tuple[str, ...] = (
    "Gordon",    # 0
    "Prim",      # 1
    "Doniphan",  # 2
    "Baxter",    # 3
    "Cross",     # 4
    "Webb",      # 5
    "Wilcox",    # 6
    "Service",   # 7
    "Garnett",   # 8
    "Jack",      # 9
    "Jenkins",   # 10
    "Iverson",   # 11
    "Dole",      # 12
    "Costar",    # 13
    "Moko",      # 14
)

# Pre-build a frozenset for O(1) membership checks — built once at import time.
VALID_BOY_IDS: frozenset = frozenset(range(MAX_ROOM_SIZE))

# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class PlayerConnection:
    """
    Represents one live TCP connection from a game client.
    Holds the asyncio writer (used for sending) and metadata set after
    successful slot registration.
    """
    writer:       asyncio.StreamWriter
    display_name: Optional[str] = None
    boy_id:       Optional[int] = None
    room_id:      Optional[str] = None

    # Convenience alias for logging/packets.
    @property
    def boy_name(self) -> Optional[str]:
        return BOY_NAMES[self.boy_id] if self.boy_id is not None else None

    async def send(self, payload: dict) -> None:
        """
        Serialises payload to JSON and writes a newline-terminated line.
        Flushes immediately so the client doesn't need to wait for buffer fill.
        Fire-and-forget: individual send errors are caught here so one bad
        client can't crash the server or stall a broadcast loop.
        """
        try:
            data = json.dumps(payload) + "\n"
            self.writer.write(data.encode("utf-8"))
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            log.warning("Send failed for %s: %s", self.boy_name or "unknown", exc)

    def close(self) -> None:
        """Gracefully closes the underlying transport."""
        if not self.writer.is_closing():
            self.writer.close()


@dataclass
class Room:
    """
    Represents one matchmaking room holding up to MAX_ROOM_SIZE (15) players.

    Slot Map
    ────────
    _slots: dict mapping boy_id (int) → PlayerConnection
    Fixed-capacity: enforced by pre-seeding available slot checking.

    State
    ────────────────
    WAITING  — accepting new slot registrations.
    LAUNCHING — all 15 slots claimed; launch broadcast in progress.
    LAUNCHED  — broadcast complete; room is sealed.
    """

    room_id:   str                                    = field(default_factory=lambda: str(uuid.uuid4()))
    _slots:    Dict[int, PlayerConnection]            = field(default_factory=dict, repr=False)
    _lock:     asyncio.Lock                           = field(default_factory=asyncio.Lock, repr=False)
    state:     str                                    = "WAITING"

    @property
    def player_count(self) -> int:
        return len(self._slots)

    @property
    def is_full(self) -> bool:
        return len(self._slots) == MAX_ROOM_SIZE

    @property
    def is_available(self) -> bool:
        """True when the room can still accept new registrations."""
        return self.state == "WAITING" and not self.is_full

    def is_slot_taken(self, boy_id: int) -> bool:
        return boy_id in self._slots

    async def try_claim_slot(
        self,
        boy_id: int,
        conn: PlayerConnection
    ) -> Tuple[bool, Optional[str]]:
        """
        Atomically claims a slot for the given connection.

        Returns
        ───────
        (True, None)        — slot claimed successfully.
        (False, reason_str) — claim failed; reason explains why.

        The asyncio.Lock ensures that two simultaneous registration
        requests for the same slot cannot both succeed.
        """
        async with self._lock:
            if self.state != "WAITING":
                return False, "room_not_waiting"

            if boy_id in self._slots:
                return False, "slot_taken"

            self._slots[boy_id] = conn
            conn.room_id = self.room_id
            log.info(
                "[Room %s] Slot claimed: %s (%s). %d/%d filled.",
                self.room_id[:8],
                BOY_NAMES[boy_id],
                conn.display_name,
                len(self._slots),
                MAX_ROOM_SIZE,
            )
            return True, None

    async def broadcast_launch(self) -> None:
        """
        Sends the launch packet to all 15 connected clients simultaneously.
        Uses asyncio.gather so all writes fire concurrently — no serial stall.
        Marks room state as LAUNCHED to prevent duplicate broadcasts.
        """
        async with self._lock:
            if self.state != "WAITING":
                return  # Already launching or launched — skip.
            self.state = "LAUNCHING"

        # Build the launch payload once — shared across all 15 sends.
        player_list = [
            {"boy_id": bid, "boy_name": BOY_NAMES[bid], "display_name": c.display_name}
            for bid, c in sorted(self._slots.items())
        ]
        launch_packet = {
            "status":  "launch",
            "room_id": self.room_id,
            "players": player_list,
            "message": "All 15 players ready. Initiating storm sequence NOW.",
        }

        log.info("[Room %s] All 15 slots filled — broadcasting launch.", self.room_id[:8])

        # Fire all 15 sends concurrently; exceptions per-client are swallowed
        # inside PlayerConnection.send() so one bad client can't stall others.
        await asyncio.gather(
            *(conn.send(launch_packet) for conn in self._slots.values()),
            return_exceptions=True,
        )

        self.state = "LAUNCHED"
        log.info("[Room %s] Launch broadcast complete.", self.room_id[:8])

    def get_all_connections(self) -> List[PlayerConnection]:
        return list(self._slots.values())


# ==============================================================================
# Room Manager
# ==============================================================================

class RoomManager:
    """
    Manages the collection of active rooms.
    Always attempts to fill the most-recently-opened WAITING room before
    creating a new one (simple greedy bin-packing).
    """

    def __init__(self) -> None:
        # Ordered insertion so we can efficiently find the last WAITING room.
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def assign_room(self, boy_id: int, conn: PlayerConnection) -> Tuple[Room, bool, Optional[str]]:
        """
        Finds or creates a room, then attempts to claim the requested slot.

        Returns
        ───────
        (room, success, error_reason)

        If success is True and the room is now full, the caller must trigger
        the launch broadcast (done in handle_client to keep Room methods pure).
        """
        async with self._lock:
            # Find the first WAITING room that has the slot available.
            target_room: Optional[Room] = None
            for room in reversed(list(self._rooms.values())):
                if room.is_available and not room.is_slot_taken(boy_id):
                    target_room = room
                    break

            if target_room is None:
                target_room = Room()
                self._rooms[target_room.room_id] = target_room
                log.info("[RoomManager] Created new room: %s", target_room.room_id[:8])

        # Claim happens outside the room-manager lock so rooms can be
        # allocated concurrently while other rooms process their own claims.
        success, reason = await target_room.try_claim_slot(boy_id, conn)
        return target_room, success, reason

    def remove_room(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    @property
    def active_room_count(self) -> int:
        return len(self._rooms)


# ==============================================================================
# Client Handler Coroutine
# ==============================================================================

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    room_manager: RoomManager,
) -> None:
    """
    One coroutine per connected TCP client.
    Reads newline-delimited JSON messages until the connection closes or
    the idle timeout fires.

    Protocol state per connection:
        UNREGISTERED → (register action) → REGISTERED → waits for launch
    """
    peer = writer.get_extra_info("peername", ("?", 0))
    log.info("Client connected: %s:%s", peer[0], peer[1])

    conn = PlayerConnection(writer=writer)

    try:
        while True:
            # Timeout prevents zombie connections from leaking file descriptors.
            try:
                raw = await asyncio.wait_for(
                    reader.readline(),
                    timeout=IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.info("Idle timeout for %s — disconnecting.", peer)
                break

            if not raw:
                # Empty read = client closed the connection cleanly.
                break

            # -------------- Parse inbound message ---------------------------
            try:
                msg = json.loads(raw.decode("utf-8").strip())
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                await conn.send({"status": "error", "reason": f"bad_json: {exc}"})
                continue

            action = msg.get("action", "").strip().lower()

            # -------------- Route action ------------------------------------
            if action == "register":
                await _handle_register(msg, conn, room_manager)

            elif action == "ping":
                # Lightweight keepalive — prevents idle timeout for connected players.
                await conn.send({"status": "pong"})

            else:
                await conn.send({"status": "error", "reason": "unknown_action"})

    except (ConnectionResetError, asyncio.IncompleteReadError):
        log.info("Client %s:%s disconnected abruptly.", peer[0], peer[1])
    finally:
        # Always clean up the transport, even if an exception fires.
        conn.close()
        log.info("Connection closed: %s:%s", peer[0], peer[1])


async def _handle_register(
    msg: dict,
    conn: PlayerConnection,
    room_manager: RoomManager,
) -> None:
    """
    Processes a 'register' action.

    Expected payload:
        {"action": "register", "display_name": "Alex", "boy_id": 3}

    Validates input, claims the slot in a room, and — if the room
    reaches 15/15 — triggers the launch broadcast.
    """
    # ---- Validation --------------------------------------------------------
    display_name = msg.get("display_name", "").strip()
    if not display_name:
        await conn.send({"status": "error", "reason": "missing_display_name"})
        return

    raw_boy_id = msg.get("boy_id")
    if raw_boy_id is None:
        await conn.send({"status": "error", "reason": "missing_boy_id"})
        return

    try:
        boy_id = int(raw_boy_id)
    except (TypeError, ValueError):
        await conn.send({"status": "error", "reason": "invalid_boy_id_type"})
        return

    if boy_id not in VALID_BOY_IDS:
        await conn.send({
            "status": "error",
            "reason": f"invalid_boy_id: must be 0–{MAX_ROOM_SIZE - 1}",
        })
        return

    # ---- Already registered guard ------------------------------------------
    if conn.boy_id is not None:
        await conn.send({"status": "error", "reason": "already_registered"})
        return

    # ---- Claim slot in a room ----------------------------------------------
    conn.display_name = display_name
    conn.boy_id       = boy_id

    room, success, reason = await room_manager.assign_room(boy_id, conn)

    if not success:
        conn.boy_id       = None   # Roll back partial state
        conn.display_name = None
        await conn.send({"status": "error", "reason": reason})
        return

    # ---- Acknowledge successful registration --------------------------------
    await conn.send({
        "status":       "ok",
        "room_id":      room.room_id,
        "slot":         BOY_NAMES[boy_id],
        "player_count": room.player_count,
        "message":      f"Slot '{BOY_NAMES[boy_id]}' reserved. "
                        f"Waiting for {MAX_ROOM_SIZE - room.player_count} more player(s).",
    })

    # ---- Check if room is now full — trigger launch if so ------------------
    if room.is_full:
        # Launch broadcast is awaited here so the final registering client's
        # own send completes before the broadcast fires (ordered delivery).
        await room.broadcast_launch()


# ==============================================================================
# Server Entry Point
# ==============================================================================

async def main() -> None:
    """
    Bootstraps the asyncio TCP server and runs it indefinitely.
    Graceful shutdown is handled via KeyboardInterrupt (Ctrl-C).
    """
    room_manager = RoomManager()

    server = await asyncio.start_server(
        client_connected_cb=lambda r, w: handle_client(r, w, room_manager),
        host=HOST,
        port=PORT,
        limit=READ_LIMIT,
        # reuse_address: allow fast restart after process crash without
        # waiting for the OS TIME_WAIT timeout.
        reuse_address=True,
    )

    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log.info("Lost Island Matchmaking Server listening on %s", addrs)
    log.info("Waiting for up to %d players per room…", MAX_ROOM_SIZE)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server shut down gracefully.")

