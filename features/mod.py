"""Modulo Remainder implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["mod"] = lambda a, b: a % b if b != 0 else (_ for _ in ()).throw(ZeroDivisionError("division by zero in modulo"))

# Pytest Unit Tests
def run_test_mod():
    assert OPS["mod"](14, 4) == 2.0
    assert OPS["mod"](10, 3) == 1.0
    try:
        OPS["mod"](10, 0)
        assert False, 'Zero division not caught'
    except ZeroDivisionError:
        pass
