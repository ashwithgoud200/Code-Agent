"""State Sales Tax implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["tax"] = lambda a, b: round(a * (b / 100), 2)

# Pytest Unit Tests
def run_test_tax():
    res = OPS["tax"](10, 2)
    assert isinstance(res, (int, float))
