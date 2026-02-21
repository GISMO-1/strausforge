from strausforge.coverage import coverage_report, covered_residues, uncovered_residues
from strausforge.identities import Identity


def _identity(modulus: int, residues: list[int], name: str = "id") -> Identity:
    return Identity(
        name=name,
        modulus=modulus,
        residues=residues,
        x_form="n",
        y_form="n",
        z_form="n",
        conditions=[],
        notes="",
    )


def test_covered_residues_lifts_dividing_moduli() -> None:
    identities = [_identity(2, [0], "even"), _identity(4, [3], "mod4_3")]
    covered = covered_residues(identities, modulus=8)
    assert covered == {0, 2, 3, 4, 6, 7}


def test_covered_residues_ignores_non_dividing_moduli() -> None:
    identities = [_identity(3, [1], "mod3_1")]
    assert covered_residues(identities, modulus=8) == set()


def test_uncovered_residues_and_report_are_deterministic() -> None:
    identities = [_identity(2, [0], "even"), _identity(4, [3], "mod4_3")]

    uncovered = uncovered_residues(identities, modulus=8)
    assert uncovered == {1, 5}

    report = coverage_report(identities, modulus=8)
    assert report["modulus"] == 8
    assert report["total_residues"] == 8
    assert report["covered_count"] == 6
    assert report["uncovered_count"] == 2
    assert report["covered_pct"] == 75.0
    assert report["covered_residues"] == [0, 2, 3, 4, 6, 7]
    assert report["uncovered_residues"] == [1, 5]


def test_covered_residues_validates_modulus() -> None:
    try:
        covered_residues([], modulus=0)
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("expected ValueError for modulus <= 0")
