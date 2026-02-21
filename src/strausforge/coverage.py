"""Residue-class coverage helpers for mined identities."""

from __future__ import annotations

from .identities import Identity


def covered_residues(identities: list[Identity], modulus: int) -> set[int]:
    """Compute residues covered modulo ``modulus``.

    An identity with modulus ``m`` contributes when ``m`` divides ``modulus``.
    For each residue ``r`` in that identity, all lifted classes
    ``r + k*m (mod modulus)`` are covered.
    """
    if modulus <= 0:
        raise ValueError("modulus must be a positive integer")

    covered: set[int] = set()
    for identity in identities:
        if identity.modulus <= 0 or modulus % identity.modulus != 0:
            continue
        step = identity.modulus
        for residue in identity.residues:
            lifted = residue % step
            covered.update(range(lifted, modulus, step))
    return covered


def uncovered_residues(identities: list[Identity], modulus: int) -> set[int]:
    """Compute residues not covered modulo ``modulus``."""
    universe = set(range(modulus))
    return universe - covered_residues(identities, modulus)


def coverage_report(identities: list[Identity], modulus: int) -> dict[str, object]:
    """Build a deterministic coverage summary.

    Returns counts/percentage and sorted residue lists for covered/uncovered classes.
    """
    covered = covered_residues(identities, modulus)
    uncovered = set(range(modulus)) - covered
    total = modulus

    return {
        "modulus": modulus,
        "total_residues": total,
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "covered_pct": (len(covered) / total) * 100.0,
        "covered_residues": sorted(covered),
        "uncovered_residues": sorted(uncovered),
    }
