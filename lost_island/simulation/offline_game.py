"""
Lost Island: 15 Boys Survival RPG Engine
Offline Single-Player Game Engine.
Coordinates the human player, the 14 AI companions, storm prologue, and island survival.
"""

from typing import Dict, List, Optional, Tuple
from lost_island.core.types import BoyProfile, StormStation, AIState, GameMode
from lost_island.core.roster import create_fresh_roster, CANONICAL_ROSTER
from lost_island.simulation.storm import StormSimulation
from lost_island.simulation.island import IslandSimulation
from lost_island.ai.companion_fsm import CompanionBrain
from lost_island.ai.quest_system import SquadCommander
from lost_island.database.persistence import PersistenceEngine

class OfflineGameEngine:
    def __init__(self, human_boy_id: str = "gordon", db_path: str = "lost_island.db"):
        self.roster: Dict[str, BoyProfile] = create_fresh_roster()
        if human_boy_id not in self.roster:
            human_boy_id = "gordon"
        self.human_boy_id = human_boy_id
        self.db = PersistenceEngine(db_path)

        # Initialize AI brains for all 15 boys (1 human, 14 companions)
        self.brains: Dict[str, CompanionBrain] = {}
        for boy_id, boy in self.roster.items():
            is_human = (boy_id == self.human_boy_id)
            self.brains[boy_id] = CompanionBrain(boy, is_human_controlled=is_human)

        # Squad commander
        self.commander = SquadCommander(self.brains)

        # Prologue Storm Simulation
        self.storm_sim: Optional[StormSimulation] = StormSimulation(self.roster, storm_duration_ticks=25)
        # Island Simulation (instantiated after shipwreck)
        self.island_sim: Optional[IslandSimulation] = None

        self.phase = "PROLOGUE_STORM" # "PROLOGUE_STORM", "ISLAND_SURVIVAL", "GAME_OVER"
        self.turn = 0

    def get_human_profile(self) -> BoyProfile:
        return self.roster[self.human_boy_id]

    def set_human_station(self, station: StormStation) -> bool:
        """Assign human player to storm station."""
        if self.phase != "PROLOGUE_STORM" or not self.storm_sim:
            return False
        return self.storm_sim.assign_boy_to_station(self.human_boy_id, station)

    def step_storm(self) -> Tuple[Dict[str, any], List[str]]:
        """
        One simulation step during the Sea Storm Prologue.
        The 14 AI companions dynamically assess the ship's crisis and assign themselves.
        """
        if self.phase != "PROLOGUE_STORM" or not self.storm_sim:
            return {}, []

        self.turn += 1
        
        # 1. Companions decide stations based on ship hazards
        station_counts: Dict[StormStation, int] = {s: 0 for s in StormStation}
        human_station = self.roster[self.human_boy_id].target_station
        station_counts[human_station] = 1

        for boy_id, brain in self.brains.items():
            if not brain.is_human_controlled:
                station = brain.decide_storm_action(self.storm_sim, station_counts)
                self.storm_sim.assign_boy_to_station(boy_id, station)
                station_counts[station] = station_counts.get(station, 0) + 1

        # 2. Step storm physics
        state = self.storm_sim.step()

        # 3. Check for wreck or loss
        events = list(self.storm_sim.log_messages[-3:])
        if self.storm_sim.wrecked_on_shore:
            self.phase = "ISLAND_SURVIVAL"
            self.island_sim = IslandSimulation(self.roster)
            events.append("TRANSITION: The storm has cleared. The boys have washed ashore on Chairman Island!")
        elif self.storm_sim.ship_sunk:
            self.phase = "GAME_OVER"
            events.append("DEFEAT: The Sloughi has sunk into the deep ocean.")

        return state, events

    def step_island(self, human_action: Optional[AIState] = None) -> Tuple[Dict[str, any], List[str]]:
        """
        One simulation step during Island Survival.
        The 14 AI companions evaluate their utility matrix and perform work.
        """
        if self.phase != "ISLAND_SURVIVAL" or not self.island_sim:
            return {}, []

        self.turn += 1
        events = []

        # 1. Human boy action
        if human_action:
            human_brain = self.brains[self.human_boy_id]
            act_text = human_brain.execute_island_work(human_action, self.island_sim)
            events.append(f"Leader {act_text}")

        # 2. Autonomous companion utility decisions & work execution
        for boy_id, brain in self.brains.items():
            if not brain.is_human_controlled:
                state = brain.evaluate_island_utility(self.island_sim)
                act_msg = brain.execute_island_work(state, self.island_sim)
                # Keep logs concise by sampling important actions
                if state in (AIState.BUILDING_SHELTER, AIState.DEFENDING_CAMP, AIState.TENDING_FIRE):
                    events.append(act_msg)

        # 3. Step island consumption & events
        island_state = self.island_sim.step()

        # 4. Check Quests
        metrics = {
            "hull_integrity": 100.0,
            "distance_to_reef_covered": 1000.0,
            "shelter_level": self.island_sim.shelter_level,
            "food_rations": self.island_sim.food_rations,
            "defense_level": self.island_sim.defense_level
        }
        quest_msgs = self.commander.update_quests(metrics)
        events.extend(quest_msgs)

        return island_state, events

    def issue_command(self, order_text: str, target_boy: Optional[str] = None) -> str:
        """Issue a squad command to companions."""
        return self.commander.issue_squad_order(order_text, target_boy)

