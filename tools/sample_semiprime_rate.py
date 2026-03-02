#!/usr/bin/env python3
"""Deterministic semiprime-rate sampling over configurable mod-48 residues.

Examples:
    python tools/sample_semiprime_rate.py --n-min 2 --n-max 100000 --step 97
    python tools/sample_semiprime_rate.py --n-min 2 --n-max 100000 --step 97 --residues 1,25
"""

import argparse
import math
from typing import Dict, List, Sequence


def parse_residues(raw: str) -> List[int]:
    """Parse a comma-separated residue list.

    Args:
        raw: Comma-separated list, e.g. ``"1,25"``.

    Returns:
        Normalized integer residues in ``[0, 47]`` preserving order.

    Raises:
        ValueError: If no residues are provided.
    """

    items = [part.strip() for part in raw.split(",") if part.strip()]
    if not items:
        raise ValueError("At least one residue is required")
    return [int(value) % 48 for value in items]


def sieve_primes(limit: int) -> List[int]:
    if limit < 2:
        return []
    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0:2] = b"\x00\x00"
    for p in range(2, int(limit**0.5) + 1):
        if is_prime[p]:
            is_prime[p*p:limit+1:p] = b"\x00" * (((limit - p*p) // p) + 1)
    return [i for i in range(2, limit + 1) if is_prime[i]]


def factorize(n: int, primes: List[int]) -> Dict[int, int]:
    rem = n
    fac = {}
    for p in primes:
        if p * p > rem:
            break
        if rem % p == 0:
            e = 0
            while rem % p == 0:
                rem //= p
                e += 1
            fac[p] = e
    if rem > 1:
        fac[rem] = 1
    return fac


def omega_total(fac: Dict[int, int]) -> int:
    return sum(fac.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, required=True)
    ap.add_argument("--n-max", type=int, required=True)
    ap.add_argument("--step", type=int, default=1000)
    ap.add_argument(
        "--residues",
        type=str,
        default="1,25",
        help="Comma-separated mod-48 residues to sample (default: 1,25)",
    )
    args = ap.parse_args()
    residues: Sequence[int] = tuple(parse_residues(args.residues))

    limit = int(math.isqrt(args.n_max)) + 1
    primes = sieve_primes(limit)

    total = 0
    semiprime = 0

    for n in range(args.n_min, args.n_max + 1, args.step):
        if n % 48 not in residues:
            continue
        total += 1
        fac = factorize(n, primes)
        if omega_total(fac) == 2:
            semiprime += 1

    print(f"sampled_candidates: {total}")
    print(f"semiprime_count: {semiprime}")
    if total:
        print(f"semiprime_rate: {semiprime/total:.6f}")


if __name__ == "__main__":
    main()
