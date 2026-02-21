from fractions import Fraction

from strausforge.erdos_straus import check_identity


def test_check_identity_true_example() -> None:
    assert check_identity(5, 2, 4, 20)


def test_check_identity_false_case() -> None:
    assert not check_identity(5, 2, 5, 20)


def test_check_identity_uses_exact_rational_arithmetic() -> None:
    n, x, y, z = 11, 3, 34, 1122
    assert Fraction(4, n) == Fraction(1, x) + Fraction(1, y) + Fraction(1, z)
    assert check_identity(n, x, y, z)
