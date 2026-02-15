from bots.strategy_base import (
    RangeBot,
    normalize_hand_key,
    pair_range,
    suited_plus,
    offsuit_plus,
    suited_range,
    evaluate_hand,
)

BUTTON_OPEN_RANGE = set()
BUTTON_OPEN_RANGE |= pair_range("2")
BUTTON_OPEN_RANGE |= suited_plus("A", "2")
BUTTON_OPEN_RANGE |= offsuit_plus("A", "7")
BUTTON_OPEN_RANGE |= suited_plus("K", "2")
BUTTON_OPEN_RANGE |= offsuit_plus("K", "9")
BUTTON_OPEN_RANGE |= suited_plus("Q", "6")
BUTTON_OPEN_RANGE |= offsuit_plus("Q", "9")
BUTTON_OPEN_RANGE |= suited_plus("J", "7")
BUTTON_OPEN_RANGE |= offsuit_plus("J", "9")
BUTTON_OPEN_RANGE |= suited_plus("T", "7")
BUTTON_OPEN_RANGE |= offsuit_plus("T", "9")
BUTTON_OPEN_RANGE |= suited_range("9", "6", "6")
BUTTON_OPEN_RANGE |= suited_range("8", "6", "6")
BUTTON_OPEN_RANGE |= suited_range("7", "5", "5")
BUTTON_OPEN_RANGE |= suited_range("6", "5", "5")

BUTTON_4BET_VALUE = {"QQ", "KK", "AA", "AKs", "AKo"}
BUTTON_4BET_BLUFF = {"ATo", "A9s", "A8s", "A7s"}
BUTTON_FLAT_RANGE = {
    "JJ", "TT", "99", "88",
    "AQs", "AQo", "AJs", "AJo", "ATs",
    "KQs", "KQo", "KJs", "KJo", "KTs",
    "QJs", "QTs", "JTs",
}


class Bot(RangeBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        street = round_state.get("street", "preflop")
        hand_key = normalize_hand_key(hole_card)
        if street != "preflop" or hand_key is None:
            return self._postflop_action(valid_actions, hole_card, round_state)

        seats = round_state.get("seats", [])
        our_index = self._seat_index(seats, self.uuid)
        dealer_btn = round_state.get("dealer_btn")
        is_button = our_index == dealer_btn

        context = self._preflop_context(round_state)

        if context["facing_4bet"] and is_button:
            if hand_key in BUTTON_4BET_VALUE:
                if self._call_amount(valid_actions) > 0:
                    return self._call(valid_actions)
                return self._raise_amount(valid_actions, prefer_max=True)
            return self._fold(valid_actions)

        if context["facing_3bet"] and is_button:
            if hand_key in BUTTON_4BET_VALUE or hand_key in BUTTON_4BET_BLUFF:
                return self._raise_amount(valid_actions)
            if hand_key in BUTTON_FLAT_RANGE:
                return self._call(valid_actions)
            return self._fold(valid_actions)

        if context["unopened"] and is_button:
            if hand_key in BUTTON_OPEN_RANGE:
                return self._raise_amount(valid_actions)
            return self._fold(valid_actions)

        return self._safe_call_or_fold(valid_actions)

    def _postflop_action(self, valid_actions, hole_card, round_state):
        community_cards = round_state.get("community_card", [])
        info = evaluate_hand(hole_card, community_cards)

        if info["strong"]:
            if self._can_raise(valid_actions):
                return self._raise_amount(valid_actions)
            return self._call(valid_actions)

        if info["medium"]:
            if self._can_raise(valid_actions) and self.preflop_aggressor:
                return self._raise_amount(valid_actions)
            return self._call(valid_actions)

        if info["draw"]:
            if self._can_raise(valid_actions) and self.preflop_aggressor:
                return self._raise_amount(valid_actions)
            return self._call(valid_actions)

        return self._safe_call_or_fold(valid_actions)
