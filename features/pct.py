"""Percentage implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["pct"] = lambda a, b: (a / 100.0) * b

# Pytest Unit Tests
def run_test_pct():
    assert OPS["pct"](20, 150) == 30.0
    assert OPS["pct"](50, 200) == 100.0
