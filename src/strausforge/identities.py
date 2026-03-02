"""Identity representation and verification helpers."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Any

import sympy

from .erdos_straus import check_identity, find_solution_fast
from .factor_meta import semiprime_window_trigger


@dataclass(slots=True)
class Identity:
    """Parametric residue-class identity for ``4/n``.

    Attributes:
        name: Stable identifier for deduplication and reporting.
        modulus: Residue modulus for applicability.
        residues: Residue classes where the identity is intended to hold.
        x_form: SymPy/Python expression string in variable ``n``.
        y_form: SymPy/Python expression string in variable ``n``.
        z_form: SymPy/Python expression string in variable ``n``.
        conditions: Extra boolean constraints in ``n``.
        kind: Identity representation kind: ``symbolic`` or ``procedural``.
        procedural_params: Optional deterministic rule parameters.
        notes: Human-readable metadata.
    """

    name: str
    modulus: int
    residues: list[int]
    x_form: str
    y_form: str
    z_form: str
    conditions: list[str]
    notes: str = ""
    kind: str = "symbolic"
    procedural_params: dict[str, Any] | None = None


@dataclass(slots=True)
class HardCaseRecord:
    """One procedural evaluation that required non-fast-path solving."""

    identity: str
    n: int
    path: str
    window_used: int
    t_used: int


@dataclass(slots=True)
class ProceduralProfileStats:
    """Per-identity profiling counters for procedural evaluation behavior."""

    identity: str
    total_applications: int = 0
    fast_success: int = 0
    expanded_success: int = 0
    solver_fallback_success: int = 0
    expanded_prime_count: int = 0
    expanded_square_count: int = 0
    max_window_used: int = 0
    max_t_used: int = 0


@dataclass(slots=True)
class ProceduralProfile:
    """Aggregate profiling output over a range."""

    per_identity: dict[str, ProceduralProfileStats]
    hardest_records: list[HardCaseRecord]


_PATH_SEVERITY: dict[str, int] = {"fast": 0, "expanded": 1, "solver": 2}
_N_SYMBOL = sympy.Symbol("n", integer=True)


def _hard_case_sort_key(item: HardCaseRecord) -> tuple[int, int, int, int, str]:
    return (_PATH_SEVERITY[item.path], item.window_used, item.t_used, item.n, item.identity)


def sort_hard_cases(records: list[HardCaseRecord]) -> list[HardCaseRecord]:
    """Return deterministic hardest-case ordering.

    Cases are sorted by path severity, then window/t usage, then ``n``.
    """

    return sorted(records, key=_hard_case_sort_key)


def identity_to_jsonl(identity: Identity) -> str:
    """Serialize an :class:`Identity` to one JSONL line."""
    return json.dumps(asdict(identity), sort_keys=True)


def identity_from_jsonl(line: str) -> Identity:
    """Parse one JSONL line into an :class:`Identity`."""
    payload = json.loads(line)
    return Identity(
        name=str(payload["name"]),
        modulus=int(payload["modulus"]),
        residues=[int(item) for item in payload["residues"]],
        x_form=str(payload["x_form"]),
        y_form=str(payload["y_form"]),
        z_form=str(payload["z_form"]),
        conditions=[str(item) for item in payload.get("conditions", [])],
        kind=str(payload.get("kind", "symbolic")),
        procedural_params=payload.get("procedural_params"),
        notes=str(payload.get("notes", "")),
    )


def _ceil_reciprocal(value: Fraction) -> int:
    if value <= 0:
        raise ValueError("Expected positive fraction")
    return (value.denominator + value.numerator - 1) // value.numerator


def _build_attempts(initial_window: int, initial_t_max: int) -> list[tuple[int, int]]:
    attempts: list[tuple[int, int]] = [(initial_window, initial_t_max)]
    if initial_window < 64:
        attempts.append((64, initial_t_max))
    if initial_t_max < 4096:
        attempts.append((max(initial_window, 64), 4096))

    unique_attempts: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for attempt in attempts:
        if attempt in seen:
            continue
        seen.add(attempt)
        unique_attempts.append(attempt)
    return unique_attempts


def _eval_procedural_identity(
    identity: Identity,
    n_value: int,
    proc_heuristic: str = "off",
    semiprime_factor_bound: int = 5000,
) -> tuple[tuple[int, int, int], str, int, int]:
    if identity.procedural_params is None:
        raise ValueError(f"Procedural identity {identity.name} has no procedural_params.")

    anchor = str(identity.procedural_params.get("anchor", "(n+5)//4"))
    if anchor != "(n+5)//4":
        raise ValueError(f"Unsupported anchor expression for procedural identity {identity.name}.")

    initial_window = int(identity.procedural_params.get("window", 8))
    if proc_heuristic == "prime-window":
        initial_window = 64 if sympy.isprime(n_value) else 8
    elif proc_heuristic == "prime-or-square-window":
        is_square = _is_square(n_value)
        initial_window = 64 if sympy.isprime(n_value) or is_square else 8
    elif proc_heuristic == "prime-or-square-or-semiprime-window":
        is_prime = sympy.isprime(n_value)
        is_square = _is_square(n_value)
        if is_prime or is_square:
            initial_window = 64
        else:
            triggered, _, _ = semiprime_window_trigger(n_value, semiprime_factor_bound)
            initial_window = 128 if triggered else 8
    elif proc_heuristic == "semiprime-window":
        triggered, _, _ = semiprime_window_trigger(n_value, semiprime_factor_bound)
        initial_window = 128 if triggered else 8
    elif proc_heuristic != "off":
        raise ValueError(f"Unknown procedural heuristic: {proc_heuristic}")
    initial_t_max = int(identity.procedural_params.get("t_max", 256))
    if initial_window < 0 or initial_t_max < 0:
        raise ValueError(f"Procedural parameters must be non-negative for {identity.name}.")

    x0 = (n_value + 5) // 4
    target = Fraction(4, n_value)

    attempts = _build_attempts(initial_window, initial_t_max)

    for attempt_index, (window, t_max) in enumerate(attempts):
        for x_value in range(x0 - window, x0 + window + 1):
            if x_value < 2 or Fraction(1, x_value) >= target:
                continue
            remainder = target - Fraction(1, x_value)
            y_start = _ceil_reciprocal(remainder)
            for delta in range(t_max + 1):
                y_value = y_start + delta
                if y_value < 2:
                    continue
                tail = remainder - Fraction(1, y_value)
                if tail.numerator != 1 or tail.denominator <= 0:
                    continue
                z_value = tail.denominator
                if check_identity(n=n_value, x=x_value, y=y_value, z=z_value):
                    path = "fast" if attempt_index == 0 else "expanded"
                    return (x_value, y_value, z_value), path, window, delta

    solved = find_solution_fast(n_value)
    if solved is not None:
        max_window = max(window for window, _ in attempts)
        max_t = max(t_max for _, t_max in attempts)
        return solved, "solver", max_window, max_t

    raise RuntimeError(
        "Procedural identity matched residue class but no decomposition was found "
        f"for n={n_value} via procedural search or solver fallback."
    )


def _eval_expr_int(expression: str, n_value: int) -> int | None:
    expr = _sympify_with_n(expression)
    value = sympy.simplify(expr.subs({_N_SYMBOL: n_value}))
    if value.is_integer is False:
        return None
    if value.is_Rational:
        numerator, denominator = int(value.p), int(value.q)
        if denominator == 0 or numerator % denominator != 0:
            return None
        return numerator // denominator
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return None
    if sympy.Integer(int_value) != sympy.simplify(value):
        return None
    return int_value


def _is_square(n_value: int) -> bool:
    """Return whether ``n_value`` is a perfect square."""
    if n_value < 0:
        return False
    root = math.isqrt(n_value)
    return root * root == n_value


def _conditions_hold(identity: Identity, n_value: int) -> bool:
    if identity.modulus <= 0:
        return False
    if n_value % identity.modulus not in _residue_set(tuple(identity.residues)):
        return False

    for condition in identity.conditions:
        condition_expr = _sympify_with_n(condition)
        evaluated = condition_expr.subs({_N_SYMBOL: n_value})
        if bool(evaluated) is False:
            return False
    return True


@lru_cache(maxsize=1024)
def _sympify_with_n(expression: str) -> sympy.Expr:
    """Parse ``expression`` with a cached integer ``n`` symbol."""
    return sympy.sympify(expression, locals={"n": _N_SYMBOL})


@lru_cache(maxsize=1024)
def _residue_set(residues: tuple[int, ...]) -> frozenset[int]:
    """Return cached residue set for identity applicability checks."""
    return frozenset(int(item) for item in residues)


def identity_applies(identity: Identity, n: int) -> bool:
    """Return whether an identity is applicable to ``n`` by gate+conditions."""
    if n <= 0:
        return False
    return _conditions_hold(identity, n)


def eval_identity(
    identity: Identity,
    n: int,
    proc_heuristic: str = "off",
) -> tuple[int, int, int] | None:
    """Evaluate one identity at ``n`` and validate exact equality."""
    if not identity_applies(identity, n):
        return None

    if identity.kind == "procedural":
        triple, _, _, _ = _eval_procedural_identity(identity, n, proc_heuristic=proc_heuristic)
        return triple

    x = _eval_expr_int(identity.x_form, n)
    y = _eval_expr_int(identity.y_form, n)
    z = _eval_expr_int(identity.z_form, n)
    if x is None or y is None or z is None:
        return None
    if min(x, y, z) <= 0:
        return None

    left = Fraction(4, n)
    right = Fraction(1, x) + Fraction(1, y) + Fraction(1, z)
    if left != right:
        return None
    return (x, y, z)


def profile_identities(
    identities: list[Identity],
    n_min: int,
    n_max: int,
    top_k: int,
    proc_heuristic: str = "off",
    progress_callback: Callable[[int, int], None] | None = None,
) -> ProceduralProfile:
    """Profile identity evaluation behavior over ``[n_min, n_max]``.

    For procedural identities this records fast-path, expanded-search, and
    solver-fallback counters plus deterministic hardest cases.
    """

    per_identity: dict[str, ProceduralProfileStats] = {
        identity.name: ProceduralProfileStats(identity=identity.name) for identity in identities
    }
    hard_cases: list[HardCaseRecord] = []

    total_steps = len(identities) * (n_max - n_min + 1)
    completed_steps = 0
    for identity in identities:
        stats = per_identity[identity.name]
        for n_value in range(n_min, n_max + 1):
            completed_steps += 1
            if progress_callback is not None:
                progress_callback(completed_steps, total_steps)
            if not identity_applies(identity, n_value):
                continue

            stats.total_applications += 1
            if identity.kind != "procedural":
                triple = eval_identity(identity, n_value, proc_heuristic=proc_heuristic)
                if triple is not None:
                    stats.fast_success += 1
                continue

            triple, path, window_used, t_used = _eval_procedural_identity(
                identity,
                n_value,
                proc_heuristic=proc_heuristic,
            )
            if triple is None:
                continue
            stats.max_window_used = max(stats.max_window_used, window_used)
            stats.max_t_used = max(stats.max_t_used, t_used)

            if path == "fast":
                stats.fast_success += 1
            elif path == "expanded":
                stats.expanded_success += 1
                if sympy.isprime(n_value):
                    stats.expanded_prime_count += 1
                if _is_square(n_value):
                    stats.expanded_square_count += 1
                hard_cases.append(
                    HardCaseRecord(
                        identity=identity.name,
                        n=n_value,
                        path=path,
                        window_used=window_used,
                        t_used=t_used,
                    )
                )
            else:
                stats.solver_fallback_success += 1
                hard_cases.append(
                    HardCaseRecord(
                        identity=identity.name,
                        n=n_value,
                        path=path,
                        window_used=window_used,
                        t_used=t_used,
                    )
                )

    return ProceduralProfile(
        per_identity=per_identity,
        hardest_records=sort_hard_cases(hard_cases)[:top_k],
    )


def verify_identity(
    identity: Identity,
    n_min: int,
    n_max: int,
    proc_heuristic: str = "off",
) -> dict[str, object]:
    """Empirically verify identity over a closed range."""
    tested = 0
    passed = 0
    failed = 0
    first_failure: dict[str, int] | None = None

    for n in range(n_min, n_max + 1):
        if n % identity.modulus not in set(identity.residues):
            continue
        if not _conditions_hold(identity, n):
            continue

        tested += 1
        result = eval_identity(identity, n, proc_heuristic=proc_heuristic)
        if result is None:
            failed += 1
            if first_failure is None:
                first_failure = {"n": n}
            continue

        x, y, z = result
        if check_identity(n=n, x=x, y=y, z=z):
            passed += 1
        else:
            failed += 1
            if first_failure is None:
                first_failure = {"n": n, "x": x, "y": y, "z": z}

    return {
        "tested": tested,
        "passed": passed,
        "failed": failed,
        "first_failure": first_failure,
    }


def verify_identity_symbolic(identity: Identity) -> bool:
    """Attempt symbolic proof by residue substitution with SymPy."""
    if identity.kind == "procedural":
        return False
    n = sympy.Symbol("n", integer=True, positive=True)
    k = sympy.Symbol("k", integer=True, nonnegative=True)

    x_expr = sympy.sympify(identity.x_form, locals={"n": n})
    y_expr = sympy.sympify(identity.y_form, locals={"n": n})
    z_expr = sympy.sympify(identity.z_form, locals={"n": n})
    target = sympy.Rational(4, 1) / n - (
        sympy.Rational(1, 1) / x_expr
        + sympy.Rational(1, 1) / y_expr
        + sympy.Rational(1, 1) / z_expr
    )

    for residue in sorted(set(identity.residues)):
        substituted_n = identity.modulus * k + residue
        reduced = sympy.together(sympy.simplify(target.subs({n: substituted_n})))
        if sympy.simplify(reduced) != 0:
            return False

        for expr in (x_expr, y_expr, z_expr):
            candidate = sympy.simplify(expr.subs({n: substituted_n}))
            for check_k in range(0, 20):
                value = sympy.simplify(candidate.subs({k: check_k}))
                if value.is_real is False:
                    return False
                if value.is_zero:
                    return False
                if value.is_number and value <= 0:
                    return False

    return True
