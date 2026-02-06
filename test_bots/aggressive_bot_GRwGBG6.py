from bots.base import CountingBot

class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        action_histories = round_state.get('action_histories', {})
        current_street = round_state.get('street', 'preflop')
        
        street_actions = action_histories.get(current_street, [])
        raise_count = sum(1 for action in street_actions if action['action'] == 'raise')
        fold_count = sum(1 for action in street_actions if action['action'] == 'fold')
        total_actions = len(street_actions)
        
        # Aggressive strategy
        if total_actions > 0:
            fold_ratio = fold_count / total_actions
            if fold_ratio > 0.4:
                action = next(action for action in valid_actions if action["action"] == "raise")
            else:
                action = next(action for action in valid_actions if action["action"] == "raise")
        else:
            action = next(action for action in valid_actions if action["action"] == "raise")
        
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)