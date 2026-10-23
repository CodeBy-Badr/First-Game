"""
Lost Island: 15 Boys Survival RPG Engine
Prologue Sea Storm Simulation: 'The Wreck of The Sloughi'
Real-time tactical boat stability management during a tempest at sea.
"""

import random
import time
from typing import Dict, List, Optional, Tuple
from lost_island.core.types import StormStation, BoyProfile, CharacterStats

class StormSimulation:
    def __init__(self, roster: Dict[str, BoyProfile], storm_duration_ticks: int = 40):
        self.roster = roster
        self.storm_duration_ticks = storm_duration_ticks
        self.current_tick = 0
        
        # Ship metrics
        self.hull_integrity: float = 100.0       # 0 = submerged/destroyed
        self.water_level: float = 10.0           # 0 (dry) to 100 (capsized)
        self.rudder_stability: float = 100.0     # 0 to 100
        self.rigging_tension: float = 50.0       # 0 (slack) to 100 (mast snaps)
        
        # Distance to shore (decreases each tick)
        self.distance_to_reef: float = 1000.0     # Meters to island barrier
        
        # Environmental state
        self.wind_speed_knots: float = 48.0
        self.wave_height_meters: float = 7.5
        self.rogue_wave_incoming: bool = False
        self.rogue_wave_timer: int = 0
        self.hull_breaches: int = 1
        
        # Narrative event log
        self.log_messages: List[str] = [
            "PROLOGUE: The Sloughi is caught in an unforgiving Pacific tempest!",
            "Wind howls at Force 10. The 15 boys must fight to keep the schooner afloat!"
        ]
        
        # Climax flag
        self.wrecked_on_shore: bool = False
        self.ship_sunk: bool = False

    def assign_boy_to_station(self, boy_id: str, station: StormStation) -> bool:
        """Assign a boy to an active action station."""
        if boy_id not in self.roster:
            return False
        boy = self.roster[boy_id]
        if boy.stats.health <= 0:
            return False
            
        boy.target_station = station
        boy.current_action = f"Manning station: {station.value}"
        self.log_messages.append(f"{boy.name} manned the {station.value} station.")
        return True

    def step(self) -> Dict[str, any]:
        """
        Advance storm simulation by 1 tick (representing 1-2 seconds of high-intensity survival).
        """
        if self.wrecked_on_shore or self.ship_sunk:
            return self.get_state()

        self.current_tick += 1
        
        # 1. Update Distance towards the reef barrier
        approach_speed = 22.0 + (self.wind_speed_knots * 0.2)
        self.distance_to_reef = max(0.0, self.distance_to_reef - approach_speed)

        # 2. Process Station Contributions from crew
        station_crews: Dict[StormStation, List[BoyProfile]] = {s: [] for s in StormStation}
        for boy in self.roster.values():
            if boy.stats.health > 0:
                station_crews[boy.target_station].append(boy)

        # Helm Steering
        helm_crew = station_crews[StormStation.HELM]
        if helm_crew:
            helm_power = sum(b.seamanship * (b.stats.stamina / 100.0) for b in helm_crew)
            self.rudder_stability = min(100.0, self.rudder_stability + helm_power * 1.5)
            for b in helm_crew:
                b.stats.stamina = max(10.0, b.stats.stamina - 1.2)
        else:
            self.rudder_stability = max(0.0, self.rudder_stability - 6.0)

        # Bilge Bailing
        bilge_crew = station_crews[StormStation.BILGE]
        if bilge_crew:
            bail_power = sum((b.seamanship * 0.5 + 4.0) * (b.stats.stamina / 100.0) for b in bilge_crew)
            self.water_level = max(0.0, self.water_level - bail_power * 1.2)
            for b in bilge_crew:
                b.stats.stamina = max(10.0, b.stats.stamina - 1.8)
                b.stats.warmth = max(30.0, b.stats.warmth - 1.0) # cold bilge water

        # Carpentry Repairs
        carp_crew = station_crews[StormStation.CARPENTRY]
        if carp_crew:
            repair_power = sum(b.carpentry * 0.8 for b in carp_crew)
            self.hull_integrity = min(100.0, self.hull_integrity + repair_power * 0.8)
            if self.hull_breaches > 0 and random.random() < (repair_power * 0.08):
                self.hull_breaches -= 1
                self.log_messages.append(f"A hull breach was secured by the carpentry team! Remaining breaches: {self.hull_breaches}")
            for b in carp_crew:
                b.stats.stamina = max(10.0, b.stats.stamina - 1.5)

        # Rigging Management
        rig_crew = station_crews[StormStation.RIGGING]
        if rig_crew:
            # Brings tension closer to optimal 50%
            rig_skill = sum(b.seamanship * 0.7 for b in rig_crew)
            if self.rigging_tension > 55.0:
                self.rigging_tension = max(50.0, self.rigging_tension - rig_skill)
            elif self.rigging_tension < 45.0:
                self.rigging_tension = min(50.0, self.rigging_tension + rig_skill)
            for b in rig_crew:
                b.stats.stamina = max(10.0, b.stats.stamina - 1.4)

        # 3. Environmental Influx & Hazard Generation
        # Water ingress based on hull breaches and integrity
        water_inflow = (self.hull_breaches * 3.5) + ((100.0 - self.hull_integrity) * 0.08)
        self.water_level = min(100.0, self.water_level + water_inflow)

        # Fluctuate wind & rigging tension
        self.rigging_tension += random.uniform(-4.0, 5.0)

        # 4. Rogue Wave Hazards
        if self.rogue_wave_incoming:
            self.rogue_wave_timer -= 1
            if self.rogue_wave_timer <= 0:
                self._resolve_rogue_wave_impact(station_crews)
                self.rogue_wave_incoming = False
        else:
            # Chance to spawn a rogue wave warning
            if random.random() < 0.18 and self.current_tick < self.storm_duration_ticks - 3:
                self.rogue_wave_incoming = True
                self.rogue_wave_timer = 2 # 2 ticks to brace!
                self.log_messages.append("WARNING: MONSTROUS ROGUE WAVE SPOTTED ON THE PORT BOW! ALL HANDS BRACE!")

        # 5. Spontaneous Hull Breach chance if rudder stability is low or water level high
        if self.rudder_stability < 30.0 and random.random() < 0.15:
            self.hull_breaches += 1
            self.hull_integrity = max(5.0, self.hull_integrity - 8.0)
            self.log_messages.append("CRACK! The unguided schooner struck a floating timber! Hull breach opened!")

        # 6. Check Sinking Failure Condition
        if self.water_level >= 95.0 or self.hull_integrity <= 0.0:
            self.ship_sunk = True
            self.log_messages.append("CRITICAL FAILURE: The Sloughi has foundered and capsized beneath the raging seas.")
            return self.get_state()

        # 7. Check Climax / Washing Ashore Transition
        if self.distance_to_reef <= 0 or self.current_tick >= self.storm_duration_ticks:
            self.wrecked_on_shore = True
            self.log_messages.append("CRASH! The Sloughi surges across the foaming reef and lodges firmly into sandy shoals!")
            self.log_messages.append("PROLOGUE COMPLETE: All surviving boys scramble out onto the sands of Chairman Island!")

        return self.get_state()

    def _resolve_rogue_wave_impact(self, station_crews: Dict[StormStation, List[BoyProfile]]):
        """Impact of rogue wave on vessel and crew."""
        self.log_messages.append("IMPACT! The massive breaker crashes over the deck!")
        impact_water = random.uniform(15.0, 25.0)
        self.water_level = min(98.0, self.water_level + impact_water)
        self.hull_integrity = max(10.0, self.hull_integrity - random.uniform(5.0, 12.0))

        # Check injuries for boys who did not BRACE
        for station, boys in station_crews.items():
            if station != StormStation.BRACE:
                for b in boys:
                    if random.random() < 0.35:
                        dmg = random.uniform(10.0, 25.0)
                        b.stats.health = max(15.0, b.stats.health - dmg)
                        b.stats.morale = max(20.0, b.stats.morale - 15.0)
                        b.stats.is_injured = True
                        b.stats.injury_desc = "Bruised & soaked by heavy breaker"
                        self.log_messages.append(f"{b.name} was knocked against the gunwale! (-{dmg:.1f} HP)")
            else:
                for b in boys:
                    # Braced successfully
                    b.stats.morale = min(100.0, b.stats.morale + 5.0)
                    self.log_messages.append(f"{b.name} braced firmly against the bulkhead and took no damage!")

    def get_state(self) -> Dict[str, any]:
        """Serialize complete storm state for networking and UI rendering."""
        return {
            "current_tick": self.current_tick,
            "total_ticks": self.storm_duration_ticks,
            "hull_integrity": round(self.hull_integrity, 1),
            "water_level": round(self.water_level, 1),
            "rudder_stability": round(self.rudder_stability, 1),
            "rigging_tension": round(self.rigging_tension, 1),
            "distance_to_reef": round(self.distance_to_reef, 1),
            "hull_breaches": self.hull_breaches,
            "rogue_wave_incoming": self.rogue_wave_incoming,
            "rogue_wave_timer": self.rogue_wave_timer,
            "wrecked_on_shore": self.wrecked_on_shore,
            "ship_sunk": self.ship_sunk,
            "recent_logs": self.log_messages[-6:],
            "crew_status": [
                {
                    "id": b.id,
                    "name": b.name,
                    "health": round(b.stats.health, 1),
                    "stamina": round(b.stats.stamina, 1),
                    "morale": round(b.stats.morale, 1),
                    "station": b.target_station.value,
                    "action": b.current_action,
                    "is_injured": b.stats.is_injured
                }
                for b in self.roster.values()
            ]
        }

