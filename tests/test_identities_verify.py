from pathlib import Path

from strausforge.erdos_straus import check_identity
from strausforge.identities import (
    _eval_procedural_identity,
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


def test_prime_window_heuristic_turns_known_hard_prime_into_fast_path() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r1"]

    n_value = 35809
    _, baseline_path, baseline_window, _ = _eval_procedural_identity(identity, n_value)
    _, heuristic_path, heuristic_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="prime-window",
    )

    assert baseline_path == "expanded"
    assert baseline_window == 64
    assert heuristic_path == "fast"
    assert heuristic_window == 64


def test_procedural_heuristic_off_matches_eval_default_behavior() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r25"]
    n_value = 58921

    baseline = eval_identity(identity, n_value)
    explicit_off = eval_identity(identity, n_value, proc_heuristic="off")
    assert baseline == explicit_off


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


def test_prime_or_square_window_heuristic_turns_known_prime_square_into_fast_path() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r25"]

    n_value = 994009
    _, baseline_path, baseline_window, _ = _eval_procedural_identity(identity, n_value)
    _, heuristic_path, heuristic_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="prime-or-square-window",
    )

    assert baseline_path == "expanded"
    assert baseline_window == 64
    assert heuristic_path == "fast"
    assert heuristic_window == 64



def test_semiprime_window_heuristic_increases_initial_window_for_triggered_semiprime() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r1"]

    n_value = 22033
    _, baseline_path, baseline_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="off",
    )
    _, heuristic_path, heuristic_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="semiprime-window",
        semiprime_factor_bound=5000,
    )

    assert baseline_path == "fast"
    assert baseline_window == 8
    assert heuristic_path == "fast"
    assert heuristic_window == 128


def test_semiprime_window_heuristic_does_not_trigger_for_prime_candidate() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r1"]

    n_value = 35809
    _, baseline_path, baseline_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="off",
    )
    _, heuristic_path, heuristic_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="semiprime-window",
        semiprime_factor_bound=5000,
    )

    assert baseline_path == "expanded"
    assert heuristic_path == "expanded"
    assert baseline_window == heuristic_window == 64

def test_prime_or_square_or_semiprime_window_preserves_prime_square_behavior() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}

    prime_identity = by_name["fit_proc_m48_r1"]
    prime_n = 35809
    _, prime_posw_path, prime_posw_window, _ = _eval_procedural_identity(
        prime_identity,
        prime_n,
        proc_heuristic="prime-or-square-window",
    )
    _, prime_combined_path, prime_combined_window, _ = _eval_procedural_identity(
        prime_identity,
        prime_n,
        proc_heuristic="prime-or-square-or-semiprime-window",
    )

    assert prime_posw_path == prime_combined_path == "fast"
    assert prime_posw_window == prime_combined_window == 64

    square_identity = by_name["fit_proc_m48_r25"]
    square_n = 994009
    _, square_posw_path, square_posw_window, _ = _eval_procedural_identity(
        square_identity,
        square_n,
        proc_heuristic="prime-or-square-window",
    )
    _, square_combined_path, square_combined_window, _ = _eval_procedural_identity(
        square_identity,
        square_n,
        proc_heuristic="prime-or-square-or-semiprime-window",
    )

    assert square_posw_path == square_combined_path == "fast"
    assert square_posw_window == square_combined_window == 64


def test_prime_or_square_or_semiprime_window_triggers_semiprime_case() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    by_name = {identity.name: identity for identity in identities}
    identity = by_name["fit_proc_m48_r1"]

    n_value = 22033
    _, baseline_path, baseline_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="prime-or-square-window",
    )
    _, heuristic_path, heuristic_window, _ = _eval_procedural_identity(
        identity,
        n_value,
        proc_heuristic="prime-or-square-or-semiprime-window",
        semiprime_factor_bound=5000,
    )

    assert baseline_path == "fast"
    assert baseline_window == 8
    assert heuristic_path == "fast"
    assert heuristic_window == 128


def test_symbolic_expression_cache_preserves_eval_results() -> None:
    identities = _load_identities(Path("data/identities.jsonl"))
    symbolic = next(identity for identity in identities if identity.kind == "symbolic")

    sample_n = [n for n in range(2, 200) if n % symbolic.modulus in set(symbolic.residues)][:8]
    assert sample_n

    baseline = [eval_identity(symbolic, n) for n in sample_n]
    repeated = [eval_identity(symbolic, n) for n in sample_n]

    assert baseline == repeated
