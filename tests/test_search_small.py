from strausforge.erdos_straus import check_identity, find_solution, find_solution_fast


def test_find_solution_for_small_range() -> None:
    for n in range(2, 201):
        solution = find_solution(n)
        assert solution is not None, f"Expected a solution for n={n}"
        x, y, z = solution
        assert check_identity(n, x, y, z)


def test_find_solution_fast_for_small_range() -> None:
    # 2..500 stays comfortably fast in CI while still giving broad coverage.
    for n in range(2, 501):
        solution = find_solution_fast(n)
        assert solution is not None, f"Expected a fast-solver solution for n={n}"
        x, y, z = solution
        assert check_identity(n, x, y, z)


def test_find_solution_returns_none_for_invalid_n() -> None:
    assert find_solution(1) is None
    assert find_solution(0) is None
    assert find_solution_fast(1) is None
    assert find_solution_fast(0) is None
