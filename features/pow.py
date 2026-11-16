"""Power implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["pow"] = lambda a, b: a ** b

# Pytest Unit Tests
def run_test_pow():
    res = OPS["pow"](10, 2)
    assert isinstance(res, (int, float))
