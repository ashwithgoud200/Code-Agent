"""Discount Coupon Engine Feature Plugin for eCommerce Microservice."""
from typing import Any

def apply_coupon(code: str, subtotal: float) -> float:
    c = str(code).upper().strip()
    if c == "DEVOPS20":
        return round(subtotal * 0.20, 2)
    elif c == "SAVE10":
        return min(10.0, subtotal)
    elif c == "BLACKFRIDAY":
        return round(subtotal * 0.30, 2)
    return 0.0

DYNAMIC_FEATURES["coupon"] = apply_coupon
