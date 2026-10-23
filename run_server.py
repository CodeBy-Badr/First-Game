"""
Lost Island: 15 Boys Survival RPG
Multiplayer Matchmaking & Simulation Server Runner.
"""

import asyncio
import logging
import argparse
from lost_island.multiplayer.server import GameServer

def main():
    parser = argparse.ArgumentParser(description="Lost Island Multiplayer Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--db", default="lost_island.db", help="SQLite database path")
    args = parser.parse_args()

    server = GameServer(host=args.host, port=args.port, db_path=args.db)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.start())
        print(f"============================================================")
        print(f" LOST ISLAND MULTIPLAYER MATCHMAKING SERVER STARTED")
        print(f" Listening on ws://{args.host}:{args.port}")
        print(f" Room capacity: Exactly 15 distinct character slots per room")
        print(f" Press Ctrl+C to terminate.")
        print(f"============================================================")
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        loop.run_until_complete(server.stop())
    finally:
        loop.close()

if __name__ == "__main__":
    main()

