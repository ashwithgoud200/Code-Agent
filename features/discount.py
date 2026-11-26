"""Seasonal Coupon (20% Off) implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["discount"] = lambda a, b: max(0.0, round(a - (a * b / 100.0), 2))

# Pytest Unit Tests
def run_test_discount():
    assert OPS["discount"](100.0, 20.0) == 80.0
    assert OPS["discount"](50.0, 100.0) == 0.0
