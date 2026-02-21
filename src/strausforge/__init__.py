"""strausforge package."""

from .cert import Certificate, from_jsonl, make_certificate, to_jsonl
from .erdos_straus import check_identity, find_solution, find_solution_fast

__all__ = [
    "Certificate",
    "check_identity",
    "find_solution",
    "find_solution_fast",
    "from_jsonl",
    "make_certificate",
    "to_jsonl",
]
__version__ = "0.1.0"
