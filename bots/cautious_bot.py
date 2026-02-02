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
        
        # Adjust strategy based on aggression
        aggression_ratio = raise_count / max(total_actions, 1)
        
        # Existing pot logic
        current_pot = round_state["pot"]["main"]["amount"]
        
        # Enhanced decision: Be more cautious if high aggression, aggressive if many folds
        if aggression_ratio > 0.5:  # High raises, play tight
            action = next(action for action in valid_actions if action["action"] == "fold")
        elif fold_count > total_actions * 0.6:  # Many folds, steal the pot
            action = next(action for action in valid_actions if action["action"] == "raise")
        elif current_pot < 100:
            action = next(action for action in valid_actions if action["action"] == "call")
        else:
            action = next(action for action in valid_actions if action["action"] == "fold")
        
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)


