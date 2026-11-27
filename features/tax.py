"""State Sales Tax implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["tax"] = lambda a, b: round(a * (b / 100.0), 2)

# Pytest Unit Tests
def run_test_tax():
    assert OPS["tax"](100.0, 8.25) == 8.25
    assert OPS["tax"](200.0, 5.0) == 10.0
