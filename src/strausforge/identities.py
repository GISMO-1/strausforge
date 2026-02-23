"""Identity representation and verification helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

import sympy

from .erdos_straus import check_identity, find_solution_fast


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


def _eval_procedural_identity(identity: Identity, n_value: int) -> tuple[int, int, int]:
    if identity.procedural_params is None:
        raise ValueError(f"Procedural identity {identity.name} has no procedural_params.")

    anchor = str(identity.procedural_params.get("anchor", "(n+5)//4"))
    if anchor != "(n+5)//4":
        raise ValueError(f"Unsupported anchor expression for procedural identity {identity.name}.")

    initial_window = int(identity.procedural_params.get("window", 8))
    initial_t_max = int(identity.procedural_params.get("t_max", 256))
    if initial_window < 0 or initial_t_max < 0:
        raise ValueError(f"Procedural parameters must be non-negative for {identity.name}.")

    x0 = (n_value + 5) // 4
    target = Fraction(4, n_value)

    attempts: list[tuple[int, int]] = [(initial_window, initial_t_max)]
    if initial_window < 64:
        attempts.append((64, initial_t_max))
    if initial_t_max < 4096:
        attempts.append((max(initial_window, 64), 4096))

    for window, t_max in attempts:
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
                    return (x_value, y_value, z_value)

    solved = find_solution_fast(n_value)
    if solved is not None:
        return solved

    raise RuntimeError(
        "Procedural identity matched residue class but no decomposition was found "
        f"for n={n_value} via procedural search or solver fallback."
    )


def _eval_expr_int(expression: str, n_value: int) -> int | None:
    n = sympy.Symbol("n", integer=True)
    expr = sympy.sympify(expression, locals={"n": n})
    value = sympy.simplify(expr.subs({n: n_value}))
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


def _conditions_hold(identity: Identity, n_value: int) -> bool:
    if identity.modulus <= 0:
        return False
    if n_value % identity.modulus not in set(identity.residues):
        return False

    n = sympy.Symbol("n", integer=True)
    for condition in identity.conditions:
        condition_expr = sympy.sympify(condition, locals={"n": n})
        evaluated = condition_expr.subs({n: n_value})
        if bool(evaluated) is False:
            return False
    return True


def identity_applies(identity: Identity, n: int) -> bool:
    """Return whether an identity is applicable to ``n`` by gate+conditions."""
    if n <= 0:
        return False
    return _conditions_hold(identity, n)


def eval_identity(identity: Identity, n: int) -> tuple[int, int, int] | None:
    """Evaluate one identity at ``n`` and validate exact equality."""
    if not identity_applies(identity, n):
        return None

    if identity.kind == "procedural":
        return _eval_procedural_identity(identity, n)

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


def verify_identity(identity: Identity, n_min: int, n_max: int) -> dict[str, object]:
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
        result = eval_identity(identity, n)
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
