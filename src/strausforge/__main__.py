"""Module entrypoint for ``python -m strausforge``.

Examples:
    Run the CLI help via module execution::

        python -m strausforge --help
"""

from __future__ import annotations

from strausforge.cli import app


def main() -> None:
    """Execute the Typer CLI application."""
    app()


if __name__ == "__main__":
    main()
