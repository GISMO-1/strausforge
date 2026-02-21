from pathlib import Path

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
