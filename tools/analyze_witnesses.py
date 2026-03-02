#!/usr/bin/env python3
"""
Deterministic witness analyzer for Strausforge expanded-case JSONL.

Reads one-object-per-line JSONL produced by:
  strausforge hardness ... --export-expanded <file>.jsonl

Outputs a CSV suitable for PowerShell Import-Csv.
IMPORTANT: PowerShell treats column headers case-insensitively, so we avoid
names like "omega" vs "Omega" and instead emit:
  omega_distinct, omega_total
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from typing import Dict, List, Tuple


def sieve_primes(limit: int) -> List[int]:
    """Simple deterministic sieve up to `limit` (inclusive)."""
    if limit < 2:
        return []
    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0:2] = b"\x00\x00"
    for p in range(2, int(limit**0.5) + 1):
        if is_prime[p]:
            step = p
            start = p * p
            is_prime[start : limit + 1 : step] = b"\x00" * (((limit - start) // step) + 1)
    return [i for i in range(2, limit + 1) if is_prime[i]]


def factorize(n: int, primes: List[int]) -> Dict[int, int]:
    """Return prime factorization dict {p: exponent} using trial division by `primes`."""
    rem = n
    fac: Dict[int, int] = {}
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
        fac[rem] = fac.get(rem, 0) + 1
    return fac


def format_factorization(fac: Dict[int, int]) -> str:
    parts = []
    for p in sorted(fac):
        e = fac[p]
        parts.append(f"{p}^{e}" if e != 1 else str(p))
    return " * ".join(parts)


def omega_distinct(fac: Dict[int, int]) -> int:
    """ω(n): number of distinct prime factors."""
    return len(fac)


def omega_total(fac: Dict[int, int]) -> int:
    """Ω(n): total number of prime factors counting multiplicity."""
    return sum(fac.values())


def is_squarefree(fac: Dict[int, int]) -> bool:
    return all(e == 1 for e in fac.values())


def semiprime_kind(fac: Dict[int, int]) -> str:
    """
    If Ω(n)=2 classify:
      - p^2 if only one distinct prime
      - p*q if two distinct primes
    else "".
    """
    if omega_total(fac) != 2:
        return ""
    return "p^2" if len(fac) == 1 else "p*q"


def nearest_square_delta(n: int) -> Tuple[int, int]:
    """
    Return (root, delta) where root^2 is the nearest square to n.
    delta = n - root^2 (can be negative if nearest square is above n).
    """
    r = int(math.isqrt(n))
    lo = r * r
    hi = (r + 1) * (r + 1)
    if (n - lo) <= (hi - n):
        return (r, n - lo)
    return (r + 1, n - hi)  # negative


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="expanded JSONL input")
    ap.add_argument("--out", dest="out", required=True, help="CSV output path")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    # Read JSONL
    records = []
    max_n = 0
    with open(args.inp, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"Invalid JSON on line {line_no}: {e}") from e
            if "n" not in obj:
                raise SystemExit(f"Missing 'n' field on line {line_no}")
            n = int(obj["n"])
            max_n = max(max_n, n)
            records.append(obj)

    # Precompute primes up to sqrt(max_n) for trial division
    limit = int(math.isqrt(max_n)) + 1
    primes = sieve_primes(limit)

    # Write CSV (PowerShell-friendly headers)
    with open(args.out, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow([
            "n",
            "res48",
            "identity",
            "t_used",
            "window_used",
            "factorization",
            "omega_distinct",
            "omega_total",
            "squarefree",
            "semiprime_kind",
            "spf",
            "lpf",
            "near_sq_root",
            "near_sq_delta",
        ])

        for obj in records:
            n = int(obj["n"])
            fac = factorize(n, primes)

            fac_str = format_factorization(fac)
            res48 = n % 48
            od = omega_distinct(fac)
            ot = omega_total(fac)
            sqf = 1 if is_squarefree(fac) else 0
            semi = semiprime_kind(fac)
            spf = min(fac) if fac else ""
            lpf = max(fac) if fac else ""
            r, d = nearest_square_delta(n)

            w.writerow([
                n,
                res48,
                obj.get("identity", ""),
                obj.get("t_used", ""),
                obj.get("window_used", ""),
                fac_str,
                od,
                ot,
                sqf,
                semi,
                spf,
                lpf,
                r,
                d,
            ])

    print(f"Wrote {len(records)} rows -> {args.out}")


if __name__ == "__main__":
    main()