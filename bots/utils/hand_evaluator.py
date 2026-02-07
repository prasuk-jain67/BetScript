"""
Hand evaluation module for basic poker strategy.
Evaluates hand strength using poker ranking logic.
"""
from itertools import combinations
from collections import Counter


class HandEvaluator:
    """Evaluates poker hand strength on a 0-1 scale."""
    
    # Hand rank values
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10
    
    # Card value mapping
    CARD_VALUES = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    
    @staticmethod
    def parse_card(card_str):
        """Parse card string like 'SA' or '2H' into value and suit."""
        if len(card_str) != 2:
            return None, None
        
        # Card format: suit + value (e.g., 'HA' for Ace of Hearts)
        suit, value_str = card_str[0], card_str[1]
        value = HandEvaluator.CARD_VALUES.get(value_str)
        return value, suit
    
    @staticmethod
    def is_flush(suits):
        """Check if 5 cards are a flush."""
        suit_counts = Counter(suits)
        return max(suit_counts.values()) >= 5
    
    @staticmethod
    def is_straight(values):
        """Check if 5 cards are a straight."""
        sorted_vals = sorted(values, reverse=True)
        # Check regular straight
        if sorted_vals[0] - sorted_vals[4] == 4 and len(set(sorted_vals)) == 5:
            return True, sorted_vals[0]
        
        # Check A-2-3-4-5 (wheel)
        if sorted_vals == [14, 5, 4, 3, 2]:
            return True, 5
        
        return False, 0
    
    @staticmethod
    def get_hand_rank(values):
        """Determine hand rank from 5 card values."""
        value_counts = Counter(values)
        counts = sorted(value_counts.values(), reverse=True)
        
        is_flush = len(set(len(cards) for cards in [values])) == 1  # Placeholder
        is_straight_check, straight_high = HandEvaluator.is_straight(values)
        
        # Determine hand type
        if counts == [4, 1]:
            return HandEvaluator.FOUR_OF_A_KIND
        elif counts == [3, 2]:
            return HandEvaluator.FULL_HOUSE
        elif counts == [3, 1, 1]:
            return HandEvaluator.THREE_OF_A_KIND
        elif counts == [2, 2, 1]:
            return HandEvaluator.TWO_PAIR
        elif counts == [2, 1, 1, 1]:
            return HandEvaluator.ONE_PAIR
        else:
            return HandEvaluator.HIGH_CARD
    
    @staticmethod
    def evaluate_hole_cards(hole_card, community_cards):
        """
        Evaluate strength of hole cards.
        Returns a hand strength value between 0 and 1.
        
        Args:
            hole_card: List of 2 cards (e.g., ['SA', 'SK'])
            community_cards: List of 0-5 community cards (e.g., ['H2', 'D3', 'C4'])
        
        Returns:
            float: Hand strength 0-1
        """
        # Parse cards
        all_cards = hole_card + community_cards
        card_values = []
        card_suits = []
        
        for card in all_cards:
            value, suit = HandEvaluator.parse_card(card)
            if value is None:
                return 0.0  # Invalid card
            card_values.append(value)
            card_suits.append(suit)
        
        num_cards = len(all_cards)
        
        # Preflop: evaluate hole cards only
        if num_cards == 2:
            return HandEvaluator._evaluate_preflop(card_values)
        
        # Postflop: find best 5-card hand
        if num_cards >= 5:
            best_rank = 0
            best_kicker = 0
            
            for five_card_combo in combinations(range(num_cards), 5):
                combo_values = [card_values[i] for i in five_card_combo]
                combo_suits = [card_suits[i] for i in five_card_combo]
                
                # Check for flush
                is_flush = len(set(combo_suits)) == 1
                
                # Check for straight
                is_straight_check, straight_high = HandEvaluator.is_straight(combo_values)
                
                # Get base rank
                rank = HandEvaluator.get_hand_rank(combo_values)
                
                # Special cases for flush/straight
                if is_flush and is_straight_check:
                    if straight_high == 14 and set(combo_values) == {14, 13, 12, 11, 10}:
                        rank = HandEvaluator.ROYAL_FLUSH
                    else:
                        rank = HandEvaluator.STRAIGHT_FLUSH
                elif is_flush:
                    rank = HandEvaluator.FLUSH
                elif is_straight_check:
                    rank = HandEvaluator.STRAIGHT
                
                # Get kicker for tiebreaker
                kicker = max(combo_values)
                
                if rank > best_rank or (rank == best_rank and kicker > best_kicker):
                    best_rank = rank
                    best_kicker = kicker
            
            return HandEvaluator._rank_to_strength(best_rank, best_kicker)
        
        return 0.0
    
    @staticmethod
    def _evaluate_preflop(hole_values):
        """Evaluate preflop hand strength."""
        v1, v2 = sorted(hole_values, reverse=True)
        
        # Pair
        if v1 == v2:
            # Pair strength: 22=0.25, AA=1.0
            return 0.25 + (v1 - 2) * (0.75 / 12)
        
        # High card
        high_card_strength = (v1 / 14) * 0.5  # High card contributes up to 0.5
        gap = v1 - v2
        gap_penalty = (gap / 13) * 0.2  # Gap penalty up to 0.2
        
        return 0.05 + high_card_strength - gap_penalty
    
    @staticmethod
    def _rank_to_strength(rank, kicker):
        """Convert hand rank to strength value (0-1)."""
        base_strength = (rank / 10) * 0.88  # Rank contributes up to 0.88
        kicker_bonus = (kicker / 14) * 0.12  # Kicker contributes up to 0.12
        return base_strength + kicker_bonus
    
    @staticmethod
    def get_hand_strength_category(strength):
        """Categorize hand strength."""
        if strength < 0.2:
            return "very_weak"
        elif strength < 0.4:
            return "weak"
        elif strength < 0.6:
            return "medium"
        elif strength < 0.8:
            return "strong"
        else:
            return "very_strong"
