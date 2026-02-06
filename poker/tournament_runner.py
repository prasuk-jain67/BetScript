import sys
import random
import glob
import os
from .utils import load_bot, redirect_stdout_to_file, read_output_file_and_parse
from pypokerengine.api.game import setup_config

def run_tournament(user_bot, all_possible_opponents, iterations=100):
    """
    user_bot: The TestBot object for the user's uploaded bot.
    all_possible_opponents: List of dicts {'name': str, 'path': str} for potential opponents.
    """
    best_match = None
    worst_match = None
    all_matches_metadata = []
    
    # Track best/worst results (initial stack 10000)
    best_stack = -1
    worst_stack = float('inf')

    for i in range(iterations):
        # Select up to 5 random opponents
        num_opponents = min(5, len(all_possible_opponents))
        selected_opponents = random.sample(all_possible_opponents, num_opponents)
        
        # Prepare bots list (User Bot + Opponents)
        current_match_bots = []
        
        current_match_bots.append({'name': user_bot.name, 'path': user_bot.file.path})
        current_match_bots.extend(selected_opponents)

        bot_instances = []
        checks = []
        
        for bot_info in current_match_bots:
            instance, chk = load_bot(bot_info['path'], bot_info['name'])
            bot_instances.append(instance)
            checks.append(chk)

        if not all(checks):
             continue

        config = setup_config(max_round=5, initial_stack=10000, small_blind_amount=250)
        for bot_info, instance in zip(current_match_bots, bot_instances):
            config.register_player(name=bot_info['name'], algorithm=instance)

        output_file = "poker_output.txt"

        result, success = redirect_stdout_to_file(config, output_file)
        replay_data, error = read_output_file_and_parse(output_file)
        
        if replay_data == "Invalid amount":
             continue

        rounds_data = []
        previous_stack = {b['name']: 10000 for b in current_match_bots}
        
        current_match_winner = None
        final_stacks = {}
        if isinstance(result, dict) and "players" in result:
             for player in result["players"]:
                 final_stacks[player["name"]] = player["stack"]
        
        current_match_winner = max(final_stacks, key=final_stacks.get) if final_stacks else "No one"
        
        bot_wins = {b['name']: 0 for b in current_match_bots} 

        for round_num in range(len(replay_data["rounds"])):
            round_data = replay_data["rounds"][round_num] if round_num < len(replay_data["rounds"]) else {}

            if not round_data:
                continue

            actions = {street: {"name": [], "action": [], "amount": []} for street in ['preflop', 'flop', 'turn', 'river']}
            communitycards = {street: [] for street in ['preflop', 'flop', 'turn', 'river']}
            streets = []

            for street in ['preflop', 'flop', 'turn', 'river']:
                street_actions = round_data.get("actions", {}).get(street, [])
                if street_actions:
                    streets.append(street)
                    actions[street]['name'] = [action['name'] for action in street_actions]
                    actions[street]['action'] = [action['action'] for action in street_actions]
                    actions[street]['amount'] = [action['amount'] for action in street_actions]

                if street != 'preflop':
                    communitycards[street] = round_data.get("community_cards", {}).get(street, [])

            winner = round_data.get("winner")
            stacks = round_data.get("stacks", {})
            active_players = set()
            for street, a in replay_data["rounds"][round_num]["actions"].items():
                for action in a:
                    active_players.add(action["name"])
            if winner and winner != "No one":
                active_players.add(winner)

            hole_cards = []
            for k, bot_info in enumerate(current_match_bots):
                if str(bot_info['name']) in active_players:
                    if round_num < len(bot_instances[k].hole_cards_log):
                         hole_cards.append(bot_instances[k].hole_cards_log[round_num])
                    else:
                         hole_cards.append([])

            if winner is None or stacks == {}:
                rounds_data.append({
                    'hole_cards': hole_cards,
                    'street': streets,
                    'actions': actions,
                    'communitycards': communitycards,
                    'chips_exchanged': 0,
                    'total_chips_exchanged': 0,
                    'winner': "No one"
                })
            else:
                stacks_array = {name: value for name, value in stacks.items()}
                chips_exchanged = 0
                for bot_info in current_match_bots:
                    if bot_info['name'] in active_players:
                        chips_exchanged += abs(stacks_array[bot_info['name']] - previous_stack.get(bot_info['name'], 10000))
                chips_exchanged /= 2
                previous_stack = stacks_array

                rounds_data.append({
                    'hole_cards': hole_cards,
                    'street': streets,
                    'actions': actions,
                    'communitycards': communitycards,
                    'chips_exchanged': chips_exchanged,
                    'winner': winner
                })
        
        user_stack = final_stacks.get(user_bot.name, 0)
        
        match_info = {
            'winner': current_match_winner,
            'rounds_data': rounds_data,
            'stack': user_stack,
            'players': final_stacks,
            'opponent_names': [opp['name'] for opp in selected_opponents]
        }
        
        if user_stack > best_stack:
            best_stack = user_stack
            best_match = match_info
        
        if user_stack < worst_stack:
            worst_stack = user_stack
            worst_match = match_info

        all_matches_metadata.append({
            'iteration': i + 1,
            'winner': current_match_winner,
            'user_stack': user_stack,
            'opponents': [opp['name'] for opp in selected_opponents],
            'rounds_data': rounds_data
        })

    return best_match, worst_match, all_matches_metadata
