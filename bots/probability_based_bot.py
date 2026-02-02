import random
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
        
        # Adjust probabilities based on observed actions
        base_fold_prob = 0.2
        base_call_prob = 0.5  # 0.5 - 0.2 = 0.3, then raise 0.3
        base_raise_prob = 0.3
        
        if total_actions > 0:
            fold_ratio = fold_count / total_actions
            raise_ratio = raise_count / total_actions
            
            # If many folds, increase raise probability (steal blinds)
            if fold_ratio > 0.5:
                base_raise_prob += 0.2
                base_call_prob -= 0.1
                base_fold_prob -= 0.1
            # If many raises, increase fold probability (tight play)
            elif raise_ratio > 0.3:
                base_fold_prob += 0.2
                base_call_prob -= 0.1
                base_raise_prob -= 0.1
        
        # Normalize probabilities
        total = base_fold_prob + base_call_prob + base_raise_prob
        fold_prob = base_fold_prob / total
        call_prob = base_call_prob / total
        raise_prob = base_raise_prob / total
        
        rand = random.random()
        if rand < fold_prob:
            action = next(
                action for action in valid_actions if action["action"] == "fold")
        elif rand < fold_prob + call_prob:
            action = next(
                action for action in valid_actions if action["action"] == "call")
        else:
            action = next(
                action for action in valid_actions if action["action"] == "raise")
        
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)

    
