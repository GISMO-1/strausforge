"""Deterministic identity mining from solved certificates."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .cert import Certificate, from_jsonl
from .identities import (
    Identity,
    identity_to_jsonl,
    verify_identity,
    verify_identity_symbolic,
)

MODULI = (4, 8, 12, 24, 48)


def _load_verified_certs(path: Path) -> list[Certificate]:
    certs: list[Certificate] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            cert = from_jsonl(stripped)
            if cert.verified:
                certs.append(cert)
    return certs


def _fit_affine(samples: list[tuple[int, int]]) -> str | None:
    if len(samples) < 2:
        return None
    n1, v1 = samples[0]
    for n2, v2 in samples[1:]:
        denom = n2 - n1
        if denom == 0:
            continue
        delta = v2 - v1
        if delta % denom != 0:
            continue
        a = delta // denom
        b = v1 - a * n1
        if all(a * n + b == value for n, value in samples):
            return _affine_expr(a=a, b=b)
    return None


def _affine_expr(a: int, b: int) -> str:
    if a == 0:
        return str(b)
    if b == 0:
        return f"{a}*n"
    sign = "+" if b > 0 else "-"
    return f"{a}*n{sign}{abs(b)}"


def _fit_linear_quotient(samples: list[tuple[int, int]]) -> str | None:
    for c in range(2, 25):
        scaled = [(n, value * c) for n, value in samples]
        affine = _fit_affine(scaled)
        if affine is None:
            continue

        a, b = _extract_affine_coefficients(affine)
        if a is None or b is None:
            continue
        if all((a * n + b) % c == 0 and (a * n + b) // c == value for n, value in samples):
            return f"({a}*n{b:+d})/{c}"
    return None


def _extract_affine_coefficients(expression: str) -> tuple[int | None, int | None]:
    if "*n" not in expression:
        return (0, int(expression))
    a_part, _, b_part = expression.partition("*n")
    a = int(a_part)
    if not b_part:
        return (a, 0)
    return (a, int(b_part))


def _fit_bilinear(samples: list[tuple[int, int]]) -> str | None:
    for c in range(1, 25):
        maybe_a: int | None = None
        ok = True
        for n, value in samples:
            num = value * c - n * n
            if n == 0 or num % n != 0:
                ok = False
                break
            a = num // n
            maybe_a = a if maybe_a is None else maybe_a
            if maybe_a != a:
                ok = False
                break
        if ok and maybe_a is not None:
            if all(
                (n * (n + maybe_a)) % c == 0 and (n * (n + maybe_a)) // c == value
                for n, value in samples
            ):
                return f"(n*(n{maybe_a:+d}))/{c}"
    return None


def _infer_form(samples: list[tuple[int, int]]) -> str | None:
    return _fit_affine(samples) or _fit_linear_quotient(samples) or _fit_bilinear(samples)


def _make_name(modulus: int, residue: int, flavor: str, index: int) -> str:
    return f"m{modulus}_r{residue}_{flavor}{index}"


def _family_templates() -> list[Identity]:
    """Return deterministic built-in identity families.

    The ``odd4_family`` template handles ``n ≡ 5 (mod 8)``, which is a
    previously uncovered subset of the ``n ≡ 1 (mod 4)`` class.

    The ``odd4_mod12_r9`` template adds another odd-residue construction for
    ``n ≡ 9 (mod 12)`` (equivalently ``n ≡ 1 (mod 4)`` and ``n ≡ 0 (mod 3)``).
    """
    return [
        Identity(
            name="odd4_family_m8_r5",
            modulus=8,
            residues=[5],
            x_form="(n+3)/4",
            y_form="n*(n+3)/4",
            z_form="n*(n+3)/8",
            conditions=[],
            notes="family=odd4; symbolic",
        ),
        Identity(
            name="odd4_mod12_r9",
            modulus=12,
            residues=[9],
            x_form="(n+3)/4",
            y_form="n*(n+3)/6",
            z_form="n*(n+3)/6",
            conditions=[],
            notes="family=odd4; symbolic",
        ),
    ]


def mine_identities(
    certs_path: Path,
    out_path: Path,
    *,
    max_identities: int = 50,
) -> list[Identity]:
    """Mine deterministic residue-class identities from solved certificate data."""
    certs = _load_verified_certs(certs_path)
    groups: dict[tuple[int, int], list[Certificate]] = defaultdict(list)
    for cert in certs:
        for modulus in MODULI:
            groups[(modulus, cert.n % modulus)].append(cert)

    identities: list[Identity] = []
    seen: set[tuple[int, tuple[int, ...], str, str, str, tuple[str, ...]]] = set()

    for template in _family_templates():
        empirical = verify_identity(template, n_min=2, n_max=5000)
        if empirical["tested"] == 0 or empirical["failed"] > 0:
            continue
        if not verify_identity_symbolic(template):
            continue

        dedupe_key = (
            template.modulus,
            tuple(template.residues),
            template.x_form,
            template.y_form,
            template.z_form,
            tuple(template.conditions),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        identities.append(template)
        if len(identities) >= max_identities:
            break

    for modulus in MODULI:
        for residue in range(modulus):
            group = sorted(groups[(modulus, residue)], key=lambda item: item.n)
            if len(group) < 3:
                continue
            sampled = group[:6]
            x_form = _infer_form([(cert.n, cert.x) for cert in sampled])
            y_form = _infer_form([(cert.n, cert.y) for cert in sampled])
            z_form = _infer_form([(cert.n, cert.z) for cert in sampled])
            if not x_form or not y_form or not z_form:
                continue

            candidate = Identity(
                name=_make_name(modulus, residue, "template", len(identities) + 1),
                modulus=modulus,
                residues=[residue],
                x_form=x_form,
                y_form=y_form,
                z_form=z_form,
                conditions=[],
                notes="mined",
            )
            empirical = verify_identity(candidate, n_min=2, n_max=5000)
            if empirical["tested"] == 0 or empirical["failed"] > 0:
                continue

            symbolic_ok = verify_identity_symbolic(candidate)
            notes = "mined; symbolic" if symbolic_ok else "mined; empirical-only"
            candidate = Identity(
                name=_make_name(
                    modulus,
                    residue,
                    "affine" if "*n" in x_form and "(n*(" not in x_form else "template",
                    len(identities) + 1,
                ),
                modulus=modulus,
                residues=[residue],
                x_form=x_form,
                y_form=y_form,
                z_form=z_form,
                conditions=[],
                notes=notes,
            )
            dedupe_key = (
                candidate.modulus,
                tuple(candidate.residues),
                candidate.x_form,
                candidate.y_form,
                candidate.z_form,
                tuple(candidate.conditions),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            identities.append(candidate)
            if len(identities) >= max_identities:
                break
        if len(identities) >= max_identities:
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for identity in identities:
            handle.write(identity_to_jsonl(identity) + "\n")
    return identities
