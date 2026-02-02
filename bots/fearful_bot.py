from bots.base import CountingBot

class Bot(CountingBot):
    def __init__(self, bot_name):
        super().__init__(bot_name)
        self.pot_threshold = 2000  # Fold if pot exceeds this amount

    def declare_action(self, valid_actions, hole_card, round_state):
        # Extract action history
        action_histories = round_state.get('action_histories', {})
        current_street = round_state.get('street', 'preflop')
        
        # Calculate total bets in current street
        street_actions = action_histories.get(current_street, [])
        total_bets = sum(action.get('amount', 0) for action in street_actions)
        
        # Get current pot
        current_pot = round_state["pot"]["main"]["amount"]
        
        # Fearful logic: Fold if pot has increased drastically
        if current_pot > self.pot_threshold or total_bets > 1000:  # Drastic increase threshold
            action = next(action for action in valid_actions if action["action"] == "fold")
        else:
            # Otherwise, play cautiously: call if pot is small
            if current_pot < 500:
                action = next(action for action in valid_actions if action["action"] == "call")
            else:
                action = next(action for action in valid_actions if action["action"] == "fold")
        
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)