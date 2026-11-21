"""Representability checks for numeric tokens in physical model JSON."""
import math


def finite_float(token):
    value = float(token)
    significand = token.lower().partition("e")[0]
    if not math.isfinite(value) or (value == 0 and any(c in "123456789" for c in significand)):
        raise ValueError("JSON number not representable as finite float64: " + token)
    return value
