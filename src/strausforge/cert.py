"""Certificate utilities for machine-checkable Erdős–Straus search outputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .erdos_straus import check_identity


@dataclass(slots=True)
class Certificate:
    """Serializable result record for one ``n``.

    A certificate is *proof-carrying* in a practical sense: it includes candidate
    denominators and a verification bit produced with exact arithmetic.
    """

    n: int
    x: int
    y: int
    z: int
    method: str
    elapsed_ms: float
    verified: bool
    residue: dict[str, int]


def make_certificate(
    n: int,
    x: int,
    y: int,
    z: int,
    method: str,
    elapsed_ms: float,
) -> Certificate:
    """Create a certificate with deterministic residue metadata."""
    verified = x > 0 and y > 0 and z > 0 and check_identity(n=n, x=x, y=y, z=z)
    residue = {
        "n_mod_4": n % 4,
        "n_mod_12": n % 12,
        "n_mod_24": n % 24,
    }
    return Certificate(
        n=n,
        x=x,
        y=y,
        z=z,
        method=method,
        elapsed_ms=elapsed_ms,
        verified=verified,
        residue=residue,
    )


def to_jsonl(cert: Certificate) -> str:
    """Serialize a :class:`Certificate` as one JSONL line."""
    return json.dumps(asdict(cert), sort_keys=True)


def from_jsonl(line: str) -> Certificate:
    """Parse one JSONL line into a :class:`Certificate`."""
    payload = json.loads(line)
    return Certificate(
        n=int(payload["n"]),
        x=int(payload["x"]),
        y=int(payload["y"]),
        z=int(payload["z"]),
        method=str(payload["method"]),
        elapsed_ms=float(payload["elapsed_ms"]),
        verified=bool(payload["verified"]),
        residue={k: int(v) for k, v in dict(payload["residue"]).items()},
    )
