"""Factorial implementation for Calculator application."""
import math

# Feature Code synthesized by Code Agent (qwen2.5-coder:3b)
OPS["fact"] = lambda a: math.factorial(int(a)) if 0 <= int(a) <= 20 else (_ for _ in ()).throw(ValueError("factorial input out of bounds [0, 20]"))
