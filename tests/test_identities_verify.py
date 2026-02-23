from pathlib import Path

from strausforge.erdos_straus import check_identity
from strausforge.identities import (
    eval_identity,
    identity_from_jsonl,
    verify_identity,
    verify_identity_symbolic,
)


def _load_identities(path: Path):
    identities = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            identities.append(identity_from_jsonl(stripped))
    return identities


def test_seed_identity_eval_and_verify() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    assert identities

    identity = identities[0]
    candidates = [n for n in range(2, 40) if n % identity.modulus in set(identity.residues)]
    assert candidates

    for n in candidates[:5]:
        triple = eval_identity(identity, n)
        assert triple is not None

    stats = verify_identity(identity, n_min=2, n_max=200)
    assert stats["tested"] > 0
    assert stats["failed"] == 0


def test_at_least_one_symbolic_identity() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    assert any(verify_identity_symbolic(identity) for identity in identities)


def test_procedural_regression_values_resolve_with_valid_decompositions() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}

    targets = {
        "fit_proc_m48_r1": [18481, 35809],
        "fit_proc_m48_r25": [58921, 87481, 99961],
    }

    for identity_name, values in targets.items():
        identity = by_name[identity_name]
        for n in values:
            triple = eval_identity(identity, n)
            assert triple is not None
            x, y, z = triple
            assert check_identity(n=n, x=x, y=y, z=z)


def test_procedural_identities_have_no_failures_on_small_verify_window() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    procedural = [
        identity
        for identity in identities
        if identity.name in {"fit_proc_m48_r1", "fit_proc_m48_r25"}
    ]

    assert len(procedural) == 2
    for identity in procedural:
        stats = verify_identity(identity, n_min=2, n_max=5000)
        assert stats["tested"] > 0
        assert stats["failed"] == 0
