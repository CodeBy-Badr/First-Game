"""
Lost Island: 15 Boys Survival RPG Engine
Modular Quest and Squad Command System.
Orchestrates mission goals, player orders, and environment triggers.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from lost_island.core.types import AIState, TimeOfDay, StormStation
from lost_island.ai.companion_fsm import CompanionBrain

@dataclass
class QuestObjective:
    key: str
    description: str
    target_value: float
    current_value: float = 0.0
    is_completed: bool = False

class Quest:
    def __init__(self, quest_id: str, title: str, description: str, objectives: List[QuestObjective]):
        self.quest_id = quest_id
        self.title = title
        self.description = description
        self.objectives = objectives
        self.is_completed = False

    def check_progress(self, metrics: Dict[str, float]) -> bool:
        """Check and update completion of all objectives."""
        all_done = True
        for obj in self.objectives:
            if obj.key in metrics:
                obj.current_value = metrics[obj.key]
            if obj.current_value >= obj.target_value:
                obj.is_completed = True
            else:
                all_done = False
        self.is_completed = all_done
        return self.is_completed

class SquadCommander:
    """Manages player orders and high-level quest triggers for companions."""
    def __init__(self, companion_brains: Dict[str, CompanionBrain]):
        self.brains = companion_brains
        self.active_quests: List[Quest] = self._init_default_quests()
        self.current_order: Optional[str] = None

    def _init_default_quests(self) -> List[Quest]:
        return [
            Quest(
                quest_id="prologue_storm",
                title="The Wreck of The Sloughi",
                description="Manage ship stability and stay afloat until the schooner breaches the coastal reef.",
                objectives=[
                    QuestObjective("hull_integrity", "Keep hull integrity above 0", 1.0),
                    QuestObjective("distance_to_reef_covered", "Reach Chairman Island shore", 1000.0)
                ]
            ),
            Quest(
                quest_id="act1_shelter",
                title="Haven on Chairman Island",
                description="Establish fortified shelter and store sufficient food before the first gale strikes.",
                objectives=[
                    QuestObjective("shelter_level", "Build shelter to 50%", 50.0),
                    QuestObjective("food_rations", "Stockpile 45 food rations", 45.0),
                    QuestObjective("defense_level", "Construct perimeter stakes to 40%", 40.0)
                ]
            )
        ]

    def issue_squad_order(self, order_name: str, target_boy_id: Optional[str] = None) -> str:
        """Issue an explicit high-priority squad order from the human leader."""
        order_name = order_name.upper()
        self.current_order = order_name
        
        target_state: Optional[AIState] = None
        if order_name in ("FORAGE", "GATHER_FOOD"):
            target_state = AIState.FORAGING
        elif order_name in ("BUILD", "FORTIFY", "BUILD_SHELTER"):
            target_state = AIState.BUILDING_SHELTER
        elif order_name in ("DEFEND", "GUARD", "DEFEND_CAMP"):
            target_state = AIState.DEFENDING_CAMP
        elif order_name in ("RETREAT", "SLEEP", "SHELTER"):
            target_state = AIState.RETREATING_TO_SHELTER
        elif order_name in ("FOLLOW", "REGROUP"):
            target_state = AIState.FOLLOWING_LEADER
        elif order_name in ("FREE", "AUTONOMOUS", "RESET"):
            target_state = None

        if target_boy_id:
            if target_boy_id in self.brains and not self.brains[target_boy_id].is_human_controlled:
                self.brains[target_boy_id].forced_order = target_state
                boy_name = self.brains[target_boy_id].boy.name
                return f"Assigned order '{order_name}' specifically to {boy_name}."
            return f"Invalid or human-controlled target boy: {target_boy_id}"
        else:
            # Broadcast to all companions
            affected = 0
            for brain in self.brains.values():
                if not brain.is_human_controlled:
                    brain.forced_order = target_state
                    affected += 1
            return f"Broadcast squad order '{order_name}' to all {affected} AI companions."

    def on_nightfall_trigger(self) -> List[str]:
        """Triggered automatically when night falls across the island."""
        events = []
        for brain in self.brains.values():
            if not brain.is_human_controlled:
                # Young pupils automatically retreat to shelter
                if brain.boy.age <= 11:
                    brain.forced_order = AIState.RETREATING_TO_SHELTER
                    events.append(f"{brain.boy.name} scurried to the warm shelter as night fell.")
                elif brain.boy.id == "doniphan" or brain.boy.hunting >= 8:
                    # Guards stay on watch
                    brain.forced_order = AIState.DEFENDING_CAMP
                    events.append(f"{brain.boy.name} lit a torch to guard the camp perimeter through the night.")
        return events

    def update_quests(self, metrics: Dict[str, float]) -> List[str]:
        """Update quest states and return completed announcements."""
        completed = []
        for q in self.active_quests:
            if not q.is_completed:
                if q.check_progress(metrics):
                    completed.append(f"MISSION ACCOMPLISHED: {q.title} - {q.description}")
        return completed

