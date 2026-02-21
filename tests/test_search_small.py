from strausforge.erdos_straus import check_identity, find_solution


def test_find_solution_for_small_range() -> None:
    for n in range(2, 201):
        solution = find_solution(n)
        assert solution is not None, f"Expected a solution for n={n}"
        x, y, z = solution
        assert check_identity(n, x, y, z)


def test_find_solution_returns_none_for_invalid_n() -> None:
    assert find_solution(1) is None
    assert find_solution(0) is None
