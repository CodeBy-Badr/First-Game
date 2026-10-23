"""
Lost Island: 15 Boys Survival RPG
Offline Single-Player Mode Runner with Interactive Console TUI.
"""

import sys
import time
from lost_island.core.roster import CANONICAL_ROSTER
from lost_island.core.types import StormStation, AIState, TimeOfDay
from lost_island.simulation.offline_game import OfflineGameEngine

def display_roster_selection():
    print("=" * 70)
    print("      LOST ISLAND: 15 BOYS SURVIVAL - CHARACTER SELECTION")
    print("=" * 70)
    print("Select which boy you want to command in Offline Single-Player mode:")
    print("The remaining 14 characters will be dynamically steered by Companion AI.\n")
    
    boy_list = list(CANONICAL_ROSTER.values())
    for idx, boy in enumerate(boy_list, 1):
        print(f"[{idx:2d}] {boy.name.upper():<16} (Age {boy.age:2d}) - {boy.archetype}")
        print(f"     Skills: Lead:{boy.leadership} Seamanship:{boy.seamanship} Carp:{boy.carpentry} Hunt:{boy.hunting} Cook:{boy.cooking}")
        print(f"     Note: {boy.description}\n")
    return boy_list

def play_prologue_storm(game: OfflineGameEngine):
    print("\n" + "#" * 70)
    print("            ACT 0: PROLOGUE - THE STORM OF THE SLOUGHI")
    print("#" * 70)
    print("A catastrophic gale strikes the Pacific! The 15 boys must stay afloat.\n")

    step = 0
    while game.phase == "PROLOGUE_STORM":
        step += 1
        storm = game.storm_sim
        print(f"\n--- [STORM TICK #{step}] Distance to Reef: {storm.distance_to_reef:.0f}m ---")
        print(f"Hull Integrity:    [{'#' * int(storm.hull_integrity // 5):<20}] {storm.hull_integrity:.1f}%")
        print(f"Water Flooding:    [{'~' * int(storm.water_level // 5):<20}] {storm.water_level:.1f}%")
        print(f"Rudder Stability:  [{'=' * int(storm.rudder_stability // 5):<20}] {storm.rudder_stability:.1f}%")
        print(f"Hull Breaches:     {storm.hull_breaches} | Wind: {storm.wind_speed_knots} knots")

        if storm.rogue_wave_incoming:
            print(">>> [DANGER] MONSTROUS ROGUE WAVE INCOMING! CHOOSE 'BRACE' IMMEDIATELY! <<<")

        print("\nChoose Station for your character:")
        print("[1] HELM (Steering)   [2] BILGE (Bailing)   [3] CARPENTRY (Fix Hull)")
        print("[4] RIGGING (Sails)   [5] BRACE (Hold on)   [Enter to keep current]")

        choice = input("Your Station Action (1-5, or press Enter): ").strip()
        station_map = {
            "1": StormStation.HELM,
            "2": StormStation.BILGE,
            "3": StormStation.CARPENTRY,
            "4": StormStation.RIGGING,
            "5": StormStation.BRACE
        }
        if choice in station_map:
            game.set_human_station(station_map[choice])

        # Step storm simulation (companions act autonomously)
        state, logs = game.step_storm()

        print("\nRecent Ship Activity & Companion Decisions:")
        for log in logs:
            print(f"  * {log}")

        time.sleep(0.4)

    if game.phase == "GAME_OVER":
        print("\n[GAME OVER] The schooner has sunk. The expedition was lost at sea.")
        sys.exit(0)

def play_island_survival(game: OfflineGameEngine):
    print("\n" + "=" * 70)
    print("           ACT I: HAVEN ON CHAIRMAN ISLAND")
    print("=" * 70)
    print("The Sloughi has wrecked on the sands. All 15 boys have survived!")
    print("You now lead the colony. 14 companions follow utility logic & squad orders.\n")

    while game.phase == "ISLAND_SURVIVAL":
        island = game.island_sim
        print(f"\n--- DAY {island.day} | TIME: {island.time_of_day.value} | WEATHER: {island.weather.value} ---")
        print(f"Camp Stockpiles:  Wood: {island.wood:.1f} | Food: {island.food_rations:.1f} | Water: {island.fresh_water:.1f}")
        print(f"Infrastructure:   Shelter: {island.shelter_level:.1f}% | Defense: {island.defense_level:.1f}% | Fire: {island.fire_intensity:.1f}%")

        human = game.get_human_profile()
        print(f"\nLeader {human.name} Status: HP: {human.stats.health:.0f} | Stamina: {human.stats.stamina:.0f} | Warmth: {human.stats.warmth:.0f}")

        print("\nAction Menu:")
        print("[1] Forage for food & driftwood       [2] Build shelter frame")
        print("[3] Fortify perimeter defense          [4] Tend hearth fire")
        print("[5] Issue Squad Command to all AI     [6] Advance to next cycle")
        print("[Q] Save & Quit")

        choice = input("Select Action (1-6, Q): ").strip().upper()
        if choice == "Q":
            save_id = game.db.save_campaign(
                user_id="offline_user",
                save_name="Island Campaign Save",
                game_mode="OFFLINE_SINGLEPLAYER",
                day=island.day,
                time_of_day=island.time_of_day.value,
                camp_data=island.get_state(),
                roster_data={"leader": game.human_boy_id}
            )
            print(f"Campaign saved successfully! Save ID: {save_id}")
            break

        human_action = None
        if choice == "1":
            human_action = AIState.FORAGING
        elif choice == "2":
            human_action = AIState.BUILDING_SHELTER
        elif choice == "3":
            human_action = AIState.DEFENDING_CAMP
        elif choice == "4":
            human_action = AIState.TENDING_FIRE
        elif choice == "5":
            print("\nSquad Command Directives:")
            print("  - FORAGE : All companions gather resources")
            print("  - BUILD  : All companions fortify shelter")
            print("  - DEFEND : All companions guard perimeter")
            print("  - RETREAT: All companions seek safety")
            print("  - FREE   : Restore companion autonomous free will")
            cmd = input("Enter command: ").strip()
            res = game.issue_command(cmd)
            print(f"\n>>> {res}")
            continue
        elif choice == "6":
            island.advance_time()
            if island.time_of_day == TimeOfDay.NIGHT:
                night_logs = game.commander.on_nightfall_trigger()
                for nl in night_logs:
                    print(f"  * {nl}")

        # Step island simulation
        state, events = game.step_island(human_action=human_action)
        print("\nCompanion Actions & Camp Events:")
        for ev in events:
            print(f"  * {ev}")

def main():
    boy_list = display_roster_selection()
    selected_idx = None
    while selected_idx is None:
        raw = input("Enter character number (1-15, default is 1 for Gordon): ").strip()
        if not raw:
            selected_idx = 0
            break
        try:
            val = int(raw) - 1
            if 0 <= val < len(boy_list):
                selected_idx = val
            else:
                print("Invalid number. Pick 1 to 15.")
        except ValueError:
            print("Please enter a valid integer.")

    chosen_boy = boy_list[selected_idx]
    print(f"\nYou have chosen to survive as: {chosen_boy.name} ({chosen_boy.archetype})!")
    print("Initializing offline engine with 14 companion AI agents...\n")
    time.sleep(1.0)

    game = OfflineGameEngine(human_boy_id=chosen_boy.id)
    play_prologue_storm(game)
    play_island_survival(game)

if __name__ == "__main__":
    main()

