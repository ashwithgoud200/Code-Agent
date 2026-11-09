"""Logarithm implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["log"] = lambda a: math.log(a) if a > 0 else (_ for _ in ()).throw(ValueError("log of non-positive number"))

# Pytest Unit Tests
def run_test_log():
    assert round(OPS["log"](math.e), 4) == 1.0
    try:
        OPS["log"](0)
        assert False, 'Zero log not caught'
    except ValueError:
        pass
