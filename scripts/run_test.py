import os
import sys
from types import SimpleNamespace

# Ensure project root is on path
sys.path.insert(0, os.getcwd())

from poker.utils import play_test_match

bot_files = [
    "bots/aggressive_bot.py",
    "bots/always_call_bot.py",
    "bots/cautious_bot.py",
    "bots/probability_based_bot.py",
    "bots/random_bot.py",
]

bots = [SimpleNamespace(name="Aggressive"), SimpleNamespace(name="Always_Call"), SimpleNamespace(name="Cautious_bot"), SimpleNamespace(name="Probability_based_bot"), SimpleNamespace(name="Random_bot")]
bot_paths = [os.path.join(os.getcwd(), p) for p in bot_files]

if os.path.exists("poker_output.txt"):
    try:
        os.remove("poker_output.txt")
    except Exception:
        pass

result = play_test_match(bot_paths, bots)
print("PLAY_TEST_MATCH RESULT:\n", result)

if os.path.exists("poker_output.txt"):
    with open("poker_output.txt", "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    print("\n--- poker_output.txt (last 2000 chars) ---\n")
    print(content[-2000:])
