"""Core identities and baseline search for the Erdős–Straus conjecture."""

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
