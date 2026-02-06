from bots.base import CountingBot

class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        return "fold", 0
