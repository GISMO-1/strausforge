"""Core identities and baseline/fast search for the Erdős–Straus conjecture."""

from __future__ import annotations

import math
from fractions import Fraction


def check_identity(n: int, x: int, y: int, z: int) -> bool:
    """Return True iff ``4/n == 1/x + 1/y + 1/z`` exactly.

    Uses exact rational arithmetic to avoid floating-point error.
    """
    if min(n, x, y, z) <= 0:
        return False
    left = Fraction(4, n)
    right = Fraction(1, x) + Fraction(1, y) + Fraction(1, z)
    return left == right


def _solve_two_unit_fraction(
    remainder: Fraction,
    *,
    max_y: int | None,
) -> tuple[int, int] | None:
    """Solve ``1/y + 1/z = remainder`` via divisor enumeration.

    For ``remainder = a/b`` in lowest terms, positive solutions satisfy:

    ``(a*y - b) * (a*z - b) = b^2``.

    Enumerating divisors of ``b^2`` gives exact integral candidates.
    """
    if remainder <= 0:
        return None

    a = remainder.numerator
    b = remainder.denominator
    b2 = b * b

    y_min = math.ceil(b / a)
    y_max = math.floor(2 * b / a)
    if max_y is not None:
        y_max = min(y_max, max_y)
    if y_min > y_max:
        return None

    root = math.isqrt(b2)
    for d in range(1, root + 1):
        if b2 % d != 0:
            continue

        for factor in (d, b2 // d):
            y_num = factor + b
            if y_num % a != 0:
                continue
            y = y_num // a
            if not (y_min <= y <= y_max):
                continue

            paired = b2 // factor
            z_num = paired + b
            if z_num % a != 0:
                continue
            z = z_num // a
            if z <= 0:
                continue
            return (y, z)

    return None


def find_solution(n: int) -> tuple[int, int, int] | None:
    """Search for one decomposition for ``4/n`` as three unit fractions.

    The algorithm is deterministic and intentionally simple:
    - Iterate x from ceil(n/4) to a bounded range
    - Compute the remaining rational value r = 4/n - 1/x
    - Iterate candidate y and derive z from the residual

    Returns:
        A tuple ``(x, y, z)`` if found, else ``None``.
    """
    if n <= 1:
        return None

    x_start = max(1, math.ceil(n / 4))
    x_limit = max(x_start + 1, 5 * n)

    for x in range(x_start, x_limit + 1):
        remainder = Fraction(4, n) - Fraction(1, x)
        if remainder <= 0:
            continue

        a = remainder.numerator
        b = remainder.denominator

        y_start = max(1, math.ceil(b / a))
        y_limit = 20 * n

        for y in range(y_start, y_limit + 1):
            numerator = a * y - b
            if numerator <= 0:
                continue

            denominator = b * y
            if denominator % numerator != 0:
                continue

            z = denominator // numerator
            if z <= 0:
                continue

            if check_identity(n, x, y, z):
                return (x, y, z)

    return None


def find_solution_fast(
    n: int,
    *,
    max_x: int | None = None,
    max_y: int | None = None,
) -> tuple[int, int, int] | None:
    """Find a decomposition using deterministic constructive+bounded heuristics.

    Strategy order:
    1) Quick constructive families:
       - Even ``n``: ``4/n = 1/(n/2) + 1/n + 1/n``.
       - ``n ≡ 3 (mod 4)``: split ``4/n = 1/((n+1)/4) + 4/(n(n+1))`` and then
         ``4/(n(n+1)) = 1/(n(n+1)/2) + 1/(n(n+1)/2)``.
    2) Two-term reduction for each ``x`` candidate, solved exactly by divisors
       of ``b^2`` for ``1/y + 1/z = a/b``.
    3) Bounded ``y`` scan with ceil/floor bounds as a final deterministic fallback.
    """
    if n <= 1:
        return None

    if n % 2 == 0:
        candidate = (n // 2, n, n)
        if check_identity(n, *candidate):
            return candidate

    if n % 4 == 3:
        x = (n + 1) // 4
        yz = n * (n + 1) // 2
        candidate = (x, yz, yz)
        if check_identity(n, *candidate):
            return candidate

    x_start = math.ceil(n / 4)
    computed_x_max = max(4 * n, x_start + 1)
    x_limit = min(computed_x_max, max_x) if max_x is not None else computed_x_max

    for x in range(x_start, x_limit + 1):
        remainder = Fraction(4, n) - Fraction(1, x)
        if remainder <= 0:
            continue

        yz = _solve_two_unit_fraction(remainder, max_y=max_y)
        if yz is not None:
            y, z = yz
            if check_identity(n, x, y, z):
                return (x, y, z)

        a = remainder.numerator
        b = remainder.denominator

        y_start = math.ceil(b / a)
        y_stop = math.floor(2 * b / a)
        if max_y is not None:
            y_stop = min(y_stop, max_y)
        if y_start > y_stop:
            continue

        for y in range(y_start, y_stop + 1):
            numerator = a * y - b
            if numerator <= 0:
                continue

            denominator = b * y
            if denominator % numerator != 0:
                continue
            z = denominator // numerator
            if z <= 0:
                continue

            if check_identity(n, x, y, z):
                return (x, y, z)

    return None
