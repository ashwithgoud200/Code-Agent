"""square implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["square"] = lambda a: a*a

# Pytest Unit Tests
def run_test_square():
    res = OPS["square"](10)
    assert isinstance(res, (int, float))
