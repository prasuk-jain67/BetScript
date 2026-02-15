from bots.base import CountingBot

RANK_ORDER = "23456789TJQKA"


def _rank_index(rank):
    return RANK_ORDER.index(rank)


def _normalize_hand_key(hole_card):
    if len(hole_card) != 2:
        return None
    card_a, card_b = hole_card
    rank_a, rank_b = card_a[1], card_b[1]
    suited = card_a[0] == card_b[0]
    if rank_a == rank_b:
        return f"{rank_a}{rank_b}"
    if _rank_index(rank_a) < _rank_index(rank_b):
        rank_a, rank_b = rank_b, rank_a
    return f"{rank_a}{rank_b}{'s' if suited else 'o'}"


def _pair_range(start_rank):
    start_idx = _rank_index(start_rank)
    return {f"{RANK_ORDER[i]}{RANK_ORDER[i]}" for i in range(start_idx, len(RANK_ORDER))}


def _suited_range(high_rank, low_start, low_end):
    start_idx = _rank_index(low_end)
    end_idx = _rank_index(low_start)
    return {
        f"{high_rank}{RANK_ORDER[i]}s"
        for i in range(start_idx, end_idx + 1)
        if _rank_index(high_rank) > i
    }


def _offsuit_range(high_rank, low_start, low_end):
    start_idx = _rank_index(low_end)
    end_idx = _rank_index(low_start)
    return {
        f"{high_rank}{RANK_ORDER[i]}o"
        for i in range(start_idx, end_idx + 1)
        if _rank_index(high_rank) > i
    }


def _suited_plus(high_rank, low_start):
    return _suited_range(high_rank, low_start, RANK_ORDER[_rank_index(high_rank) - 1])


def _offsuit_plus(high_rank, low_start):
    return _offsuit_range(high_rank, low_start, RANK_ORDER[_rank_index(high_rank) - 1])


BUTTON_OPEN_RANGE = set()
BUTTON_OPEN_RANGE |= _pair_range("2")
BUTTON_OPEN_RANGE |= _suited_plus("A", "2")
BUTTON_OPEN_RANGE |= _offsuit_plus("A", "7")
BUTTON_OPEN_RANGE |= _suited_plus("K", "2")
BUTTON_OPEN_RANGE |= _offsuit_plus("K", "9")
BUTTON_OPEN_RANGE |= _suited_plus("Q", "6")
BUTTON_OPEN_RANGE |= _offsuit_plus("Q", "9")
BUTTON_OPEN_RANGE |= _suited_plus("J", "7")
BUTTON_OPEN_RANGE |= _offsuit_plus("J", "9")
BUTTON_OPEN_RANGE |= _suited_plus("T", "7")
BUTTON_OPEN_RANGE |= _offsuit_plus("T", "9")
BUTTON_OPEN_RANGE |= _suited_range("9", "6", "6")
BUTTON_OPEN_RANGE |= _suited_range("8", "6", "6")
BUTTON_OPEN_RANGE |= _suited_range("7", "5", "5")
BUTTON_OPEN_RANGE |= _suited_range("6", "5", "5")

OOP_VALUE_RANGE = set()
OOP_VALUE_RANGE |= _pair_range("T")
OOP_VALUE_RANGE |= {"AQs", "AQo", "AKs", "AKo"}

OOP_FLAT_RANGE = {
    "99", "88", "77",
    "AJs", "ATs", "AJo",
    "KTs", "KJs", "KQs", "KQo",
    "QJs", "JTs",
}

OOP_3BET_AIR_RANGE = {
    "66", "55", "44", "33", "22",
    "A9s", "A8s", "A7s", "A6s",
    "K9s", "K8s",
    "QTs", "Q9s",
    "J9s", "J8s",
    "97s", "98s", "9Ts",
    "87s", "76s", "65s",
}

BUTTON_4BET_VALUE = {"QQ", "KK", "AA", "AKs", "AKo"}
BUTTON_4BET_BLUFF = {"ATo", "A9s", "A8s", "A7s"}
BUTTON_FLAT_RANGE = {
    "JJ", "TT", "99", "88",
    "AQs", "AQo", "AJs", "AJo", "ATs",
    "KQs", "KQo", "KJs", "KJo", "KTs",
    "QJs", "QTs", "JTs",
}


class Bot(CountingBot):
    def declare_action(self, valid_actions, hole_card, round_state):
        street = round_state.get("street", "preflop")
        hand_key = _normalize_hand_key(hole_card)
        if street != "preflop" or hand_key is None:
            return self._safe_call_or_fold(valid_actions)

        seats = round_state.get("seats", [])
        our_index = self._seat_index(seats, self.uuid)
        dealer_btn = round_state.get("dealer_btn")
        sb_pos = round_state.get("small_blind_pos")
        bb_pos = round_state.get("big_blind_pos")

        is_button = our_index == dealer_btn
        is_sb = our_index == sb_pos
        is_bb = our_index == bb_pos

        actions = round_state.get("action_histories", {}).get("preflop", [])
        raises = [action for action in actions if action.get("action") == "raise"]
        our_raised = any(
            action.get("uuid") == self.uuid and action.get("action") == "raise"
            for action in actions
        )

        facing_4bet = our_raised and len(raises) >= 3 and raises[-1].get("uuid") != self.uuid
        facing_3bet = our_raised and len(raises) == 2 and raises[-1].get("uuid") != self.uuid
        facing_open = (not our_raised) and len(raises) == 1
        unopened = len(raises) == 0

        if facing_4bet:
            if hand_key in OOP_VALUE_RANGE or hand_key in BUTTON_4BET_VALUE:
                return self._raise_amount(valid_actions, prefer_max=True)
            return self._fold(valid_actions)

        if facing_3bet and is_button:
            if hand_key in BUTTON_4BET_VALUE or hand_key in BUTTON_4BET_BLUFF:
                return self._raise_amount(valid_actions)
            if hand_key in BUTTON_FLAT_RANGE:
                return self._call(valid_actions)
            return self._fold(valid_actions)

        if facing_open and (is_sb or is_bb):
            raiser_uuid = raises[-1].get("uuid") if raises else None
            raiser_index = self._seat_index(seats, raiser_uuid)
            if raiser_index == dealer_btn:
                if hand_key in OOP_VALUE_RANGE or hand_key in OOP_3BET_AIR_RANGE:
                    return self._raise_amount(valid_actions)
                if hand_key in OOP_FLAT_RANGE:
                    return self._call(valid_actions)
                return self._fold(valid_actions)

        if unopened and is_button:
            if hand_key in BUTTON_OPEN_RANGE:
                return self._raise_amount(valid_actions)
            return self._fold(valid_actions)

        return self._safe_call_or_fold(valid_actions)

    def _seat_index(self, seats, uuid):
        for index, seat in enumerate(seats):
            if seat.get("uuid") == uuid:
                return index
        return None

    def _raise_amount(self, valid_actions, prefer_max=False):
        action = next((a for a in valid_actions if a["action"] == "raise"), None)
        if not action:
            return self._safe_call_or_fold(valid_actions)
        amount = action.get("amount", 0)
        if isinstance(amount, dict):
            amount = amount.get("max" if prefer_max else "min", 0)
        return action["action"], int(amount or 0)

    def _call(self, valid_actions):
        action = next((a for a in valid_actions if a["action"] == "call"), None)
        if not action:
            return self._safe_call_or_fold(valid_actions)
        amount = action.get("amount", 0)
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return action["action"], int(amount or 0)

    def _fold(self, valid_actions):
        action = next((a for a in valid_actions if a["action"] == "fold"), None)
        if not action:
            return self._safe_call_or_fold(valid_actions)
        return action["action"], 0

    def _safe_call_or_fold(self, valid_actions):
        call_action = next((a for a in valid_actions if a["action"] == "call"), None)
        if call_action:
            amount = call_action.get("amount", 0)
            if isinstance(amount, dict):
                amount = amount.get("min", 0)
            return call_action["action"], int(amount or 0)
        return self._fold(valid_actions)
