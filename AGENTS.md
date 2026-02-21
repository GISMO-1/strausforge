AGENTS.md

Environment Setup (always run in this order)

python -m pip install -e ".[dev]"

Do not run tests or linters before installing the package in editable mode.


---

Required Quality Gates (must pass before commit)

ruff format .
ruff check .
pytest -q

If any command fails, fix issues before committing.


---

Project Principles

Deterministic behavior only. No randomness unless explicitly seeded.

Use exact rational arithmetic (fractions.Fraction) for all identity checks.

All new public functions must include:

Type hints

Docstrings with usage examples (for CLI commands)

Tests covering normal and edge cases


Avoid hidden global state.

Avoid unnecessary dependencies.



---

Solver Rules

Never sacrifice correctness for speed.

Any optimization must preserve exact verification via check_identity.

New heuristics must include regression tests against small ranges (e.g., n=2..200).



---

Identity & Mining Rules

Do not store identities unless:

Empirically verified on a bounded range, AND

Symbolically verified when feasible.


Clearly label identities as:

"symbolic"

"empirical"


Mining must be deterministic given the same input certificates.



---

CLI Rules

CLI commands must:

Have clear help text

Return proper exit codes

Support JSON output when appropriate




---

Pull Request Discipline

Prefer small, focused PRs.

Do not refactor unrelated code in feature branches.

Do not remove tests unless replacing with stronger ones.
