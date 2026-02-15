import random
from collections import Counter
from bots.base import CountingBot

RANK_ORDER = "23456789TJQKA"


def rank_index(rank):
    return RANK_ORDER.index(rank)


def normalize_hand_key(hole_card):
    if len(hole_card) != 2:
        return None
    card_a, card_b = hole_card
    rank_a, rank_b = card_a[1], card_b[1]
    suited = card_a[0] == card_b[0]
    if rank_a == rank_b:
        return f"{rank_a}{rank_b}"
    if rank_index(rank_a) < rank_index(rank_b):
        rank_a, rank_b = rank_b, rank_a
    return f"{rank_a}{rank_b}{'s' if suited else 'o'}"


def pair_range(start_rank):
    start_idx = rank_index(start_rank)
    return {f"{RANK_ORDER[i]}{RANK_ORDER[i]}" for i in range(start_idx, len(RANK_ORDER))}


def suited_range(high_rank, low_start, low_end):
    start_idx = rank_index(low_end)
    end_idx = rank_index(low_start)
    return {
        f"{high_rank}{RANK_ORDER[i]}s"
        for i in range(start_idx, end_idx + 1)
        if rank_index(high_rank) > i
    }


def offsuit_range(high_rank, low_start, low_end):
    start_idx = rank_index(low_end)
    end_idx = rank_index(low_start)
    return {
        f"{high_rank}{RANK_ORDER[i]}o"
        for i in range(start_idx, end_idx + 1)
        if rank_index(high_rank) > i
    }


def suited_plus(high_rank, low_start):
    return suited_range(high_rank, low_start, RANK_ORDER[rank_index(high_rank) - 1])


def offsuit_plus(high_rank, low_start):
    return offsuit_range(high_rank, low_start, RANK_ORDER[rank_index(high_rank) - 1])


def _card_rank_value(rank):
    return rank_index(rank) + 2


def _is_straight(ranks):
    unique = sorted(set(ranks))
    if 14 in unique:
        unique.insert(0, 1)
    for i in range(len(unique) - 4):
        window = unique[i:i + 5]
        if window[-1] - window[0] == 4 and len(window) == 5:
            return True
    return False


def _has_straight_draw(ranks):
    unique = sorted(set(ranks))
    if 14 in unique:
        unique.insert(0, 1)
    for start in range(1, 11):
        count = sum(1 for rank in unique if start <= rank <= start + 4)
        if count >= 4:
            return True
    return False


def evaluate_hand(hole_cards, community_cards):
    cards = list(hole_cards) + list(community_cards)
    if not cards:
        return {
            "category": "none",
            "strong": False,
            "medium": False,
            "draw": False,
        }

    ranks = [_card_rank_value(card[1]) for card in cards]
    suits = [card[0] for card in cards]
    rank_counts = Counter(ranks)
    counts = sorted(rank_counts.values(), reverse=True)
    is_flush = max(Counter(suits).values()) >= 5
    is_straight = _is_straight(ranks)

    if is_flush and is_straight:
        category = "straight_flush"
    elif 4 in counts:
        category = "quads"
    elif 3 in counts and 2 in counts:
        category = "full_house"
    elif is_flush:
        category = "flush"
    elif is_straight:
        category = "straight"
    elif 3 in counts:
        category = "trips"
    elif counts.count(2) >= 2:
        category = "two_pair"
    elif 2 in counts:
        category = "pair"
    else:
        category = "high_card"

    board_ranks = [_card_rank_value(card[1]) for card in community_cards]
    top_board = max(board_ranks) if board_ranks else None
    hole_ranks = [_card_rank_value(card[1]) for card in hole_cards]
    overpair = len(hole_ranks) == 2 and hole_ranks[0] == hole_ranks[1] and top_board
    overpair = bool(overpair and hole_ranks[0] > top_board)
    top_pair = top_board in hole_ranks if top_board else False

    draw = _has_straight_draw(ranks) or max(Counter(suits).values()) == 4

    strong = category in {"straight_flush", "quads", "full_house", "flush", "straight", "trips", "two_pair"}
    medium = category == "pair" and (top_pair or overpair)

    return {
        "category": category,
        "strong": strong,
        "medium": medium,
        "draw": draw,
    }


def should_cbet(aggression):
    return random.random() < aggression


class RangeBot(CountingBot):
    def __init__(self, bot_name):
        super().__init__(bot_name)
        self.preflop_aggressor = False

    def receive_round_start_message(self, round_count, hole_card, seats):
        self.preflop_aggressor = False
        super().receive_round_start_message(round_count, hole_card, seats)

    def _seat_index(self, seats, uuid):
        for index, seat in enumerate(seats):
            if seat.get("uuid") == uuid:
                return index
        return None

    def _last_raiser_uuid(self, actions):
        for action in reversed(actions):
            if action.get("action") == "raise":
                return action.get("uuid")
        return None

    def _preflop_context(self, round_state):
        actions = round_state.get("action_histories", {}).get("preflop", [])
        raises = [action for action in actions if action.get("action") == "raise"]
        our_raised = any(
            action.get("uuid") == self.uuid and action.get("action") == "raise"
            for action in actions
        )
        return {
            "actions": actions,
            "raises": raises,
            "our_raised": our_raised,
            "facing_open": (not our_raised) and len(raises) == 1,
            "facing_3bet": our_raised and len(raises) == 2 and raises[-1].get("uuid") != self.uuid,
            "facing_4bet": our_raised and len(raises) >= 3 and raises[-1].get("uuid") != self.uuid,
            "unopened": len(raises) == 0,
        }

    def _raise_amount(self, valid_actions, prefer_max=False):
        action = next((a for a in valid_actions if a["action"] == "raise"), None)
        if not action:
            return self._safe_call_or_fold(valid_actions)
        amount = action.get("amount", 0)
        if isinstance(amount, dict):
            amount = amount.get("max" if prefer_max else "min", 0)
        self.preflop_aggressor = True
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
        action = next((a for a in valid_actions if a["action"] == "call"), None)
        if action:
            amount = action.get("amount", 0)
            if isinstance(amount, dict):
                amount = amount.get("min", 0)
            return action["action"], int(amount or 0)
        return self._fold(valid_actions)

    def _call_amount(self, valid_actions):
        action = next((a for a in valid_actions if a["action"] == "call"), None)
        if not action:
            return 0
        amount = action.get("amount", 0)
        if isinstance(amount, dict):
            amount = amount.get("min", 0)
        return int(amount or 0)

    def _can_raise(self, valid_actions):
        return any(action.get("action") == "raise" for action in valid_actions)
