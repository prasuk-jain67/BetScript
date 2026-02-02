import random
from bots.base import CountingBot

class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        # Extract action history for adaptive randomness
        action_histories = round_state.get('action_histories', {})
        current_street = round_state.get('street', 'preflop')
        
        # Analyze actions in current street
        street_actions = action_histories.get(current_street, [])
        raise_count = sum(1 for action in street_actions if action['action'] == 'raise')
        fold_count = sum(1 for action in street_actions if action['action'] == 'fold')
        call_count = sum(1 for action in street_actions if action['action'] == 'call')
        total_actions = len(street_actions)
        
        # Adaptive weights: favor actions that are less common to balance
        weights = []
        for action in valid_actions:
            if action['action'] == 'raise':
                weight = 1 + (call_count - raise_count)  # Favor raise if fewer raises
            elif action['action'] == 'call':
                weight = 1 + (fold_count - call_count)  # Favor call if fewer calls
            elif action['action'] == 'fold':
                weight = 1 + (raise_count - fold_count)  # Favor fold if fewer folds
            else:
                weight = 1
            weights.append(max(weight, 0.1))  # Minimum weight
        
        # Choose action based on weights
        action = random.choices(valid_actions, weights=weights, k=1)[0]

        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)

