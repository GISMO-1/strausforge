"""Data-driven identity fitting for difficult residue classes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import gcd
from multiprocessing import Process, Queue
from pathlib import Path

from .erdos_straus import check_identity
from .identities import Identity, identity_to_jsonl, verify_identity, verify_identity_symbolic


@dataclass(frozen=True, slots=True)
class SolutionSample:
    """One solved ``4/n`` decomposition sample."""

    n: int
    x: int
    y: int
    z: int


@dataclass(slots=True)
class TemplateCandidate:
    """Parametric template candidate before identity serialization."""

    a: int
    d: int
    b: int
    c: int
    e: int
    f: int
    score: int


def _load_solution_samples(in_file: Path) -> list[SolutionSample]:
    samples: list[SolutionSample] = []
    with in_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            n = int(payload["n"])
            x = int(payload.get("x", 0))
            y = int(payload.get("y", 0))
            z = int(payload.get("z", 0))
            found = bool(payload.get("found", payload.get("verified", False)))
            if not found or min(x, y, z) <= 0:
                continue
            samples.append(SolutionSample(n=n, x=x, y=y, z=z))
    return sorted(samples, key=lambda item: item.n)


def _fit_x_candidates(
    samples: list[SolutionSample], *, max_candidates: int
) -> list[tuple[int, int, int]]:
    ranked: list[tuple[int, int, int]] = []
    for a in range(-256, 257):
        for d in range(2, 129):
            if any((sample.n + a) % d != 0 for sample in samples):
                continue
            score = sum(1 for sample in samples if (sample.n + a) // d == sample.x)
            if score == 0:
                continue
            ranked.append((score, a, d))
    ranked.sort(key=lambda item: (-item[0], item[2], item[1]))
    return ranked[:max_candidates]


def _best_bilinear_params(
    samples: list[SolutionSample], *, value_name: str, max_candidates: int
) -> list[tuple[int, int, int]]:
    ranked: list[tuple[int, int, int]] = []
    for denom in range(2, 385):
        frequencies: dict[int, int] = {}
        for sample in samples:
            value = getattr(sample, value_name)
            numerator = value * denom - (sample.n * sample.n)
            if numerator % sample.n != 0:
                continue
            offset = numerator // sample.n
            if -512 <= offset <= 512:
                frequencies[offset] = frequencies.get(offset, 0) + 1

        for offset, score in frequencies.items():
            if score > 0:
                ranked.append((score, offset, denom))

    ranked.sort(key=lambda item: (-item[0], item[2], item[1]))
    return ranked[:max_candidates]


def _fit_template_candidates(
    samples: list[SolutionSample], *, max_identities: int
) -> list[TemplateCandidate]:
    x_candidates = _fit_x_candidates(samples, max_candidates=max(12, max_identities * 3))
    y_candidates = _best_bilinear_params(samples, value_name="y", max_candidates=20)
    z_candidates = _best_bilinear_params(samples, value_name="z", max_candidates=20)

    candidates: list[TemplateCandidate] = []
    seen: set[tuple[int, int, int, int, int, int]] = set()
    for _, a, d in x_candidates:
        for _, b, c in y_candidates:
            for _, e, f in z_candidates:
                key = (a, d, b, c, e, f)
                if key in seen:
                    continue
                seen.add(key)
                score = sum(
                    1
                    for sample in samples
                    if (sample.n + a) % d == 0
                    and (sample.n * (sample.n + b)) % c == 0
                    and (sample.n * (sample.n + e)) % f == 0
                    and (sample.n + a) // d == sample.x
                    and (sample.n * (sample.n + b)) // c == sample.y
                    and (sample.n * (sample.n + e)) // f == sample.z
                )
                candidates.append(TemplateCandidate(a=a, d=d, b=b, c=c, e=e, f=f, score=score))

    candidates.sort(
        key=lambda cand: (
            -cand.score,
            cand.d,
            cand.c,
            cand.f,
            cand.a,
            cand.b,
            cand.e,
        )
    )
    return candidates[: max(40, max_identities * 8)]


def _symbolic_worker(identity: Identity, queue: Queue) -> None:
    queue.put(verify_identity_symbolic(identity))


def _verify_symbolic_with_timeout(identity: Identity, timeout_seconds: float) -> bool | None:
    queue: Queue = Queue()
    process = Process(target=_symbolic_worker, args=(identity, queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return None
    if queue.empty():
        return False
    return bool(queue.get())


def _infer_condition(values: list[int], modulus: int) -> tuple[int, int] | None:
    if len(values) < 2:
        return None
    step = 0
    for left, right in zip(values, values[1:], strict=True):
        diff = right - left
        step = diff if step == 0 else gcd(step, diff)
    if step == 0:
        return None
    condition_modulus = max(modulus, step)
    condition_residue = values[0] % condition_modulus
    return (condition_modulus, condition_residue)


def _candidate_identity(
    candidate: TemplateCandidate, modulus: int, residue: int, idx: int
) -> Identity:
    return Identity(
        name=f"fit_m{modulus}_r{residue}_v{idx}",
        modulus=modulus,
        residues=[residue],
        x_form=f"(n{candidate.a:+d})/{candidate.d}",
        y_form=f"n*(n{candidate.b:+d})/{candidate.c}",
        z_form=f"n*(n{candidate.e:+d})/{candidate.f}",
        conditions=[],
        notes=f"fit; sample_score={candidate.score}",
    )


def fit_identities(
    in_file: Path,
    out_file: Path,
    *,
    modulus: int,
    residue: int,
    max_identities: int,
) -> list[Identity]:
    """Fit and verify deterministic identities from solved sample JSONL.

    Examples:
        strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 1 \
            --out data/identities_fit.jsonl
        strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 25 \
            --out data/identities_fit.jsonl --max-identities 5
    """
    if modulus <= 0:
        raise ValueError("modulus must be positive")

    target_residue = residue % modulus
    samples = [
        sample for sample in _load_solution_samples(in_file) if sample.n % modulus == target_residue
    ]
    if len(samples) < 8:
        return []

    template_candidates = _fit_template_candidates(samples, max_identities=max_identities)

    sample_ns: list[int] = []
    value = target_residue if target_residue > 0 else modulus
    while value < 2:
        value += modulus
    while len(sample_ns) < 240:
        sample_ns.append(value)
        value += modulus

    identities: list[Identity] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for index, candidate in enumerate(template_candidates, start=1):
        identity = _candidate_identity(
            candidate, modulus=modulus, residue=target_residue, idx=index
        )

        passing: list[int] = []
        for n_value in sample_ns:
            x_num = n_value + candidate.a
            y_num = n_value * (n_value + candidate.b)
            z_num = n_value * (n_value + candidate.e)
            if x_num % candidate.d != 0 or y_num % candidate.c != 0 or z_num % candidate.f != 0:
                continue
            x_value = x_num // candidate.d
            y_value = y_num // candidate.c
            z_value = z_num // candidate.f
            if min(x_value, y_value, z_value) <= 0:
                continue
            if check_identity(n=n_value, x=x_value, y=y_value, z=z_value):
                passing.append(n_value)

        if len(passing) < 100:
            continue

        if len(passing) < 200:
            inferred = _infer_condition(passing, modulus=modulus)
            if inferred is None:
                continue
            cond_modulus, cond_residue = inferred
            identity.conditions = [f"n % {cond_modulus} == {cond_residue}"]

        empirical = verify_identity(identity, n_min=2, n_max=max(sample_ns))
        if empirical["tested"] < 100 or empirical["failed"] > 0:
            continue

        symbolic = _verify_symbolic_with_timeout(identity, timeout_seconds=2.0)
        if symbolic is True:
            identity.notes = f"fit; symbolic; sample_score={candidate.score}"
        elif symbolic is None:
            identity.notes = (
                f"fit; empirical-only; symbolic_timeout; sample_score={candidate.score}"
            )
        else:
            identity.notes = f"fit; empirical-only; sample_score={candidate.score}"

        dedupe = (
            identity.x_form,
            identity.y_form,
            identity.z_form,
            tuple(identity.conditions),
        )
        if dedupe in seen:
            continue
        seen.add(dedupe)
        identities.append(identity)
        if len(identities) >= max_identities:
            break

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as handle:
        for identity in identities:
            handle.write(identity_to_jsonl(identity) + "\n")
    return identities
