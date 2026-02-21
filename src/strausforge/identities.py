"""Identity representation and verification helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from fractions import Fraction

import sympy

from .erdos_straus import check_identity


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
        notes: Human-readable metadata.
    """

    name: str
    modulus: int
    residues: list[int]
    x_form: str
    y_form: str
    z_form: str
    conditions: list[str]
    notes: str


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
        notes=str(payload.get("notes", "")),
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


def eval_identity(identity: Identity, n: int) -> tuple[int, int, int] | None:
    """Evaluate one identity at ``n`` and validate exact equality."""
    if n <= 0:
        return None
    if not _conditions_hold(identity, n):
        return None

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
