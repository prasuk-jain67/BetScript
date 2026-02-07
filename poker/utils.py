import sys
import io
from pypokerengine.api.game import setup_config, start_poker
import importlib.util
import re

def load_bot(filepath,bot_name=None):
    try:
        spec = importlib.util.spec_from_file_location("Bot", filepath)
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        if hasattr(bot, 'Bot'):
            return bot.Bot(bot_name=bot_name), True
        else:
            return "The 'Bot' class is not found in the module.", False
    except Exception as e:
        return str(e), False


def parse_poker_output_to_json(content):
    rounds = []
    round_pattern = re.compile(r"Started the round (\d+)")
    street_pattern = re.compile(r'Street "([^"]+)" started\. \(community card = \[(.*?)\]\)')
    action_pattern = re.compile(r'"([^"]+)" declared "([^:]+):(\d+)"')
    winner_pattern = re.compile(r'''"(\[.+?\])" won the round (\d+) \(stack = (\{.*\})\)''')

    current_round = None
    current_street = None

    for line in content.splitlines():
        round_match = round_pattern.search(line)
        if round_match:
            if current_round:
                rounds.append(current_round)
            current_round = {
                "round_number": int(round_match.group(1)),
                "actions": {"preflop": [], "flop": [], "turn": [], "river": []},
                "community_cards": {"preflop":[],"flop": [], "turn": [], "river": []},
                "winner": None,
                "stacks": {}
            }
            current_street = "preflop"
            continue

        if current_round:
            street_match = street_pattern.search(line)
            if street_match:
                street_name = street_match.group(1)
                current_street = street_name
                cards = street_match.group(2).replace("'", "").split(", ") if street_match.group(2) else []
                current_round["community_cards"][street_name] = cards
                if street_name not in current_round["actions"]:
                    current_round["actions"][street_name] = []
                continue

            action_match = action_pattern.search(line)
            if action_match:
                name, action, amount = action_match.groups()

                if not amount.isdigit():
                    return "Invalid amount" , {amount , action , name}
        
                current_round["actions"][current_street].append({"name": name, "action": action, "amount": int(amount)})
                continue

            winner_match = winner_pattern.search(line)

            if winner_match:
                winner_list_str = winner_match.group(1)  # e.g. "['Bot1', 'Bot2']"
                stack_info = eval(winner_match.group(3))
                current_round["stacks"] = stack_info
                
                # Parse winner list
                try:
                    winner_list = eval(winner_list_str)
                    if isinstance(winner_list, list) and len(winner_list) > 0:
                        if len(winner_list) == 1:
                            current_round["winner"] = winner_list[0]
                        else:
                            # Multiple winners (tie) - store as comma-separated string
                            current_round["winner"] = ", ".join(winner_list)
                            current_round["winners_list"] = winner_list  # Also store as list
                except:
                    pass
                continue

    if current_round:
        rounds.append(current_round)

    return {"rounds": rounds} , None


def play_match(bot_paths, bots):

    bot_instances = []
    checks = []
    for bot, path in zip(bots, bot_paths):
        instance, chk = load_bot(path, bot.name)
        bot_instances.append(instance)
        checks.append(chk)

    if not all(checks):
        return bot_instances, None, None

    bot_wins = {bot.name: 0 for bot in bots}
    rounds_data = []
    previous_stack = {bot.name: 10000 for bot in bots}

    config = setup_config(max_round=100000, initial_stack=10000, small_blind_amount=250)
    for bot, instance in zip(bots, bot_instances):
        config.register_player(name=bot.name, algorithm=instance)

    output_file = "poker_output.txt"

    result, success = redirect_stdout_to_file(config, output_file)

    # Read and parse the output file
    replay_data,error= read_output_file_and_parse(output_file)

    if replay_data == "Invalid amount":
        
        return f"Invalid Action({error[0]}) with Amount({error[1]}) check ur code player {str(error[2])}",None
    # Break down the replay data into individual rounds

    for round_num in range(len(replay_data["rounds"])):
        round_data = replay_data["rounds"][round_num] if round_num < len(replay_data["rounds"]) else {}

        if not round_data:
            continue  # Skip if no data for the current round

        # Initialize structures
        actions = {street: {"name": [], "action": [], "amount": []} for street in ['preflop', 'flop', 'turn', 'river']}

        communitycards = {street: [] for street in ['preflop', 'flop', 'turn', 'river']}
        streets = []  # Will store the streets that actually happened

        # Process each street
        for street in ['preflop', 'flop', 'turn', 'river']:
            street_actions = round_data.get("actions", {}).get(street, [])
            if street_actions:  # If actions exist for the street
                streets.append(street)
                actions[street]['name'] = [action['name'] for action in street_actions]
                actions[street]['action'] = [action['action'] for action in street_actions]
                actions[street]['amount'] = [action['amount'] for action in street_actions]

                # Update community cards
            if street != 'preflop':
                communitycards[street] = round_data.get("community_cards", {}).get(street, [])

        # Assemble round data in the desired format

        # Accessing the round result
        winner = round_data.get("winner")
        stacks = round_data.get("stacks", {})

        # Determine active players for the round
        active_players = set()

        # Extract players from actions
        for street, a in replay_data["rounds"][round_num]["actions"].items():
            for action in a:
                active_players.add(action["name"])
        # Extract the round winner (if not already included)
        winner = replay_data["rounds"][round_num]["winner"]
        if winner and winner != "No one":
            # Handle multiple winners (tie scenario)
            if ", " in str(winner):
                for winner_name in winner.split(", "):
                    active_players.add(winner_name.strip())
            else:
                active_players.add(winner)

        hole_cards = []
        for i, bot in enumerate(bots):
            if str(bot.name) in active_players:
                hole_cards.append(bot_instances[i].hole_cards_log[round_num])

        if winner is None or stacks == {}:  # No winner info provided
            rounds_data.append({
                'hole_cards':hole_cards,
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
            for bot in bots:
                if bot.name in active_players:
                    chips_exchanged += abs(stacks_array[bot.name] - previous_stack[bot.name])
            chips_exchanged/=2
            previous_stack = stacks_array

            # if winner in bot_wins:
            #     bot_wins[winner] += 1

            rounds_data.append({
                'hole_cards': hole_cards,
                'street': streets,
                'actions': actions,
                'communitycards': communitycards,
                'chips_exchanged': chips_exchanged,
                'winner': winner,
                'stacks': stacks_array
            })

    # Determine match winner - player with most chips at end
    if previous_stack:
        match_winner = max(previous_stack, key=previous_stack.get, default="No one")
    else:
        match_winner = "No one"

    # Update bot statistics
    # update_bot_stats(
    #     bots, match_winner, 
    #     abs(result["players"][0]["stack"] - result["rule"]["initial_stack"]),
    #     bot_wins, num_rounds
    # )

    return match_winner,rounds_data


def redirect_stdout_to_file(config, output_file):
    with open(output_file, "w") as file:
        original_stdout = sys.stdout
        try:
            sys.stdout = file
            result = start_poker(config, verbose=1)
            return result, True
        except Exception as e:
            sys.stdout = original_stdout
            with open(output_file, "a") as err_file:
                err_file.write(f"\nError: {str(e)}")
            return str(e), False
        finally:
            sys.stdout = original_stdout


def redirect_stdout_to_memory(config):
    buffer = io.StringIO()  # Create an in-memory buffer
    original_stdout = sys.stdout  # Save the original stdout
    try:
        sys.stdout = buffer  # Redirect stdout to the buffer
        result = start_poker(config, verbose=1)  # Run the poker game
        output_content = buffer.getvalue()  # Get the buffer's content as a string
        return result, output_content, True
    except Exception as e:
        return None, str(e), False
    finally:
        sys.stdout = original_stdout  # Restore the original stdout


def read_output_from_memory(output_content):
    return parse_poker_output_to_json(output_content)


def read_output_file_and_parse(input_file):
    with open(input_file, "r") as file:
        content = file.read()
    return parse_poker_output_to_json(content)


# def update_bot_stats(bots, winner_name, chips_exchanged, bot_wins, num_rounds):

#     for bot in bots:
#         bot.total_games += 1  # Increment total games played

#         if bot.name == winner_name:
#             bot.wins += 1
#             bot.chips_won += chips_exchanged  
#         else:
#             bot.chips_won -= chips_exchanged  

#         bot.save()


def play_test_match(bot_paths, bots):

    bot_instances = []
    checks = []
    for bot, path in zip(bots, bot_paths):
        instance, chk = load_bot(path, bot.name)
        bot_instances.append(instance)
        checks.append(chk)

    if not all(checks):
        return bot_instances, None, None

    bot_wins = {bot.name: 0 for bot in bots}
    rounds_data = []
    previous_stack = {bot.name: 10000 for bot in bots}

    config = setup_config(max_round=3, initial_stack=10000, small_blind_amount=250)
    for bot, instance in zip(bots, bot_instances):
        config.register_player(name=bot.name, algorithm=instance)

    output_file = "poker_output.txt"

    result, success = redirect_stdout_to_file(config, output_file)

    # Read and parse the output file
    replay_data,error= read_output_file_and_parse(output_file)

    if replay_data == "Invalid amount":
        
        return f"Invalid Action({error[0]}) with Amount({error[1]}) check ur code player {str(error[2])}",None
    # Break down the replay data into individual rounds

    for round_num in range(len(replay_data["rounds"])):
        round_data = replay_data["rounds"][round_num] if round_num < len(replay_data["rounds"]) else {}

        if not round_data:
            continue  # Skip if no data for the current round

        # Initialize structures
        actions = {street: {"name": [], "action": [], "amount": []} for street in ['preflop', 'flop', 'turn', 'river']}

        communitycards = {street: [] for street in ['preflop', 'flop', 'turn', 'river']}
        streets = []  # Will store the streets that actually happened

        # Process each street
        for street in ['preflop', 'flop', 'turn', 'river']:
            street_actions = round_data.get("actions", {}).get(street, [])
            if street_actions:  # If actions exist for the street
                streets.append(street)
                actions[street]['name'] = [action['name'] for action in street_actions]
                actions[street]['action'] = [action['action'] for action in street_actions]
                actions[street]['amount'] = [action['amount'] for action in street_actions]

                # Update community cards
            if street != 'preflop':
                communitycards[street] = round_data.get("community_cards", {}).get(street, [])

        # Assemble round data in the desired format

        # Accessing the round result
        winner = round_data.get("winner")
        stacks = round_data.get("stacks", {})

        # Determine active players for the round
        active_players = set()

        # Extract players from actions
        for street, a in replay_data["rounds"][round_num]["actions"].items():
            for action in a:
                active_players.add(action["name"])
        # Extract the round winner (if not already included)
        winner = replay_data["rounds"][round_num]["winner"]
        if winner and winner != "No one":
            # Handle multiple winners (tie scenario)
            if ", " in str(winner):
                for winner_name in winner.split(", "):
                    active_players.add(winner_name.strip())
            else:
                active_players.add(winner)

        hole_cards = []
        for i, bot in enumerate(bots):
            if str(bot.name) in active_players:
                hole_cards.append(bot_instances[i].hole_cards_log[round_num])

        if winner is None or stacks == {}:  # No winner info provided
            rounds_data.append({
                'hole_cards':hole_cards,
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
            for bot in bots:
                if bot.name in active_players:
                    chips_exchanged += abs(stacks_array[bot.name] - previous_stack[bot.name])
            chips_exchanged/=2
            previous_stack = stacks_array

            # if winner in bot_wins:
            #     bot_wins[winner] += 1

            rounds_data.append({
                'hole_cards': hole_cards,
                'street': streets,
                'actions': actions,
                'communitycards': communitycards,
                'chips_exchanged': chips_exchanged,
                'winner': winner,
                'stacks': stacks_array
            })

    # Determine match winner - player with most chips at end
    if previous_stack:
        match_winner = max(previous_stack, key=previous_stack.get, default="No one")
    else:
        match_winner = "No one"

    # Update bot statistics
    # update_bot_stats(
    #     bots, match_winner, 
    #     abs(result["players"][0]["stack"] - result["rule"]["initial_stack"]),
    #     bot_wins, num_rounds
    # )

    return match_winner,rounds_data