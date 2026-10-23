"""
Lost Island: 15 Boys Survival RPG
Automated 15-Client Concurrent Matchmaking & Storm Load Benchmark.
Demonstrates 15 concurrent network connections uniquely filling all 15 character slots,
launching the synchronized sea storm prologue, and exchanging real-time packets.
"""

import asyncio
import json
import time
import websockets
from lost_island.core.roster import CANONICAL_ROSTER
from lost_island.multiplayer.server import GameServer
from lost_island.multiplayer.protocol import PacketType, create_packet, parse_packet

TEST_HOST = "127.0.0.1"
TEST_PORT = 8799

async def simulated_client(player_idx: int, char_id: str, results: dict):
    uri = f"ws://{TEST_HOST}:{TEST_PORT}"
    player_name = f"NetPlayer_{char_id.capitalize()}"
    
    try:
        async with websockets.connect(uri) as ws:
            # 1. Join matchmaking room
            await ws.send(create_packet(PacketType.JOIN_ROOM, {"room_id": "test_storm_arena"}))
            
            # Read response
            resp = await ws.recv()
            p_type, payload = parse_packet(resp)
            
            # 2. Lock character slot
            await ws.send(create_packet(PacketType.SELECT_CHARACTER, {"character_id": char_id}))
            
            received_game_start = False
            ticks_received = 0
            
            # Listen for updates
            timeout_end = time.time() + 12.0
            while time.time() < timeout_end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    p_type, payload = parse_packet(msg)
                    
                    if p_type == PacketType.GAME_START:
                        received_game_start = True
                        results[f"{char_id}_game_start"] = True
                        
                        # Send station action
                        station = "CARPENTRY" if char_id == "baxter" else ("HELM" if char_id == "briant" else "BILGE")
                        await ws.send(create_packet(PacketType.STORM_ACTION, {"station": station}))

                    elif p_type == PacketType.STORM_TICK:
                        ticks_received += 1
                        if ticks_received >= 2:
                            break
                except asyncio.TimeoutError:
                    break

            results[char_id] = {
                "player_name": player_name,
                "character": char_id,
                "game_started": received_game_start,
                "ticks_received": ticks_received
            }
    except Exception as e:
        results[char_id] = {"error": str(e)}

async def main():
    print("=" * 70)
    print(" LOST ISLAND: 15-PLAYER MULTIPLAYER MATCHMAKING LOAD BENCHMARK")
    print("=" * 70)
    print(f"Launching internal GameServer on ws://{TEST_HOST}:{TEST_PORT}...")
    
    server = GameServer(host=TEST_HOST, port=TEST_PORT, db_path="benchmark_test.db")
    await server.start()
    await asyncio.sleep(0.5)

    roster_keys = list(CANONICAL_ROSTER.keys())
    assert len(roster_keys) == 15, "Roster must have exactly 15 characters!"
    print(f"Roster confirmed: 15 distinct characters:")
    print("  " + ", ".join(k.capitalize() for k in roster_keys))
    print("\nSpawning 15 concurrent asynchronous WebSocket clients...")

    results = {}
    client_tasks = [
        simulated_client(i + 1, char_id, results)
        for i, char_id in enumerate(roster_keys)
    ]

    start_time = time.time()
    await asyncio.gather(*client_tasks)
    elapsed = time.time() - start_time

    print(f"\nAll 15 client sessions concluded in {elapsed:.2f} seconds.")
    print("-" * 70)
    print(f"{'CHARACTER':<15} | {'PLAYER':<20} | {'STARTED?':<10} | {'TICKS SYNCED':<12}")
    print("-" * 70)
    
    all_started = True
    for cid in roster_keys:
        res = results.get(cid, {})
        started = res.get("game_started", False)
        ticks = res.get("ticks_received", 0)
        pname = res.get("player_name", "Unknown")
        print(f"{cid.capitalize():<15} | {pname:<20} | {str(started):<10} | {ticks:<12}")
        if not started:
            all_started = False

    print("-" * 70)
    if all_started:
        print(">>> BENCHMARK SUCCESS: All 15 distinct character slots filled & synchronized! <<<")
    else:
        print(">>> BENCHMARK COMPLETED with partial triggers. <<<")

    await server.stop()
    import os
    if os.path.exists("benchmark_test.db"):
        os.remove("benchmark_test.db")

if __name__ == "__main__":
    asyncio.run(main())

