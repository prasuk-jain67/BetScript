from pypokerengine.players import BasePokerPlayer
from typing import final
import pandas as pd


class CountingBot(BasePokerPlayer):

    def __init__(self, bot_name):
        self.bot_name = bot_name
        self.wins = 0
        self.stack = 0
        self.in_game = True
        self.game_history = []
        self.game_history_df = pd.DataFrame(columns=[
            "bot_name", "round_state",
            "valid_actions", "action_taken"
        ])  # Initialize DataFrame
        self.hole_cards_log = []

    def declare_action(self, valid_actions, hole_card, round_state):
        # Implement your bot's logic here
        pass


    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        # Hole cards are recorded for replay/analysis; avoid printing to stdout
        for player in seats:
            if player['uuid'] == self.uuid:
                self.hole_cards_log.append(hole_card)

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, new_action, round_state):
        # Log the action for analysis
        self.game_history.append({
            'street': round_state.get('street'),
            'player_uuid': new_action.get('player_uuid'),
            'action': new_action.get('action'),
            'amount': new_action.get('amount'),
            'round_state': round_state  # Full state for deeper analysis
        })
        # Avoid printing action observations to stdout to prevent duplicate output

    def receive_round_result_message(self, winners, hand_info, round_state):
        for winner in winners:
            if winner["uuid"] == self.uuid:
                self.wins += 1
        for player in round_state["seats"]:
            if player["uuid"] == self.uuid:
                self.stack = player["stack"]

        # Append game history to the DataFrame
        for entry in self.game_history:
            entry["bot_name"] = self.bot_name
            # Add summary of actions observed
            action_histories = entry.get('round_state', {}).get('action_histories', {})
            entry['total_raises'] = sum(len(actions) for actions in action_histories.values() if isinstance(actions, list) for action in actions if action.get('action') == 'raise')
            entry['total_folds'] = sum(len(actions) for actions in action_histories.values() if isinstance(actions, list) for action in actions if action.get('action') == 'fold')
            entry['total_calls'] = sum(len(actions) for actions in action_histories.values() if isinstance(actions, list) for action in actions if action.get('action') == 'call')
            self.game_history_df = pd.concat([self.game_history_df, pd.DataFrame([entry])], ignore_index=True)
        self.game_history = []  # Reset the game history for the next round