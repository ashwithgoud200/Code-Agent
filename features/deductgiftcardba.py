"""Deduct gift card balance b from order su implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["deductgiftcardba"] = lambda a, b: max(0.0, a - b)

# Pytest Unit Tests
def run_test_deductgiftcardba():
    assert OPS["deductgiftcardba"](100.0, 25.0) == 75.0
    assert OPS["deductgiftcardba"](20.0, 50.0) == 0.0
