"""
Lost Island: 15 Boys Survival RPG Engine
Multiplayer WebSocket Server.
Low-latency real-time state synchronization, 15-player matchmaking, and simulation loop.
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Optional, Set
from lost_island.core.types import RoomState, StormStation, AIState
from lost_island.multiplayer.protocol import PacketType, create_packet, parse_packet
from lost_island.multiplayer.lobby import MatchmakingEngine, LobbyRoom
from lost_island.database.persistence import PersistenceEngine

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LostIslandServer")

class GameServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765, db_path: str = "lost_island.db"):
        self.host = host
        self.port = port
        self.db = PersistenceEngine(db_path)
        self.matchmaker = MatchmakingEngine()
        
        # Connection tracking: ws -> {user_id, username, room_id, char_id}
        self.clients: Dict[Any, Dict[str, Any]] = {}
        # Room broadcast sets: room_id -> Set[ws]
        self.room_connections: Dict[str, Set[Any]] = {}
        # Active room simulation tasks: room_id -> asyncio.Task
        self.simulation_tasks: Dict[str, asyncio.Task] = {}
        self.running = False
        self._server = None

    async def broadcast_to_room(self, room_id: str, packet_type: str, payload: Dict[str, Any]):
        """Send message to all live sockets connected to a room."""
        conns = self.room_connections.get(room_id, set())
        if not conns:
            return

        message = create_packet(packet_type, payload)
        dead_conns = set()
        for ws in list(conns):
            try:
                await ws.send(message)
            except Exception:
                dead_conns.add(ws)

        for ws in dead_conns:
            conns.discard(ws)

    async def handle_connection(self, websocket):
        """Main connection lifecycle handler."""
        guest_id = f"guest_{id(websocket) % 10000}"
        self.clients[websocket] = {
            "user_id": guest_id,
            "username": f"Player_{guest_id[-4:]}",
            "room_id": None,
            "char_id": None
        }
        logger.info(f"New client connected: {self.clients[websocket]['username']}")

        try:
            async for raw_message in websocket:
                packet_type, payload = parse_packet(raw_message)
                if not packet_type:
                    continue
                await self.process_packet(websocket, packet_type, payload)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.handle_disconnect(websocket)

    async def process_packet(self, websocket, packet_type: str, payload: Dict[str, Any]):
        client = self.clients.get(websocket)
        if not client:
            return

        # 1. AUTH
        if packet_type == PacketType.AUTH:
            token = payload.get("token")
            session = self.db.validate_session(token) if token else None
            if session:
                client["user_id"] = session["user_id"]
                client["username"] = session["username"]
                await websocket.send(create_packet(PacketType.AUTH_RESULT, {
                    "success": True,
                    "user_id": session["user_id"],
                    "username": session["username"]
                }))
            else:
                # Treat as guest
                await websocket.send(create_packet(PacketType.AUTH_RESULT, {
                    "success": True,
                    "user_id": client["user_id"],
                    "username": client["username"]
                }))

        # 2. LIST ROOMS
        elif packet_type == PacketType.LIST_ROOMS:
            summary = self.matchmaker.get_all_rooms_summary()
            await websocket.send(create_packet(PacketType.ROOM_LIST, {"rooms": summary}))

        # 3. JOIN ROOM
        elif packet_type == PacketType.JOIN_ROOM:
            pref_id = payload.get("room_id")
            room = self.matchmaker.find_or_create_room(pref_id)
            room_id = room.room_id

            # Clean previous room if any
            if client["room_id"] and client["room_id"] in self.room_connections:
                self.room_connections[client["room_id"]].discard(websocket)

            client["room_id"] = room_id
            if room_id not in self.room_connections:
                self.room_connections[room_id] = set()
            self.room_connections[room_id].add(websocket)

            await websocket.send(create_packet(PacketType.ROOM_JOINED, {"room": room.to_dict()}))
            await self.broadcast_to_room(room_id, PacketType.ROOM_UPDATE, {"room": room.to_dict()})

        # 4. SELECT CHARACTER (Locks slot in 15-player room)
        elif packet_type == PacketType.SELECT_CHARACTER:
            room_id = client["room_id"]
            if not room_id:
                await websocket.send(create_packet(PacketType.ERROR, {"message": "You must join a room first."}))
                return

            room = self.matchmaker.get_room(room_id)
            char_id = payload.get("character_id")
            success, msg = room.lock_character(client["user_id"], client["username"], char_id, conn_ref=websocket)

            if success:
                client["char_id"] = char_id
                await self.broadcast_to_room(room_id, PacketType.ROOM_UPDATE, {
                    "room": room.to_dict(),
                    "announcement": f"{client['username']} selected {char_id.capitalize()}."
                })

                # Check if all 15 character slots are filled
                if room.is_fully_locked() and room.state == RoomState.WAITING_FOR_PLAYERS:
                    asyncio.create_task(self.start_room_countdown(room))
            else:
                await websocket.send(create_packet(PacketType.ERROR, {"message": msg}))

        # 5. FILL AI SLOTS (Testing helper to fill remaining of the 15 slots)
        elif packet_type == PacketType.FILL_AI_SLOTS:
            room_id = client["room_id"]
            if room_id:
                room = self.matchmaker.get_room(room_id)
                filled = room.fill_remaining_with_ai()
                await self.broadcast_to_room(room_id, PacketType.ROOM_UPDATE, {
                    "room": room.to_dict(),
                    "announcement": f"Filled {filled} open slots with autonomous companion bots."
                })
                if room.is_fully_locked() and room.state == RoomState.WAITING_FOR_PLAYERS:
                    asyncio.create_task(self.start_room_countdown(room))

        # 6. STORM ACTION
        elif packet_type == PacketType.STORM_ACTION:
            room_id = client["room_id"]
            char_id = client["char_id"]
            station_str = payload.get("station", "IDLE").upper()
            if room_id and char_id:
                room = self.matchmaker.get_room(room_id)
                if room and room.storm_sim:
                    try:
                        station = StormStation(station_str)
                        room.storm_sim.assign_boy_to_station(char_id, station)
                    except ValueError:
                        pass

        # 7. CHAT
        elif packet_type == PacketType.CHAT:
            room_id = client["room_id"]
            msg_text = payload.get("message", "").strip()
            if room_id and msg_text:
                await self.broadcast_to_room(room_id, PacketType.CHAT_MSG, {
                    "sender": client["username"],
                    "character_id": client["char_id"],
                    "message": msg_text
                })

    async def start_room_countdown(self, room: LobbyRoom):
        """Commence launch countdown once all 15 slots are locked."""
        room.state = RoomState.COUNTDOWN
        for remaining in range(room.countdown_seconds, 0, -1):
            await self.broadcast_to_room(room.room_id, PacketType.COUNTDOWN, {
                "seconds_remaining": remaining,
                "message": f"All 15 boys assembled! Sailing in {remaining}s..."
            })
            await asyncio.sleep(1.0)

        # Launch the storm prologue!
        room.start_storm_prologue()
        await self.broadcast_to_room(room.room_id, PacketType.GAME_START, {
            "mode": "PROLOGUE_STORM",
            "message": "THE TEMPEST HITS! All hands to stations!"
        })

        # Start simulation loop for this room
        sim_task = asyncio.create_task(self.run_room_simulation(room))
        self.simulation_tasks[room.room_id] = sim_task

    async def run_room_simulation(self, room: LobbyRoom):
        """Active simulation tick loop for the room."""
        logger.info(f"Simulation loop started for room {room.room_id}")
        try:
            # 1. Storm Loop
            while room.state == RoomState.IN_PROLOGUE_STORM and room.storm_sim:
                state = room.storm_sim.step()
                await self.broadcast_to_room(room.room_id, PacketType.STORM_TICK, state)

                if room.storm_sim.wrecked_on_shore:
                    # Transition to Island Survival!
                    await asyncio.sleep(2.0)
                    room.transition_to_island()
                    await self.broadcast_to_room(room.room_id, PacketType.GAME_START, {
                        "mode": "ISLAND_SURVIVAL",
                        "message": "Shipwrecked on Chairman Island! Act I begins."
                    })
                    break
                elif room.storm_sim.ship_sunk:
                    room.state = RoomState.FINISHED
                    await self.broadcast_to_room(room.room_id, PacketType.ERROR, {
                        "message": "The Sloughi has sunk into the ocean depths. Game Over."
                    })
                    return

                await asyncio.sleep(1.0)

            # 2. Island Survival Loop
            while room.state == RoomState.IN_ISLAND_SURVIVAL and room.island_sim:
                state = room.island_sim.step()
                await self.broadcast_to_room(room.room_id, PacketType.ISLAND_TICK, state)
                await asyncio.sleep(3.0)

        except asyncio.CancelledError:
            logger.info(f"Simulation cancelled for room {room.room_id}")
        except Exception as e:
            logger.error(f"Error in room {room.room_id} simulation: {e}", exc_info=True)

    async def handle_disconnect(self, websocket):
        client = self.clients.pop(websocket, None)
        if not client:
            return
        room_id = client.get("room_id")
        user_id = client.get("user_id")
        logger.info(f"Client disconnected: {client.get('username')}")

        if room_id:
            if room_id in self.room_connections:
                self.room_connections[room_id].discard(websocket)

            room = self.matchmaker.get_room(room_id)
            if room:
                freed_char = room.release_player(user_id)
                if freed_char:
                    await self.broadcast_to_room(room_id, PacketType.ROOM_UPDATE, {
                        "room": room.to_dict(),
                        "announcement": f"{client.get('username')} left the room. Slot {freed_char} is now open."
                    })

    async def start(self):
        """Start WebSocket server asynchronously."""
        self.running = True
        self._server = await websockets.serve(self.handle_connection, self.host, self.port)
        logger.info(f"Lost Island Game Server running on ws://{self.host}:{self.port}")

    async def stop(self):
        """Stop server and cancel all room simulation loops."""
        self.running = False
        for task in self.simulation_tasks.values():
            task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Lost Island Game Server stopped.")

