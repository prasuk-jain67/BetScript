import sys
import random
import glob
import os
from multiprocessing import Pool, cpu_count
from .utils import load_bot, redirect_stdout_to_memory, read_output_from_memory
from pypokerengine.api.game import setup_config

def run_single_match(args):
    """
    Function to run a single match iteration in a separate process.
    args: tuple (iteration_index, user_bot_info, selected_opponents_info)
    """
    iteration_index, user_bot_info, selected_opponents_info = args
    
    current_match_bots = [user_bot_info] + selected_opponents_info
    bot_instances = []
    
    # Load bots in the child process
    for bot_info in current_match_bots:
        instance, chk = load_bot(bot_info['path'], bot_info['name'])
        if not chk:
            return None # Skip if bot fails to load
        bot_instances.append(instance)

    config = setup_config(max_round=75, initial_stack=10000, small_blind_amount=250)
    for bot_info, instance in zip(current_match_bots, bot_instances):
        config.register_player(name=bot_info['name'], algorithm=instance)

    # Use in-memory redirection to avoid file I/O and process conflicts
    result, output_content, success = redirect_stdout_to_memory(config)
    if not success:
        return None

    replay_data, error = read_output_from_memory(output_content)
    if replay_data == "Invalid amount":
        return None

    rounds_data = []
    previous_stack = {b['name']: 10000 for b in current_match_bots}
    final_stacks = {}
    
    if isinstance(result, dict) and "players" in result:
        for player in result["players"]:
            final_stacks[player["name"]] = player["stack"]
    
    current_match_winner = max(final_stacks, key=final_stacks.get) if final_stacks else "No one"
    
    # Process rounds for replay and stats
    for round_num in range(len(replay_data["rounds"])):
        round_data = replay_data["rounds"][round_num]
        if not round_data: continue

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

        stacks_array = {name: value for name, value in stacks.items()}
        chips_exchanged = 0
        if stacks_array:
            for bot_info in current_match_bots:
                if bot_info['name'] in active_players:
                    chips_exchanged += abs(stacks_array.get(bot_info['name'], 10000) - previous_stack.get(bot_info['name'], 10000))
            chips_exchanged /= 2
            previous_stack = stacks_array

        rounds_data.append({
            'hole_cards': hole_cards,
            'street': streets,
            'actions': actions,
            'communitycards': communitycards,
            'chips_exchanged': chips_exchanged,
            'winner': winner or "No one",
            'stacks': stacks_array
        })

    user_stack = final_stacks.get(user_bot_info['name'], 0)
    
    return {
        'iteration': iteration_index + 1,
        'winner': current_match_winner,
        'user_stack': user_stack,
        'opponents': [opp['name'] for opp in selected_opponents_info],
        'rounds_data': rounds_data,
        'stack': user_stack
    }

def run_tournament(user_bot, builtin_opponents, permanent_opponents, iterations=100):
    user_bot_info = {'name': user_bot.name, 'path': user_bot.file.path}
    
    match_args = []
    for i in range(iterations):
        # PRIORITY SELECTION: 
        # Always try to pick at least 3 permanent bots if they exist
        num_perm_to_pick = min(3, len(permanent_opponents))
        selected_perm = random.sample(permanent_opponents, num_perm_to_pick)
        
        # Fill the remaining 5 slots with builtin bots
        num_builtin_needed = 5 - num_perm_to_pick
        num_builtin_to_pick = min(num_builtin_needed, len(builtin_opponents))
        selected_builtin = random.sample(builtin_opponents, num_builtin_to_pick)
        
        # If we still have slots (e.g. not enough builtins), pick more from permanent if possible
        if len(selected_perm) + len(selected_builtin) < 5:
            remaining_perm = [p for p in permanent_opponents if p not in selected_perm]
            extra_perm_needed = 5 - (len(selected_perm) + len(selected_builtin))
            extra_perm = random.sample(remaining_perm, min(extra_perm_needed, len(remaining_perm)))
            selected_perm.extend(extra_perm)

        selected_opponents = selected_perm + selected_builtin
        match_args.append((i, user_bot_info, selected_opponents))

    num_processes = max(1, cpu_count() - 1)
    
    with Pool(processes=num_processes) as pool:
        results = pool.map(run_single_match, match_args)

    all_matches_metadata = [r for r in results if r is not None]
    
    if not all_matches_metadata:
        return None, None, []

    best_match = max(all_matches_metadata, key=lambda x: x['user_stack'])
    worst_match = min(all_matches_metadata, key=lambda x: x['user_stack'])

    return best_match, worst_match, all_matches_metadata
