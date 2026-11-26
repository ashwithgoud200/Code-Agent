"""Calculate Percent 100 implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["calculate"] = lambda a, b: (a / 100.0) * b

# Pytest Unit Tests
def run_test_calculate():
    assert OPS["calculate"](20, 150) == 30.0
    assert OPS["calculate"](50, 200) == 100.0
