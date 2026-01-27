import random
from bots.base import CountingBot

class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        rand = random.random()
        if rand < 0.5:
            action = next(
                action for action in valid_actions if action["action"] == "call")
        elif rand < 0.8:
            action = next(
                action for action in valid_actions if action["action"] == "raise")
        else:
            action = next(
                action for action in valid_actions if action["action"] == "fold")
        amount = action.get("amount")
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)

    
