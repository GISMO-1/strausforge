#!/usr/bin/env python3
"""
Deterministic sampling of semiprime rate in a range.
Samples every k-th integer and measures semiprime frequency
restricted to residues 1 and 25 mod 48.
"""

import argparse
import math
from typing import Dict, List


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, required=True)
    ap.add_argument("--n-max", type=int, required=True)
    ap.add_argument("--step", type=int, default=1000)
    args = ap.parse_args()

    limit = int(math.isqrt(args.n_max)) + 1
    primes = sieve_primes(limit)

    total = 0
    semiprime = 0

    for n in range(args.n_min, args.n_max + 1, args.step):
        if n % 48 not in (1, 25):
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