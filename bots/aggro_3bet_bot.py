import random
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
BUTTON_OPEN_RANGE |= offsuit_plus("A", "5")
BUTTON_OPEN_RANGE |= suited_plus("K", "2")
BUTTON_OPEN_RANGE |= offsuit_plus("K", "8")
BUTTON_OPEN_RANGE |= suited_plus("Q", "5")
BUTTON_OPEN_RANGE |= offsuit_plus("Q", "8")
BUTTON_OPEN_RANGE |= suited_plus("J", "6")
BUTTON_OPEN_RANGE |= offsuit_plus("J", "8")
BUTTON_OPEN_RANGE |= suited_plus("T", "6")
BUTTON_OPEN_RANGE |= offsuit_plus("T", "8")
BUTTON_OPEN_RANGE |= suited_range("9", "5", "5")
BUTTON_OPEN_RANGE |= suited_range("8", "5", "5")
BUTTON_OPEN_RANGE |= suited_range("7", "4", "4")
BUTTON_OPEN_RANGE |= suited_range("6", "4", "4")

AGGRO_3BET_VALUE = set()
AGGRO_3BET_VALUE |= pair_range("J")
AGGRO_3BET_VALUE |= {"AQs", "AQo", "AKs", "AKo"}

AGGRO_3BET_BLUFF = {
    "A5s", "A4s", "A3s", "A2s",
    "K9s", "K8s", "K7s",
    "Q9s", "Q8s",
    "J9s", "J8s",
    "T9s", "T8s",
    "98s", "87s", "76s", "65s",
}

AGGRO_4BET_VALUE = {"QQ", "KK", "AA", "AKs", "AKo"}
AGGRO_4BET_BLUFF = {"ATo", "A9s", "A8s", "A7s", "A6s"}
AGGRO_FLAT_RANGE = {
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
        sb_pos = round_state.get("small_blind_pos")
        bb_pos = round_state.get("big_blind_pos")
        is_button = our_index == dealer_btn
        is_blind = our_index in {sb_pos, bb_pos}

        context = self._preflop_context(round_state)
        raises = context["raises"]

        if context["facing_4bet"]:
            if hand_key in AGGRO_4BET_VALUE:
                if self._call_amount(valid_actions) > 0:
                    return self._call(valid_actions)
                return self._raise_amount(valid_actions, prefer_max=True)
            return self._fold(valid_actions)

        if context["facing_3bet"] and is_button:
            if hand_key in AGGRO_4BET_VALUE or hand_key in AGGRO_4BET_BLUFF:
                return self._raise_amount(valid_actions)
            if hand_key in AGGRO_FLAT_RANGE:
                return self._call(valid_actions)
            return self._fold(valid_actions)

        if context["facing_open"] and is_blind:
            raiser_uuid = raises[-1].get("uuid") if raises else None
            raiser_index = self._seat_index(seats, raiser_uuid)
            if raiser_index == dealer_btn:
                if hand_key in AGGRO_3BET_VALUE or hand_key in AGGRO_3BET_BLUFF:
                    return self._raise_amount(valid_actions)
                if hand_key in AGGRO_FLAT_RANGE:
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
            if self._can_raise(valid_actions) and random.random() < 0.6:
                return self._raise_amount(valid_actions)
            return self._call(valid_actions)

        if self._can_raise(valid_actions) and self.preflop_aggressor and random.random() < 0.5:
            return self._raise_amount(valid_actions)

        return self._safe_call_or_fold(valid_actions)
