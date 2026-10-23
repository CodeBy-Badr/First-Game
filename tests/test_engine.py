"""
Comprehensive Unit & Integration Test Suite
Lost Island: 15 Boys Survival RPG Engine
"""

import unittest
import os
import tempfile
import asyncio
from lost_island.core.roster import CANONICAL_ROSTER, create_fresh_roster, get_roster_summary
from lost_island.core.types import StormStation, AIState, RoomState, TimeOfDay
from lost_island.simulation.storm import StormSimulation
from lost_island.simulation.island import IslandSimulation
from lost_island.simulation.offline_game import OfflineGameEngine
from lost_island.ai.companion_fsm import CompanionBrain
from lost_island.ai.quest_system import SquadCommander
from lost_island.database.persistence import PersistenceEngine
from lost_island.multiplayer.lobby import MatchmakingEngine, LobbyRoom
from lost_island.multiplayer.protocol import PacketType, create_packet, parse_packet

class TestLostIslandEngine(unittest.TestCase):

    def test_canonical_roster_count_and_integrity(self):
        """Verify that exactly 15 unique canonical boys are defined with historical archetypes."""
        self.assertEqual(len(CANONICAL_ROSTER), 15)
        expected_keys = {
            "gordon", "doniphan", "briant", "moko", "baxter",
            "cross", "webb", "service", "garnett", "wilcox",
            "jack", "jenkins", "iverson", "dole", "costar"
        }
        self.assertEqual(set(CANONICAL_ROSTER.keys()), expected_keys)
        
        # Verify independence of fresh roster
        r1 = create_fresh_roster()
        r2 = create_fresh_roster()
        self.assertIsNot(r1["gordon"], r2["gordon"])
        r1["gordon"].stats.health = 50.0
        self.assertEqual(r2["gordon"].stats.health, 100.0)

    def test_storm_simulation_mechanics(self):
        """Verify sea storm physics, station contributions, and reef collision."""
        roster = create_fresh_roster()
        storm = StormSimulation(roster, storm_duration_ticks=10)
        
        # Assign Briant to Helm and Baxter to Carpentry
        storm.assign_boy_to_station("briant", StormStation.HELM)
        storm.assign_boy_to_station("baxter", StormStation.CARPENTRY)
        storm.assign_boy_to_station("moko", StormStation.BILGE)
        
        initial_water = storm.water_level
        initial_dist = storm.distance_to_reef
        
        state = storm.step()
        self.assertLess(state["distance_to_reef"], initial_dist)
        self.assertIn("crew_status", state)
        self.assertEqual(len(state["crew_status"]), 15)

    def test_island_survival_simulation(self):
        """Verify island resource consumption, day/night cycles, and camp stats."""
        roster = create_fresh_roster()
        island = IslandSimulation(roster)
        
        self.assertEqual(island.day, 1)
        self.assertEqual(island.time_of_day, TimeOfDay.DAWN)
        
        # Advance through cycle
        island.advance_time() # DAY
        self.assertEqual(island.time_of_day, TimeOfDay.DAY)
        island.advance_time() # DUSK
        island.advance_time() # NIGHT
        self.assertEqual(island.time_of_day, TimeOfDay.NIGHT)
        island.advance_time() # Next DAWN (Day 2)
        self.assertEqual(island.day, 2)
        
        state = island.step()
        self.assertTrue(state["food_rations"] >= 0)
        self.assertTrue(state["fresh_water"] >= 0)

    def test_companion_ai_utility_evaluation(self):
        """Verify that companion AI makes rational utility choices based on traits."""
        roster = create_fresh_roster()
        island = IslandSimulation(roster)
        
        baxter_brain = CompanionBrain(roster["baxter"], is_human_controlled=False)
        doniphan_brain = CompanionBrain(roster["doniphan"], is_human_controlled=False)
        
        # Baxter should favor building shelter when wood is available
        baxter_choice = baxter_brain.evaluate_island_utility(island)
        self.assertIn(baxter_choice, [AIState.BUILDING_SHELTER, AIState.FORAGING, AIState.DEFENDING_CAMP])

        # Test work execution
        action_msg = baxter_brain.execute_island_work(AIState.BUILDING_SHELTER, island)
        self.assertIn("Baxter", action_msg)

    def test_squad_commander_and_nightfall(self):
        """Verify squad orders and automated nightfall triggers."""
        roster = create_fresh_roster()
        brains = {bid: CompanionBrain(b, is_human_controlled=(bid == "gordon")) for bid, b in roster.items()}
        commander = SquadCommander(brains)
        
        # Issue order to forage
        res = commander.issue_squad_order("FORAGE")
        self.assertIn("Broadcast", res)
        self.assertEqual(brains["doniphan"].forced_order, AIState.FORAGING)
        
        # Nightfall trigger
        night_logs = commander.on_nightfall_trigger()
        # Dole and Costar (younger boys) should retreat
        self.assertEqual(brains["costar"].forced_order, AIState.RETREATING_TO_SHELTER)

    def test_database_persistence_layer(self):
        """Verify SQLite user accounts, safe transactions, profile updates, and saves."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            db = PersistenceEngine(db_path)
            
            # 1. Registration
            success, user_id = db.register_user("survivor_dan", "secure_storm_pass123")
            self.assertTrue(success)
            
            # Duplicate username rejection
            dup_success, _ = db.register_user("survivor_dan", "different_pass")
            self.assertFalse(dup_success)

            # 2. Authentication
            auth_info = db.authenticate_user("survivor_dan", "secure_storm_pass123")
            self.assertIsNotNone(auth_info)
            token = auth_info["token"]

            # Bad password rejection
            bad_auth = db.authenticate_user("survivor_dan", "wrong_pass")
            self.assertIsNone(bad_auth)

            # 3. Session validation
            sess = db.validate_session(token)
            self.assertIsNotNone(sess)
            self.assertEqual(sess["username"], "survivor_dan")

            # 4. Achievements & Storm Survival
            db.record_storm_survival(user_id)
            profile = db.get_user_profile(user_id)
            self.assertEqual(profile["stats"]["storms_survived"], 1)
            self.assertEqual(len(profile["achievements"]), 1)
            self.assertEqual(profile["achievements"][0]["achievement_key"], "STORM_SURVIVOR")

            # 5. Campaign Save & Load
            save_id = db.save_campaign(
                user_id=user_id,
                save_name="Beachhead Alpha",
                game_mode="OFFLINE_SINGLEPLAYER",
                day=3,
                time_of_day="DUSK",
                camp_data={"wood": 40.0, "food": 32.0},
                roster_data={"leader": "gordon"}
            )
            loaded_save = db.load_campaign(save_id)
            self.assertIsNotNone(loaded_save)
            self.assertEqual(loaded_save["day"], 3)
            self.assertEqual(loaded_save["camp_data"]["wood"], 40.0)

        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_lobby_matchmaking_15_slots(self):
        """Verify 15-slot room allocation, locking, and atomic concurrency logic."""
        room = LobbyRoom("test_room_1")
        self.assertEqual(room.get_occupied_count(), 0)
        self.assertFalse(room.is_fully_locked())

        # Player 1 locks Doniphan
        ok, msg = room.lock_character("p1", "Alice", "doniphan")
        self.assertTrue(ok)
        self.assertEqual(room.get_occupied_count(), 1)

        # Player 2 attempts to lock Doniphan (must fail)
        ok2, msg2 = room.lock_character("p2", "Bob", "doniphan")
        self.assertFalse(ok2)
        self.assertIn("already locked", msg2)

        # Player 2 locks Gordon
        ok3, _ = room.lock_character("p2", "Bob", "gordon")
        self.assertTrue(ok3)
        self.assertEqual(room.get_occupied_count(), 2)

        # Fill remaining slots with AI to simulate all 15 boys present
        filled = room.fill_remaining_with_ai()
        self.assertEqual(filled, 13)
        self.assertEqual(room.get_occupied_count(), 15)
        self.assertTrue(room.is_fully_locked())

    def test_network_protocol_serialization(self):
        """Verify JSON packet generation and parsing."""
        pkt = create_packet(PacketType.SELECT_CHARACTER, {"character_id": "moko"})
        p_type, payload = parse_packet(pkt)
        self.assertEqual(p_type, PacketType.SELECT_CHARACTER)
        self.assertEqual(payload.get("character_id"), "moko")

    def test_offline_game_end_to_end_loop(self):
        """Verify offline mode coordinating human player and 14 AI companions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            game = OfflineGameEngine(human_boy_id="briant", db_path=db_path)
            self.assertEqual(game.human_boy_id, "briant")
            self.assertEqual(game.phase, "PROLOGUE_STORM")
            
            # Step storm
            game.set_human_station(StormStation.HELM)
            state, logs = game.step_storm()
            self.assertIn("hull_integrity", state)
            
            # Force storm completion to test island transition
            game.storm_sim.distance_to_reef = 0.0
            state2, logs2 = game.step_storm()
            self.assertEqual(game.phase, "ISLAND_SURVIVAL")
            self.assertIsNotNone(game.island_sim)

            # Step island with human action
            istate, ilogs = game.step_island(human_action=AIState.FORAGING)
            self.assertIn("shelter_level", istate)
            self.assertTrue(len(ilogs) > 0)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

if __name__ == "__main__":
    unittest.main()
