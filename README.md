# Lost Island: 15 Boys Survival - Hybrid Multiplayer/Offline RPG Engine

An advanced cross-platform hybrid RPG engine based on Jules Verne's classic survival narrative (*Two Years' Vacation* / *Deux ans de vacances*). The engine tracks the full canonical roster of **15 distinct schoolboys** stranded in the Pacific, supporting both an **Online 15-Player Multiplayer Mode** and an **Offline Autonomous AI Companion Mode**.

---

## Architecture Overview

```
                                  +-----------------------------+
                                  |    CANONICAL 15-BOY ROSTER   |
                                  |  (Gordon, Doniphan, Briant, |
                                  |   Moko, Baxter, Webb, etc.) |
                                  +--------------+--------------+
                                                 |
                        +------------------------+------------------------+
                        |                                                 |
                        v                                                 v
           [ONLINE MULTIPLAYER ENGINE]                        [OFFLINE COMPANION ENGINE]
       +---------------------------------+                +---------------------------------+
       | Asyncio WebSocket Matchmaker    |                | Human Player (1 Selected Boy)   |
       | 15-Slot Room Allocation Logic   |                | 14 Companion AI Agents          |
       | Real-Time Character Locking     |                | Utility-Based Finite State Mach |
       | Broadcast & Low-Latency Sync    |                | Modular Squad & Quest Commander |
       +----------------+----------------+                +----------------+----------------+
                        |                                                 |
                        +------------------------+------------------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    | PROLOGUE: SEA STORM      |
                                    | (Helm, Bilge, Carpentry, |
                                    |  Rigging, Brace, Waves)  |
                                    +------------+-------------+
                                                 |
                                                 v (Shipwreck on Reef)
                                    +--------------------------+
                                    | ACT I: ISLAND SURVIVAL   |
                                    | (Foraging, Camp Fire,    |
                                    |  Shelter, Day/Night)     |
                                    +------------+-------------+
                                                 |
                                                 v
                                    +--------------------------+
                                    | PERSISTENCE LAYER        |
                                    | (SQLite WAL Transactions,|
                                    |  Profiles, Saves, Quests)|
                                    +--------------------------+
```

---

## Core System Modules

### 1. The Canonical 15-Boy Roster (`lost_island/core/roster.py`)
Tracks all 15 characters from the classic chronicle, each equipped with distinct attributes (Leadership, Seamanship, Carpentry, Hunting, Foraging, Cooking, Morale Influence):
1. **Gordon** (14, American) - Elected Leader & Administrator
2. **Doniphan** (13, British) - Crack Marksman, Hunter & Scout
3. **Briant / Prim** (13, French) - Daring Navigator & Tactician
4. **Moko** (12, American) - Cabin Boy & Master Sailor
5. **Baxter** (13, British) - Master Craftsman & Engineer
6. **Cross** (13, British) - Loyal Defender & Scout
7. **Webb** (12, British) - Heavy Timber & Flotsam Specialist
8. **Service** (12, British) - Cheerful Camp Cook & Entertainer
9. **Garnett** (12, British) - Artisan & Accordion Player (Morale)
10. **Wilcox** (12, British) - Trapper & Pathfinder
11. **Jack** (10, French) - Swift Messenger & Runner
12. **Jenkins** (9, British) - Junior Pupil & Shellfish Forager
13. **Iverson** (9, British) - Junior Pupil & Signal Watcher
14. **Dole** (8, British) - Camp Helper & Hearth Guard
15. **Costar** (8, British) - Youngest Schoolboy & Inspiration

### 2. Matchmaking & Lobby Engine (`lost_island/multiplayer/lobby.py`, `server.py`)
- **15-Slot Room Allocation**: Server rooms hold an atomic 15-slot registry mapping each character ID to a connected player.
- **Atomic Character Locking**: When a client requests a character (e.g. `doniphan`), the slot is locked exclusively. If another player tries to choose that character in the same room, the server rejects the request.
- **Match Launching**: Once all 15 slots are uniquely occupied, a 5-second countdown initiates, followed by the synchronized launch of the Sea Storm Prologue.
- **Bot/AI Fillers**: Support for filling remaining slots with companion bots for instant testing and hybrid sessions (`FILL_AI_SLOTS`).

### 3. Offline Intelligent Companion Framework (`lost_island/ai/companion_fsm.py`, `quest_system.py`)
- **Utility-Based AI**: The 14 autonomous companions compute dynamic utility scores across states:
  - `FORAGING` (seeking food/wood when stockpiles deplete)
  - `BUILDING_SHELTER` (fortifying rafters with palm thatch)
  - `DEFENDING_CAMP` (patrolling the perimeter against predators)
  - `TENDING_FIRE` (stoking embers to maintain warmth)
  - `RESTING` (recovering stamina and healing injuries)
  - `RETREATING_TO_SHELTER` (triggered automatically at nightfall or severe gales)
  - `FOLLOWING_LEADER` (supporting human player)
- **Sea Storm Tactical Duty**: In the storm sequence, companions continuously evaluate boat stability:
  - If a rogue wave crashes $\rightarrow$ **BRACE**
  - If rudder stability falters $\rightarrow$ **HELM**
  - If hull breaches spring $\rightarrow$ **CARPENTRY**
  - If bilge water surges $\rightarrow$ **BILGE**
- **Squad Command System**: Human leader can issue global or targeted orders (`FORAGE`, `BUILD`, `DEFEND`, `RETREAT`, `FREE`).

### 4. Database & Profile Persistence Layer (`lost_island/database/persistence.py`)
- **Relational SQLite Schema** with Write-Ahead Logging (WAL) and atomic transactions.
- Tables:
  - `users`: Secure salted SHA-256 password hashes, creation & login timestamps.
  - `profiles`: User XP, total matches, storms survived, days lived.
  - `achievements`: Unique unlocking with transactional integrity (e.g. `STORM_SURVIVOR`).
  - `active_sessions`: Token validation for low-latency matchmaking handshakes.
  - `campaign_saves`: Serialized JSON states for camp infrastructure, roster conditions, and day/night cycles.

---

## Running the Engine

### 1. Run Offline Single-Player Mode
Control your selected boy while the 14 AI companions fight alongside you in the sea storm and island camp:
```powershell
python run_offline.py
```

### 2. Run Multiplayer Server
Start the dedicated WebSocket matchmaking server on port 8765:
```powershell
python run_server.py --port 8765
```

### 3. Run 15-Client Concurrent Load Benchmark
Simulates 15 simultaneous network connections filling all 15 character slots, triggering countdown, and syncing real-time storm ticks:
```powershell
python run_benchmark.py
```

### 4. Run Unit & Integration Test Suite
```powershell
python -m unittest discover tests
```

### 5. Web Client Dashboard
Open `web/index.html` in your browser to view the real-time slot roster matrix, station controls, and live game telemetry.

