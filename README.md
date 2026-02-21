# strausforge

`strausforge` is a lightweight computational and symbolic Python toolkit for exploring the Erdős–Straus conjecture by verifying and searching identities of the form `4/n = 1/x + 1/y + 1/z` with exact rational arithmetic and a practical baseline heuristic search.

## Install

```bash
python -m pip install -e .
```

## Usage

Check a specific identity:

```bash
strausforge check --n 5 --x 2 --y 4 --z 20
```

Sample output:

```text
PASS
```

Search a single value:

```bash
strausforge search --n 17
```

Search a range with JSON lines output:

```bash
strausforge search --start 2 --end 10 --json
```

Sample output:

```text
{"found": true, "n": 2, "x": 1, "y": 2, "z": 2}
{"found": true, "n": 3, "x": 1, "y": 4, "z": 12}
```

## Scope

This project provides a clean foundation for computational experimentation and symbolic verification around Erdős–Straus instances. It does **not** claim a proof or disproof of the conjecture.
