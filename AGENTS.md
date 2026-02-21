# AGENTS.md

## Setup

```bash
python -m pip install -e .
python -m pip install -e .[dev]
```

## Development commands

- Test: `pytest -q`
- Lint: `ruff check .`
- Format: `ruff format .`

## Contribution rules

- Keep code deterministic and reproducible.
- Add tests for every feature and bug fix.
- Run formatting, lint, and tests before committing.
- Prefer small, focused pull requests.
