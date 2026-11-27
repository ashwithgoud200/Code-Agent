"""Loyalty Points implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["points"] = lambda a: int(a * 10)

# Pytest Unit Tests
def run_test_points():
    assert OPS["points"](50.0) == 500
    assert OPS["points"](12.5) == 125
