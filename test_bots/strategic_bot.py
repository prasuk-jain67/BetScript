"""
Strategic bot using hand strength evaluation.
Formerly `basic_strategy_bot.py` — renamed to a clearer name.
"""
from bots.base import CountingBot
from bots.utils.hand_evaluator import HandEvaluator


class Bot(CountingBot):
    """Bot that makes decisions based on hand strength evaluation."""
    
    # Street-specific aggression multipliers
    AGGRESSION_BY_STREET = {
        'preflop': 0.6,
        'flop': 0.7,
        'turn': 0.8,
        'river': 0.9
    }
    
    def declare_action(self, valid_actions, hole_card, round_state):
        """
        Decide action based on hand strength.
        Returns tuple (action_type, amount)
        """
        try:
            street = round_state.get('street', 'preflop')
            community_cards = round_state.get('community_card', [])
            
            hand_strength = HandEvaluator.evaluate_hole_cards(hole_card, community_cards)
            current_call_amount = self._get_call_amount(valid_actions)
            my_stack = self._get_my_stack(round_state)
            
            aggression = self.AGGRESSION_BY_STREET.get(street, 0.7)
            max_call_ratio = hand_strength * aggression
            max_call_amount = my_stack * max_call_ratio
            
            if current_call_amount <= max_call_amount:
                if hand_strength > 0.65 and self._can_raise(valid_actions):
                    raise_amount = self._calculate_raise_amount(
                        hand_strength, current_call_amount, my_stack
                    )
                    action_type, amount = self._get_raise_action(valid_actions, raise_amount)
                    return action_type, amount
                else:
                    return self._execute_call(valid_actions)
            else:
                fold_action = next(
                    (a for a in valid_actions if a['action'] == 'fold'),
                    None
                )
                if fold_action:
                    return 'fold', 0
                return self._execute_call(valid_actions)
        except Exception:
            return self._execute_call(valid_actions)
    
    def _get_call_amount(self, valid_actions):
        call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
        return call_action['amount'] if call_action else 0
    
    def _get_my_stack(self, round_state):
        seats = round_state.get('seats', [])
        for seat in seats:
            if seat.get('uuid') == self.uuid:
                return seat.get('stack', 0)
        return 0
    
    def _can_raise(self, valid_actions):
        return any(a['action'] == 'raise' for a in valid_actions)
    
    def _calculate_raise_amount(self, hand_strength, current_bet, stack):
        if hand_strength < 0.7:
            return current_bet * 2
        elif hand_strength < 0.85:
            return current_bet * 3
        else:
            return int(stack * 0.3)
    
    def _get_raise_action(self, valid_actions, amount):
        raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
        if raise_action:
            min_amount = raise_action['amount']['min']
            max_amount = raise_action['amount']['max']
            amount = max(min_amount, min(max_amount, int(amount)))
            return ('raise', amount)
        return self._execute_call(valid_actions)
    
    def _execute_call(self, valid_actions):
        call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
        if call_action:
            amount = call_action.get('amount', 0)
            if isinstance(amount, dict):
                amount = amount.get('min', 0)
            return ('call', int(amount or 0))
        for action in valid_actions:
            amt = action.get('amount', 0)
            if isinstance(amt, dict):
                amt = amt.get('min', 0)
            return (action['action'], int(amt or 0))
