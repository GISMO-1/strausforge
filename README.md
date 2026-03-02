![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Field](https://img.shields.io/badge/field-Experimental%20Number%20Theory-purple)
![Results](https://img.shields.io/badge/results-reproducible-brightgreen)
![Deterministic](https://img.shields.io/badge/pipeline-deterministic-brightgreen)
![Range](https://img.shields.io/badge/tested%20range-up%20to%2030M%20(windowed)-orange)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18800225.svg)](https://doi.org/10.5281/zenodo.18800225)
![Interface](https://img.shields.io/badge/interface-CLI%20%7C%20Streamlit-blueviolet)

# strausforge

**Strausforge** is an experimental computational laboratory for the **Erdős–Straus conjecture**.

The conjecture asks whether every integer `n ≥ 2` admits a decomposition

```

4/n = 1/x + 1/y + 1/z

```

in positive integers `x, y, z`.

Rather than relying purely on brute-force search, this project studies the conjecture through **discovering, verifying, and measuring residue-class identities** — explicit parametric constructions that solve infinite families of integers at once.

The guiding idea is simple:

> turn numerical verification into structural evidence.

Strausforge treats solutions not as isolated computations, but as mathematical objects that can be mined, classified, stress-tested, and reproduced.

---

## Current experimental coverage (v0.3.x)

Deterministic hardness runs have been executed in 2M windows through:

```

n ≤ 30,000,000   (windowed runs)

````

Observed structural behavior:

- Escalation pressure is sparse.
- Expanded cases concentrate overwhelmingly in residues  
  **1 and 25 mod 48**.
- A large majority of expanded cases are **prime inputs**.
- The `prime-or-square-window` heuristic dramatically reduces expanded exports relative to `--proc-heuristic off`.

These results convert large computational ranges into analyzable structural data.

---

## What this project actually does

Strausforge combines three perspectives.

### 1. Exact computation
- deterministic search for solutions
- exact rational verification
- reproducible certificate generation
- fully auditable solver paths

### 2. Identity discovery
- detects congruence-class structure
- fits parametric solution families
- mines residue-class lemmas from verified data
- performs empirical and symbolic validation

### 3. Experimental number theory
- measures where identities succeed or struggle
- studies structurally “hard” integers
- profiles solver pressure across ranges of `n`
- visualizes escalation / expansion behavior (often concentrated on primes and squares)

The system functions as a **computational microscope** for the Erdős–Straus equation.

---

## Reproducibility contract

Strausforge enforces the following guarantees:

- All solver paths are deterministic.
- All certificates include exact rational verification.
- Hardness metrics are derived from reproducible pipeline stages.
- Expanded-case JSONL exports can be summarized without loading entire files in memory.
- CLI and GUI share the same evaluation engine.

Re-running the same command with the same identity file produces identical outputs.

---

## Installation

Core CLI install:

```bash
python -m pip install -e .
````

Developer install (tests + lint):

```bash
python -m pip install -e '.[dev]'
```

GUI install:

```bash
pip install -e ".[gui]"
```

---

## Basic usage

```bash
python -m strausforge --help
```

Hardness run example:

```bash
strausforge hardness \
  --identity data/identities.jsonl \
  --n-min 2 \
  --n-max 2000000 \
  --bin-size 5000 \
  --out hardness.csv \
  --progress
```

Summarize expanded exports:

```bash
strausforge expanded-stats --in expanded.jsonl --mod 48 --top 20
```

---

## Identity mining

Mine identities from certified solutions:

```bash
strausforge mine \
  --in certs.jsonl \
  --out data/identities.jsonl \
  --max-identities 50
```

---

## Procedural heuristics

Example:

```bash
--proc-heuristic prime-or-square-window
```

Empirically, difficult regions correlate strongly with:

* primes
* perfect squares
* near-square arithmetic structure

The heuristic widens evaluation windows precisely where structural pressure is expected.

---

## What this project is (and is not)

Strausforge is:

* a reproducible experimental framework
* a residue-class identity explorer
* a computational number theory laboratory

Strausforge is **not**:

* a claimed proof of the Erdős–Straus conjecture
* a heuristic black box
* a machine learning system

All results remain deterministic and auditable.

---

## Philosophy

Large conjectures often resist direct proof but expose structural regularities under systematic measurement.

Strausforge treats computation as structured evidence, not as brute-force confirmation.

The project is released openly so mathematicians and experimenters can extend its structural exploration further.
