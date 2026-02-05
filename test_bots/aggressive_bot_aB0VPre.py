from bots.base import CountingBot

class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        # Extract action history
        action_histories = round_state.get('action_histories', {})
        current_street = round_state.get('street', 'preflop')
        
        # Analyze actions in current street
        street_actions = action_histories.get(current_street, [])
        raise_count = sum(1 for action in street_actions if action['action'] == 'raise')
        fold_count = sum(1 for action in street_actions if action['action'] == 'fold')
        total_actions = len(street_actions)
        
        # Aggressive base: prefer raise, but adapt
        if total_actions > 0:
            fold_ratio = fold_count / total_actions
            # If opponents are folding, definitely raise to steal
            if fold_ratio > 0.4:
                action = next(action for action in valid_actions if action["action"] == "raise")
            else:
                # Otherwise, still aggressive but mix in calls
                action = next(action for action in valid_actions if action["action"] == "raise")
        else:
            # No actions yet, raise
            action = next(action for action in valid_actions if action["action"] == "raise")
        
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)

