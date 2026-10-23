"""
Lost Island: 15 Boys Survival RPG Engine
Intelligent Companion Framework: Utility-Weighted Finite-State Machine (FSM).
Controls the 14 autonomous companions in offline single-player mode.
"""

import random
from typing import Dict, List, Optional
from lost_island.core.types import (
    BoyProfile, StormStation, AIState, TimeOfDay, WeatherType
)
from lost_island.simulation.storm import StormSimulation
from lost_island.simulation.island import IslandSimulation

class CompanionBrain:
    """Individual AI cognitive controller for a single boy companion."""
    def __init__(self, boy: BoyProfile, is_human_controlled: bool = False):
        self.boy = boy
        self.is_human_controlled = is_human_controlled
        self.forced_order: Optional[AIState] = None

    def decide_storm_action(self, storm: StormSimulation, station_occupancy: Dict[StormStation, int]) -> StormStation:
        """Dynamic tactical assignment during the Sea Storm Prologue."""
        if self.is_human_controlled:
            return self.boy.target_station

        # Rule 1: Emergency BRACE takes precedence if rogue wave is crashing
        if storm.rogue_wave_incoming:
            return StormStation.BRACE

        # Rule 2: Prioritize critical uncrewed helm if boat is losing steerage
        if storm.rudder_stability < 60.0 and station_occupancy.get(StormStation.HELM, 0) == 0:
            if self.boy.seamanship >= 6:
                return StormStation.HELM

        # Rule 3: Carpentry team if hull breaches exist
        if storm.hull_breaches > 0 and station_occupancy.get(StormStation.CARPENTRY, 0) < 3:
            if self.boy.carpentry >= 6 or self.boy.id == "baxter":
                return StormStation.CARPENTRY

        # Rule 4: Bilge pump if water flooding
        if storm.water_level > 35.0 and station_occupancy.get(StormStation.BILGE, 0) < 5:
            return StormStation.BILGE

        # Rule 5: Rigging balance
        if abs(storm.rigging_tension - 50.0) > 20.0 and station_occupancy.get(StormStation.RIGGING, 0) < 2:
            if self.boy.seamanship >= 5:
                return StormStation.RIGGING

        # Rule 6: Trait-based default
        if self.boy.carpentry >= 8:
            return StormStation.CARPENTRY
        elif self.boy.seamanship >= 8:
            return StormStation.HELM if station_occupancy.get(StormStation.HELM, 0) < 2 else StormStation.RIGGING
        else:
            return StormStation.BILGE

    def evaluate_island_utility(self, island: IslandSimulation) -> AIState:
        """
        Evaluate utility scoring matrix for island survival actions.
        Returns the highest-utility AIState.
        """
        if self.is_human_controlled:
            return self.boy.ai_state

        if self.forced_order:
            return self.forced_order

        # Environmental trigger: Nightfall or Severe Tempest forces boys to shelter
        if island.time_of_day == TimeOfDay.NIGHT or island.weather == WeatherType.TEMPEST:
            # Older protectors might still defend, younger boys MUST shelter
            if self.boy.age <= 10 or self.boy.stats.warmth < 40.0:
                return AIState.RETREATING_TO_SHELTER

        scores: Dict[AIState, float] = {
            AIState.RESTING: 0.0,
            AIState.TENDING_FIRE: 0.0,
            AIState.FORAGING: 0.0,
            AIState.BUILDING_SHELTER: 0.0,
            AIState.DEFENDING_CAMP: 0.0,
            AIState.FOLLOWING_LEADER: 10.0, # baseline
            AIState.RETREATING_TO_SHELTER: 5.0
        }

        # 1. Resting Utility (stamina/health depletion)
        if self.boy.stats.stamina < 30.0:
            scores[AIState.RESTING] += (30.0 - self.boy.stats.stamina) * 2.5
        if self.boy.stats.is_injured:
            scores[AIState.RESTING] += 40.0

        # 2. Fire Tending Utility (low fire or wet weather)
        if island.fire_intensity < 35.0 and island.wood >= 2.0:
            scores[AIState.TENDING_FIRE] += (40.0 - island.fire_intensity) * 1.5
            if self.boy.cooking >= 7:
                scores[AIState.TENDING_FIRE] += 20.0

        # 3. Foraging Utility (low food or water)
        food_deficit = max(0.0, 50.0 - island.food_rations)
        scores[AIState.FORAGING] += food_deficit * 1.2
        scores[AIState.FORAGING] += self.boy.foraging * 3.5

        # 4. Building Shelter Utility
        if island.shelter_level < 80.0 and island.wood >= 5.0:
            scores[AIState.BUILDING_SHELTER] += (80.0 - island.shelter_level) * 0.8
            scores[AIState.BUILDING_SHELTER] += self.boy.carpentry * 4.0

        # 5. Defending Camp Utility
        if island.defense_level < 50.0 or island.time_of_day in (TimeOfDay.DUSK, TimeOfDay.NIGHT):
            scores[AIState.DEFENDING_CAMP] += 25.0
            scores[AIState.DEFENDING_CAMP] += self.boy.hunting * 3.0

        # 6. Specific character affinities
        if self.boy.id == "doniphan":
            scores[AIState.DEFENDING_CAMP] += 25.0
        elif self.boy.id == "baxter":
            scores[AIState.BUILDING_SHELTER] += 30.0
        elif self.boy.id in ("service", "moko"):
            scores[AIState.TENDING_FIRE] += 20.0
        elif self.boy.id in ("dole", "costar", "jenkins", "iverson"):
            # Younger boys stick close to camp or follow leader
            scores[AIState.FOLLOWING_LEADER] += 30.0
            scores[AIState.FORAGING] += 10.0
            scores[AIState.DEFENDING_CAMP] = 0.0 # too dangerous

        # Select maximum score
        best_state = max(scores.items(), key=lambda kv: kv[1])[0]
        return best_state

    def execute_island_work(self, state: AIState, island: IslandSimulation) -> str:
        """Execute selected state work tick and apply game effects."""
        self.boy.ai_state = state

        if state == AIState.RESTING:
            self.boy.stats.stamina = min(100.0, self.boy.stats.stamina + 10.0)
            self.boy.stats.morale = min(100.0, self.boy.stats.morale + 3.0)
            if self.boy.stats.is_injured and random.random() < 0.25:
                self.boy.stats.is_injured = False
                self.boy.stats.injury_desc = None
                action = f"{self.boy.name} recovered from their injuries after resting."
            else:
                action = f"{self.boy.name} is resting to recover stamina."

        elif state == AIState.TENDING_FIRE:
            if island.wood >= 2.0:
                island.wood -= 1.5
                gain = 12.0 + (self.boy.cooking * 0.8)
                island.fire_intensity = min(100.0, island.fire_intensity + gain)
                action = f"{self.boy.name} stoked the hearth fire (+{gain:.0f}% warmth)."
            else:
                action = f"{self.boy.name} searched for dry twigs to keep embers alive."

        elif state == AIState.FORAGING:
            find_roll = random.random()
            if find_roll < 0.6:
                yield_food = round(random.uniform(2.0, 5.0) + (self.boy.foraging * 0.4), 1)
                island.food_rations += yield_food
                action = f"{self.boy.name} harvested wild berries and edible roots (+{yield_food} food)."
            else:
                yield_wood = round(random.uniform(2.0, 6.0) + (self.boy.foraging * 0.5), 1)
                island.wood += yield_wood
                action = f"{self.boy.name} gathered drift timber along the beach (+{yield_wood} wood)."
            self.boy.stats.stamina = max(10.0, self.boy.stats.stamina - 4.0)

        elif state == AIState.BUILDING_SHELTER:
            if island.wood >= 4.0:
                island.wood -= 3.0
                gain = round(random.uniform(2.5, 6.0) + (self.boy.carpentry * 0.6), 1)
                island.shelter_level = min(100.0, island.shelter_level + gain)
                action = f"{self.boy.name} lashed palm rafters to improve the shelter (+{gain:.1f}%)."
            else:
                action = f"{self.boy.name} prepared framing posts (awaiting wood)."
            self.boy.stats.stamina = max(10.0, self.boy.stats.stamina - 5.0)

        elif state == AIState.DEFENDING_CAMP:
            gain = round(random.uniform(1.5, 4.0) + (self.boy.hunting * 0.5), 1)
            island.defense_level = min(100.0, island.defense_level + gain)
            action = f"{self.boy.name} patrolled the perimeter and carved stakes (+{gain:.1f}% defense)."
            self.boy.stats.stamina = max(10.0, self.boy.stats.stamina - 3.5)

        elif state == AIState.RETREATING_TO_SHELTER:
            self.boy.stats.warmth = min(100.0, self.boy.stats.warmth + 5.0)
            action = f"{self.boy.name} huddled safely inside the shelter away from the cold."

        elif state == AIState.FOLLOWING_LEADER:
            action = f"{self.boy.name} is standing by and following the player leader."
        else:
            action = f"{self.boy.name} is standing watch."

        self.boy.current_action = action
        return action

