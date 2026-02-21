"""Deterministic end-to-end mining loop for identity coverage improvements."""

from __future__ import annotations

from pathlib import Path

from .cert import make_certificate, to_jsonl
from .coverage import coverage_report
from .erdos_straus import find_solution_fast
from .identities import Identity, identity_from_jsonl, identity_to_jsonl
from .mine import mine_identities

IdentityKey = tuple[int, tuple[int, ...], str, str, str]


def _load_identities(path: Path) -> list[Identity]:
    identities: list[Identity] = []
    if not path.exists():
        return identities

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            identities.append(identity_from_jsonl(stripped))
    return identities


def _identity_key(identity: Identity) -> IdentityKey:
    return (
        identity.modulus,
        tuple(sorted(set(identity.residues))),
        identity.x_form,
        identity.y_form,
        identity.z_form,
    )


def _target_examples(modulus: int, residue: int, limit: int) -> list[int]:
    examples: list[int] = []
    value = residue if residue > 0 else modulus
    while value < 2:
        value += modulus

    while len(examples) < limit:
        examples.append(value)
        value += modulus
    return examples


def run_loop(
    identity_path: Path,
    modulus: int,
    *,
    max_targets: int,
    max_per_target: int,
    max_new_identities: int,
) -> dict[str, object]:
    """Run one deterministic iterative coverage-improvement loop.

    The loop computes uncovered residues, certifies targeted examples, mines new
    identities, appends truly new identities to ``identity_path``, and reports
    coverage delta before/after.
    """
    if modulus <= 0:
        raise ValueError("modulus must be a positive integer")

    identities = _load_identities(identity_path)
    before = coverage_report(identities, modulus=modulus)
    uncovered = list(before["uncovered_residues"])
    targets = uncovered[:max_targets]

    certs_path = Path("data") / f"certs_targets_m{modulus}.jsonl"
    certs_path.parent.mkdir(parents=True, exist_ok=True)

    n_examples: list[int] = []
    for residue in targets:
        n_examples.extend(_target_examples(modulus, residue, max_per_target))
    n_examples = sorted(set(n_examples))

    with certs_path.open("w", encoding="utf-8") as handle:
        for n in n_examples:
            solution = find_solution_fast(n)
            if solution is None:
                cert = make_certificate(n=n, x=0, y=0, z=0, method="loop_v1", elapsed_ms=0.0)
            else:
                x, y, z = solution
                cert = make_certificate(n=n, x=x, y=y, z=z, method="loop_v1", elapsed_ms=0.0)
            handle.write(to_jsonl(cert) + "\n")

    mined_path = identity_path.parent / f".{identity_path.name}.loop_mined.tmp"
    mined_identities = mine_identities(certs_path, mined_path, max_identities=max_new_identities)

    seen = {_identity_key(identity) for identity in identities}
    new_identities: list[Identity] = []
    for identity in mined_identities:
        key = _identity_key(identity)
        if key in seen:
            continue
        seen.add(key)
        new_identities.append(identity)

    if new_identities:
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        with identity_path.open("a", encoding="utf-8") as handle:
            for identity in new_identities:
                handle.write(identity_to_jsonl(identity) + "\n")

    if mined_path.exists():
        mined_path.unlink()

    all_identities = identities + new_identities
    after = coverage_report(all_identities, modulus=modulus)

    return {
        "before": before,
        "after": after,
        "targets_used": len(targets),
        "n_tested": len(n_examples),
        "certs_written": certs_path,
        "identities_added": len(new_identities),
        "added_identity_names": [identity.name for identity in new_identities],
    }
