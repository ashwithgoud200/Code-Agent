"""Square Root implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["sqrt"] = lambda a: math.sqrt(a) if a >= 0 else (_ for _ in ()).throw(ValueError("square root of negative number"))

# Pytest Unit Tests
def run_test_sqrt():
    assert OPS["sqrt"](16) == 4.0
    assert OPS["sqrt"](0) == 0.0
    try:
        OPS["sqrt"](-9)
        assert False, 'Negative square root not caught'
    except ValueError:
        pass
