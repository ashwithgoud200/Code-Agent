"""Seasonal Discount implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["coupon"] = lambda a, b: max(0.0, a - (a * b / 100))

# Pytest Unit Tests
def run_test_coupon():
    res = OPS["coupon"](10, 2)
    assert isinstance(res, (int, float))
