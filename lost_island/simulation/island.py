"""
Lost Island: 15 Boys Survival RPG Engine
Core Island Survival Simulation: Chairman Island
Camp infrastructure, resource management, day/night cycles, and group welfare.
"""

import random
from typing import Dict, List, Optional
from lost_island.core.types import (
    BoyProfile, TimeOfDay, WeatherType, AIState
)

class IslandSimulation:
    def __init__(self, roster: Dict[str, BoyProfile]):
        self.roster = roster
        self.day: int = 1
        self.time_of_day: TimeOfDay = TimeOfDay.DAWN
        self.weather: WeatherType = WeatherType.CLEAR
        
        # Camp Stockpiles & Infrastructure
        self.wood: float = 25.0
        self.food_rations: float = 30.0
        self.fresh_water: float = 40.0
        self.fire_intensity: float = 60.0       # 0 = unlit, 100 = roaring bonfire
        self.shelter_level: float = 15.0        # 0 = open sand, 100 = French Den fortified
        self.defense_level: float = 10.0        # 0 = exposed, 100 = palisade barricaded
        
        # Discovery / milestones
        self.cave_discovered: bool = False
        self.signal_flag_built: bool = False
        
        # Environmental and narrative logs
        self.log_messages: List[str] = [
            "ACT I: The boys gather on the windswept shore of Chairman Island.",
            "Flotsam from The Sloughi litters the reef. A new survival campaign begins."
        ]

    def advance_time(self):
        """Advance time through DAWN -> DAY -> DUSK -> NIGHT -> DAWN (next day)."""
        cycle = [TimeOfDay.DAWN, TimeOfDay.DAY, TimeOfDay.DUSK, TimeOfDay.NIGHT]
        current_idx = cycle.index(self.time_of_day)
        next_idx = (current_idx + 1) % len(cycle)
        self.time_of_day = cycle[next_idx]

        if self.time_of_day == TimeOfDay.DAWN:
            self.day += 1
            self.log_messages.append(f"=== Dawn breaks on Day {self.day} ===")
            self._roll_weather()
        elif self.time_of_day == TimeOfDay.NIGHT:
            self.log_messages.append("Darkness descends across Chairman Island. Temperatures plummet.")

    def _roll_weather(self):
        """Randomize regional weather."""
        roll = random.random()
        if roll < 0.5:
            self.weather = WeatherType.CLEAR
        elif roll < 0.8:
            self.weather = WeatherType.OVERCAST
        elif roll < 0.95:
            self.weather = WeatherType.RAIN
        else:
            self.weather = WeatherType.TEMPEST
        self.log_messages.append(f"Weather report: skies are now {self.weather.value}.")

    def step(self) -> Dict[str, any]:
        """
        Advance one island simulation tick (consumes supplies, handles camp stats, triggers events).
        """
        # Fire burn down
        burn_rate = 2.0 if self.weather != WeatherType.RAIN else 4.5
        self.fire_intensity = max(0.0, self.fire_intensity - burn_rate)

        # Survival consumption per tick for all 15 boys
        active_boys = [b for b in self.roster.values() if b.stats.health > 0]
        boy_count = len(active_boys)

        water_consumed = boy_count * 0.15
        food_consumed = boy_count * 0.12

        self.fresh_water = max(0.0, self.fresh_water - water_consumed)
        self.food_rations = max(0.0, self.food_rations - food_consumed)

        # Update each boy's physical condition
        for boy in active_boys:
            # Hunger increments if food is depleted
            if self.food_rations <= 0.1:
                boy.stats.hunger = min(100.0, boy.stats.hunger + 3.0)
                boy.stats.morale = max(10.0, boy.stats.morale - 2.0)
            else:
                boy.stats.hunger = max(0.0, boy.stats.hunger - 1.5)

            # Warmth depends on fire, shelter, and time of day
            if self.time_of_day == TimeOfDay.NIGHT:
                night_cold = 10.0 if self.shelter_level < 50 else 3.0
                if self.fire_intensity < 20.0:
                    boy.stats.warmth = max(10.0, boy.stats.warmth - night_cold)
                else:
                    boy.stats.warmth = min(100.0, boy.stats.warmth + 2.0)
            else:
                boy.stats.warmth = min(100.0, boy.stats.warmth + 3.0)

            # Health degradation on extreme hunger or hypothermia
            if boy.stats.hunger > 80.0 or boy.stats.warmth < 25.0:
                boy.stats.health = max(5.0, boy.stats.health - 2.0)
            elif boy.stats.hunger < 30.0 and boy.stats.warmth > 70.0:
                boy.stats.health = min(100.0, boy.stats.health + 1.0)

        # Check random event
        if random.random() < 0.15:
            self._trigger_random_event()

        return self.get_state()

    def _trigger_random_event(self):
        """Dynamic island encounters and discoveries."""
        events = [
            ("FLOTSAM_DISCOVERY", "The tide washed up a ship's cask containing salt pork and sailcloth! (+8 Food, +5 Wood)"),
            ("PREDATOR_PROWL", "A pack of wild jackals prowled near the edge of camp! The guards stood watch."),
            ("RAIN_BARREL_FILL", "A sudden fresh shower filled the hollowed rock cisterns! (+15 Fresh Water)"),
            ("CAVE_CLUE", "Doniphan and Wilcox uncovered an ancient carved path leading toward French Den cave!")
        ]
        ev_type, text = random.choice(events)
        self.log_messages.append(f"EVENT: {text}")

        if ev_type == "FLOTSAM_DISCOVERY":
            self.food_rations += 8.0
            self.wood += 5.0
        elif ev_type == "RAIN_BARREL_FILL":
            self.fresh_water += 15.0
        elif ev_type == "CAVE_CLUE":
            self.cave_discovered = True

    def get_state(self) -> Dict[str, any]:
        """Serialize complete island camp state."""
        return {
            "day": self.day,
            "time_of_day": self.time_of_day.value,
            "weather": self.weather.value,
            "wood": round(self.wood, 1),
            "food_rations": round(self.food_rations, 1),
            "fresh_water": round(self.fresh_water, 1),
            "fire_intensity": round(self.fire_intensity, 1),
            "shelter_level": round(self.shelter_level, 1),
            "defense_level": round(self.defense_level, 1),
            "cave_discovered": self.cave_discovered,
            "signal_flag_built": self.signal_flag_built,
            "recent_logs": self.log_messages[-6:],
            "roster": [
                {
                    "id": b.id,
                    "name": b.name,
                    "health": round(b.stats.health, 1),
                    "stamina": round(b.stats.stamina, 1),
                    "hunger": round(b.stats.hunger, 1),
                    "morale": round(b.stats.morale, 1),
                    "warmth": round(b.stats.warmth, 1),
                    "ai_state": b.ai_state.value,
                    "current_action": b.current_action
                }
                for b in self.roster.values()
            ]
        }

