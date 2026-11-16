"""Express Shipping implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["shipping"] = lambda a, b: 9.99 + (a * 0.5) + (b * 0.05)

# Pytest Unit Tests
def run_test_shipping():
    res = OPS["shipping"](10, 2)
    assert isinstance(res, (int, float))
