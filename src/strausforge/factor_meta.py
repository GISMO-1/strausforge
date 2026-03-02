"""Bounded factor and structure metadata helpers for expanded hardness cases."""

from __future__ import annotations

import json
import math
from typing import TextIO


def is_prime_trial(n_value: int) -> bool:
    """Return whether ``n_value`` is prime via deterministic trial division."""
    if n_value <= 1:
        return False
    if n_value <= 3:
        return True
    if n_value % 2 == 0:
        return False

    limit = math.isqrt(n_value)
    for divisor in range(3, limit + 1, 2):
        if n_value % divisor == 0:
            return False
    return True


def smallest_prime_factor_bounded(n_value: int, bound: int) -> int:
    """Return the smallest prime factor of ``n_value`` up to ``bound``, else 0.

    The search always caps at ``isqrt(n_value)`` and checks 2 first, then odd
    divisors in ascending order.
    """
    if n_value <= 1:
        return 0
    if n_value % 2 == 0:
        return 2

    limit = min(max(bound, 0), math.isqrt(n_value))
    for divisor in range(3, limit + 1, 2):
        if n_value % divisor == 0:
            return divisor
    return 0


def semiprime_kind_from_spf(n_value: int, spf: int) -> tuple[int, str]:
    """Classify ``n_value`` using its smallest factor.

    Returns ``(cofactor, kind)`` where kind is one of ``"p*q"``, ``"p^2"``, or
    ``""`` when classification is unknown/not semiprime.
    """
    if spf <= 0:
        return 0, ""

    cofactor = n_value // spf
    if cofactor == spf:
        return cofactor, "p^2"
    if is_prime_trial(cofactor):
        return cofactor, "p*q"
    return cofactor, ""


def write_jsonl_record(handle: TextIO, payload: dict[str, int | str]) -> None:
    """Write one deterministic JSONL object line."""
    handle.write(json.dumps(payload, sort_keys=True) + "\n")
