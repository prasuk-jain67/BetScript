"""
Observant heuristic bot — greedy but opponent-aware.

Features:
- Uses `bots.utils.hand_evaluator.HandEvaluator` for hand strength.
- Considers action history (folds, raises) to compute opponent aggression.
- Estimates pot from action history and uses a simple pot-odds check.
- Adjusts willingness-to-call based on number of active players and opponent aggression.
"""
from bots.base import CountingBot
from bots.utils.hand_evaluator import HandEvaluator
from collections import defaultdict


class Bot(CountingBot):
    AGGRESSION_BY_STREET = {
        'preflop': 0.55,
        'flop': 0.7,
        'turn': 0.8,
        'river': 0.95
    }

    def declare_action(self, valid_actions, hole_card, round_state):
        try:
            street = round_state.get('street', 'preflop')
            community_cards = round_state.get('community_card', [])

            # Basic evaluation
            hand_strength = HandEvaluator.evaluate_hole_cards(hole_card, community_cards)

            # Action history analysis
            action_histories = round_state.get('action_histories', {})
            stats = self._analyze_actions(action_histories)

            # Players still active (not folded)
            players_active = stats['players_active']

            # Opponent aggression metric (normalized)
            opp_aggr = stats['avg_raises_per_player']

            # Estimate pot from actions
            pot = stats['pot']

            # Current call amount and our stack
            current_call_amount = self._get_call_amount(valid_actions)
            my_stack = self._get_my_stack(round_state)

            # Base willingness to risk from hand strength and street aggression
            base_aggr = self.AGGRESSION_BY_STREET.get(street, 0.7)
            max_call_ratio = hand_strength * base_aggr

            # Adjust for number of players: more players -> be tighter
            if players_active >= 4:
                max_call_ratio *= 0.75
            elif players_active == 3:
                max_call_ratio *= 0.9

            # If opponents are passive (few raises), loosen up; if aggressive, tighten
            if opp_aggr < 0.2:
                max_call_ratio *= 1.15
            elif opp_aggr > 0.5:
                max_call_ratio *= 0.85

            # Pot odds simple check: if calling is small relative to pot, call even with weaker hand
            pot_odds = 0.0
            if pot + current_call_amount > 0:
                pot_odds = current_call_amount / (pot + current_call_amount)

            # Convert max_call_ratio to absolute amount of stack willing to call
            max_call_amount = my_stack * max(0.02, min(0.9, max_call_ratio))

            # Decision rules
            # 1) If pot odds are favorable compared to hand strength, call
            if current_call_amount > 0 and pot_odds < max(0.5, hand_strength * 0.9):
                # If strong and can raise -> raise
                if hand_strength > 0.7 and self._can_raise(valid_actions):
                    raise_amount = self._calculate_raise_amount(hand_strength, current_call_amount, my_stack, players_active)
                    return self._get_raise_action(valid_actions, raise_amount)
                return self._execute_call(valid_actions)

            # 2) If current call cost is within our allowed maximum, proceed
            if current_call_amount <= max_call_amount:
                # Consider raising when hand is strong and table is passive
                if hand_strength > 0.65 and opp_aggr < 0.35 and self._can_raise(valid_actions):
                    raise_amount = self._calculate_raise_amount(hand_strength, current_call_amount, my_stack, players_active)
                    return self._get_raise_action(valid_actions, raise_amount)
                return self._execute_call(valid_actions)

            # 3) Otherwise fold
            fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
            if fold_action:
                return 'fold', 0
            return self._execute_call(valid_actions)
        except Exception:
            return self._execute_call(valid_actions)

    def _analyze_actions(self, action_histories):
        """Produce simple stats: pot size estimate, raises per player, active players."""
        pot = 0
        raises_by_player = defaultdict(int)
        last_action_by_player = {}
        players_seen = set()

        for street in ['preflop', 'flop', 'turn', 'river']:
            for a in action_histories.get(street, []) or []:
                # Support different keys used by round_state
                name = a.get('player_uuid') or a.get('name') or a.get('player') or a.get('player_name')
                act = a.get('action') or a.get('type')
                amount = a.get('amount', 0)
                try:
                    amount = int(amount)
                except Exception:
                    amount = 0

                if name:
                    players_seen.add(name)
                    last_action_by_player[name] = act
                if act in ('raise', 'bet'):
                    raises_by_player[name] += 1
                    pot += amount
                elif act in ('call', 'check'):
                    pot += amount
                elif act == 'fold':
                    # fold doesn't add to pot
                    pass

        # players active = those seen who didn't fold as last action
        players_active = sum(1 for p in players_seen if last_action_by_player.get(p) != 'fold')
        total_raises = sum(raises_by_player.values())
        avg_raises = (total_raises / players_active) if players_active > 0 else 0.0

        return {
            'pot': pot,
            'raises_by_player': dict(raises_by_player),
            'avg_raises_per_player': avg_raises,
            'players_active': max(1, players_active)
        }

    def _get_call_amount(self, valid_actions):
        call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
        if not call_action:
            return 0
        amt = call_action.get('amount', 0)
        if isinstance(amt, dict):
            return int(amt.get('min', 0))
        return int(amt or 0)

    def _get_my_stack(self, round_state):
        seats = round_state.get('seats', [])
        for seat in seats:
            if seat.get('uuid') == self.uuid:
                return seat.get('stack', 0)
        return 0

    def _can_raise(self, valid_actions):
        return any(a['action'] == 'raise' for a in valid_actions)

    def _calculate_raise_amount(self, hand_strength, current_bet, stack, players_active):
        # Scale raise by hand strength and exploit number of players
        if hand_strength < 0.7:
            return max(current_bet * 2, int(stack * 0.05))
        if hand_strength < 0.85:
            return max(current_bet * 3, int(stack * 0.08))
        # Very strong hands: size up by number of active players
        size = 0.2 + (players_active - 1) * 0.05
        return int(stack * min(0.5, size))

    def _get_raise_action(self, valid_actions, amount):
        raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
        if raise_action:
            min_amount = raise_action['amount']['min']
            max_amount = raise_action['amount']['max']
            amount = max(min_amount, min(max_amount, int(amount)))
            return 'raise', int(amount)
        return self._execute_call(valid_actions)

    def _execute_call(self, valid_actions):
        call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
        if call_action:
            amount = call_action.get('amount', 0)
            if isinstance(amount, dict):
                amount = amount.get('min', 0)
            return 'call', int(amount or 0)
        # fallback
        if valid_actions:
            a = valid_actions[0]
            amt = a.get('amount', 0)
            if isinstance(amt, dict):
                amt = amt.get('min', 0)
            return a.get('action'), int(amt or 0)
        return 'fold', 0
