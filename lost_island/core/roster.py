"""
Lost Island: 15 Boys Survival RPG Engine
The Canonical 15-Boy Roster with historical archetypes and skill specializations.
Based on Jules Verne's 'Two Years' Vacation' (Deux ans de vacances).
"""

from typing import Dict, List
from lost_island.core.types import BoyProfile, CharacterStats, AIState

CANONICAL_ROSTER: Dict[str, BoyProfile] = {
    "gordon": BoyProfile(
        id="gordon",
        name="Gordon",
        age=14,
        nationality="American",
        archetype="Elected Leader & Administrator",
        leadership=10,
        seamanship=5,
        carpentry=6,
        hunting=5,
        foraging=6,
        cooking=5,
        morale_influence=9,
        description="Prudent, methodical, and fair-minded. Natural arbitrator who keeps order and organizes supplies."
    ),
    "doniphan": BoyProfile(
        id="doniphan",
        name="Doniphan",
        age=13,
        nationality="British",
        archetype="Crack Marksman & Hunter",
        leadership=7,
        seamanship=5,
        carpentry=3,
        hunting=10,
        foraging=7,
        cooking=4,
        morale_influence=6,
        description="Aristocratic, daring, and an expert shot. Proud and competitive, excels in exploring and defense."
    ),
    "briant": BoyProfile(
        id="briant",
        name="Briant (Prim)",
        age=13,
        nationality="French",
        archetype="Daring Navigator & Tactician",
        leadership=9,
        seamanship=9,
        carpentry=6,
        hunting=6,
        foraging=7,
        cooking=5,
        morale_influence=9,
        description="Quick-witted, heroic, and empathetic. Brilliant at sea navigation and high-stakes split-second decisions."
    ),
    "moko": BoyProfile(
        id="moko",
        name="Moko",
        age=12,
        nationality="American",
        archetype="Cabin Boy & Master Sailor",
        leadership=6,
        seamanship=10,
        carpentry=7,
        hunting=5,
        foraging=8,
        cooking=9,
        morale_influence=8,
        description="The schooner's apprentice sailor. Knows rigging, nautical knots, fishing, and camp cookery like second nature."
    ),
    "baxter": BoyProfile(
        id="baxter",
        name="Baxter",
        age=13,
        nationality="British",
        archetype="Master Craftsman & Engineer",
        leadership=5,
        seamanship=6,
        carpentry=10,
        hunting=4,
        foraging=6,
        cooking=4,
        morale_influence=7,
        description="Inventive and practical craftsman. Capable of building fortifications, tools, windlasses, and water traps."
    ),
    "cross": BoyProfile(
        id="cross",
        name="Cross",
        age=13,
        nationality="British",
        archetype="Loyal Defender & Scout",
        leadership=4,
        seamanship=4,
        carpentry=5,
        hunting=8,
        foraging=6,
        cooking=4,
        morale_influence=5,
        description="Doniphan's loyal cousin. Dependable sentinel, brave in confrontations, and stalwart watchman."
    ),
    "webb": BoyProfile(
        id="webb",
        name="Webb",
        age=12,
        nationality="British",
        archetype="Resource Gatherer",
        leadership=4,
        seamanship=5,
        carpentry=6,
        hunting=6,
        foraging=8,
        cooking=4,
        morale_influence=5,
        description="Hardy and determined pupil. Specializes in collecting heavy timber, salvage, and shoreline flotsam."
    ),
    "service": BoyProfile(
        id="service",
        name="Service",
        age=12,
        nationality="British",
        archetype="Camp Cook & Entertainer",
        leadership=5,
        seamanship=4,
        carpentry=5,
        hunting=4,
        foraging=7,
        cooking=10,
        morale_influence=10,
        description="Irrepressibly cheerful Robinson Crusoe enthusiast. Keeps morale soaring with humor and hot stews."
    ),
    "garnett": BoyProfile(
        id="garnett",
        name="Garnett",
        age=12,
        nationality="British",
        archetype="Camp Artisan & Musician",
        leadership=4,
        seamanship=5,
        carpentry=6,
        hunting=4,
        foraging=6,
        cooking=6,
        morale_influence=8,
        description="Service's inseparable friend. Plays the accordion to soothe spirits during dark tempestuous nights."
    ),
    "wilcox": BoyProfile(
        id="wilcox",
        name="Wilcox",
        age=12,
        nationality="British",
        archetype="Trapper & Pathfinder",
        leadership=4,
        seamanship=4,
        carpentry=5,
        hunting=8,
        foraging=7,
        cooking=4,
        morale_influence=5,
        description="Quiet, tenacious boy skilled in setting bird snares, tracking game paths, and finding freshwater springs."
    ),
    "jack": BoyProfile(
        id="jack",
        name="Jack",
        age=10,
        nationality="French",
        archetype="Swift Messenger & Runner",
        leadership=3,
        seamanship=5,
        carpentry=4,
        hunting=4,
        foraging=8,
        cooking=4,
        morale_influence=6,
        description="Briant's younger brother. Swift on foot, eager to redeem himself, and notices hidden clues."
    ),
    "jenkins": BoyProfile(
        id="jenkins",
        name="Jenkins",
        age=9,
        nationality="British",
        archetype="Junior Forager",
        leadership=2,
        seamanship=3,
        carpentry=3,
        hunting=3,
        foraging=7,
        cooking=5,
        morale_influence=6,
        description="Eager junior boy who gathers shellfish, dry firewood, and wild berries around camp."
    ),
    "iverson": BoyProfile(
        id="iverson",
        name="Iverson",
        age=9,
        nationality="British",
        archetype="Junior Scout & Signal Boy",
        leadership=2,
        seamanship=3,
        carpentry=3,
        hunting=3,
        foraging=7,
        cooking=4,
        morale_influence=6,
        description="Attentive junior boy who maintains signal smoke and assists with shoreline salvage."
    ),
    "dole": BoyProfile(
        id="dole",
        name="Dole",
        age=8,
        nationality="British",
        archetype="Camp Helper",
        leadership=1,
        seamanship=2,
        carpentry=2,
        hunting=2,
        foraging=6,
        cooking=5,
        morale_influence=7,
        description="One of the youngest pupils. Loved by older boys; helps tend herbs and watch the shelter fire."
    ),
    "costar": BoyProfile(
        id="costar",
        name="Costar",
        age=8,
        nationality="British",
        archetype="Camp Mascot & Helper",
        leadership=1,
        seamanship=2,
        carpentry=2,
        hunting=2,
        foraging=6,
        cooking=5,
        morale_influence=8,
        description="The smallest boy of Chairman College. His safety inspires the elder boys to fight fiercely to survive."
    )
}

def create_fresh_roster() -> Dict[str, BoyProfile]:
    """Return a completely independent deep copy of the 15-boy roster."""
    roster_copy: Dict[str, BoyProfile] = {}
    for boy_id, profile in CANONICAL_ROSTER.items():
        roster_copy[boy_id] = BoyProfile(
            id=profile.id,
            name=profile.name,
            age=profile.age,
            nationality=profile.nationality,
            archetype=profile.archetype,
            leadership=profile.leadership,
            seamanship=profile.seamanship,
            carpentry=profile.carpentry,
            hunting=profile.hunting,
            foraging=profile.foraging,
            cooking=profile.cooking,
            morale_influence=profile.morale_influence,
            description=profile.description,
            stats=CharacterStats(),
            current_action="Ready",
            ai_state=AIState.IDLE
        )
    return roster_copy

def get_roster_summary() -> List[dict]:
    """Helper to get a lightweight overview for UI / matchmaking character select."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "archetype": p.archetype,
            "skills": {
                "leadership": p.leadership,
                "seamanship": p.seamanship,
                "carpentry": p.carpentry,
                "hunting": p.hunting,
                "cooking": p.cooking
            },
            "description": p.description
        }
        for p in CANONICAL_ROSTER.values()
    ]

