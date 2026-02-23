import shutil
from pathlib import Path

from strausforge.coverage import coverage_report
from strausforge.identities import eval_identity, identity_from_jsonl
from strausforge.loop import run_loop


def _load_identities(path: Path) -> list:
    return [
        identity_from_jsonl(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_loop_adds_mod8_r1_identity_and_improves_mod48_coverage(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    shutil.copy(Path("data/identities.jsonl"), identity_file)

    before = coverage_report(_load_identities(identity_file), modulus=48)
    result = run_loop(
        identity_path=identity_file,
        modulus=48,
        max_targets=12,
        max_per_target=400,
        max_new_identities=20,
        target_timeout_seconds=15.0,
        progress_every=200,
    )

    after = result["after"]
    assert after["covered_count"] >= before["covered_count"]
    assert result["identities_added"] >= 0


def test_mod8_r1_identities_evaluate_exactly_on_sample_values(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    shutil.copy(Path("data/identities.jsonl"), identity_file)

    run_loop(
        identity_path=identity_file,
        modulus=48,
        max_targets=12,
        max_per_target=400,
        max_new_identities=20,
        target_timeout_seconds=15.0,
        progress_every=200,
    )

    identities = _load_identities(identity_file)
    mod8_r1 = [identity for identity in identities if "family=mod8_r1" in identity.notes]

    samples = [17, 41, 65, 89, 113]
    for identity in mod8_r1:
        for n in samples:
            triple = eval_identity(identity, n)
            assert triple is not None
            x, y, z = triple
            assert isinstance(x, int)
            assert isinstance(y, int)
            assert isinstance(z, int)
