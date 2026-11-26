"""Add a 20% seasonal coupon discount on ca implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["adda20seasonalco"] = lambda a, b: max(0.0, round(a - (a * b / 100.0), 2))

# Pytest Unit Tests
def run_test_adda20seasonalco():
    assert OPS["adda20seasonalco"](100.0, 20.0) == 80.0
    assert OPS["adda20seasonalco"](50.0, 100.0) == 0.0
