"""Gift Card Balance implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["giftcard"] = lambda a, b: max(0.0, a - b)

# Pytest Unit Tests
def run_test_giftcard():
    assert OPS["giftcard"](100.0, 25.0) == 75.0
    assert OPS["giftcard"](20.0, 50.0) == 0.0
