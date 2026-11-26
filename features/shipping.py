"""Express Shipping implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["shipping"] = lambda a, b: round(9.99 + (a * 0.5) + (b * 0.05), 2)

# Pytest Unit Tests
def run_test_shipping():
    assert OPS["shipping"](10.0, 20.0) == 15.99
    assert OPS["shipping"](0.0, 0.0) == 9.99
