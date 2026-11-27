"""Power implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (openai/gpt-oss-120b)
OPS["pow"] = lambda a, b: a ** b

# Pytest Unit Tests
def run_test_pow(): assert OPS["pow"](2, 3) == 8.0
