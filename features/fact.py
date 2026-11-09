"""Factorial implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["fact"] = lambda a: math.factorial(int(a)) if 0 <= int(a) <= 20 else (_ for _ in ()).throw(ValueError("factorial input out of bounds [0, 20]"))

# Pytest Unit Tests
def run_test_fact():
    assert OPS["fact"](5) == 120.0
    assert OPS["fact"](0) == 1.0
    try:
        OPS["fact"](-3)
        assert False, 'Negative factorial not caught'
    except ValueError:
        pass
