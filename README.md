![Release](https://img.shields.io/github/v/release/GISMO-1/strausforge)
![License](https://img.shields.io/github/license/GISMO-1/strausforge)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Reproducible](https://img.shields.io/badge/results-reproducible-brightgreen)
![Experimental Number Theory](https://img.shields.io/badge/field-Experimental%20Number%20Theory-purple)
![Range Tested](https://img.shields.io/badge/tested_range-n≤2,000,000-orange)

# strausforge

**Strausforge** is an experimental computational laboratory for the **Erdős–Straus conjecture**.

The conjecture asks whether every integer `n ≥ 2` admits a decomposition

    4/n = 1/x + 1/y + 1/z

in positive integers `x, y, z`.

Rather than relying purely on brute-force search, this project studies the conjecture through **discovering, verifying, and measuring residue-class identities** — explicit parametric constructions that solve infinite families of integers at once.

The guiding idea is simple:

> turn numerical verification into structural evidence.

Strausforge treats solutions not as isolated computations, but as mathematical objects that can be mined, classified, stress-tested, and reproduced.


---

## What this project actually does

Strausforge combines three perspectives.

### 1. Exact computation
- deterministic search for solutions
- exact rational verification
- reproducible certificate generation
- solver paths that remain fully auditable

### 2. Identity discovery
- detects congruence-class structure
- fits parametric solution families
- mines residue-class lemmas from verified data
- performs empirical and symbolic validation

### 3. Experimental number theory
- measures where identities succeed or struggle
- studies structurally “hard” integers
- profiles solver pressure across ranges of `n`
- visualizes expansion behavior (often concentrated on primes and squares)

The system effectively acts as a **computational microscope** for the Erdős–Straus equation.


---

## Installation

```bash
python -m pip install -e .
````

---

## Basic usage

### Check a specific decomposition

```bash
strausforge check --n 5 --x 2 --y 4 --z 20
```

Output:

```
PASS
```

---

### Search for a solution

Single value:

```bash
strausforge search --n 17
```

Range search with JSON output:

```bash
strausforge search --start 2 --end 10 --json
```

---

### Generate verification certificates

```bash
strausforge certify --start 2 --end 100 --out certs.jsonl
```

Each line records a verified solution together with solver metadata.

Example record:

```json
{"elapsed_ms":0.031,"method":"search_v1","n":17,"verified":true,"x":5,"y":34,"z":170}
```

Certificates are **proof-carrying in a practical computational sense**:
every record includes explicit `(x, y, z)` values validated by exact rational equality.

---

## Identity mining

An **identity** in strausforge is a residue-class lemma — a parametric construction

```
x(n), y(n), z(n)
```

that proves

```
4/n = 1/x + 1/y + 1/z
```

for infinitely many integers `n`.

Mining proceeds deterministically:

1. load verified certificates
2. group by modulus and residue class
3. fit small parametric templates
4. test candidate families empirically
5. attempt symbolic verification
6. store validated identities

Run mining:

```bash
strausforge mine --in certs.jsonl --out data/identities.jsonl --max-identities 50
```

---

### Data-driven fitting for difficult residues

```bash
strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 1 --out data/identities_fit.jsonl
strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 25 --out data/identities_fit.jsonl
```

These procedural identities target regions where classical templates weaken.

---

## Identity verification

Check which identity applies:

```bash
strausforge id-check --identity data/identities.jsonl --n 35
```

Verify identities across a range:

```bash
strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500000
```

Coverage across congruence classes:

```bash
strausforge id-targets --identity data/identities.jsonl --modulus 48
```

---

## Procedural heuristics

Strausforge includes deterministic evaluation heuristics that reduce search expansion pressure.

Example:

```bash
--proc-heuristic prime-or-square-window
```

Empirically, expanded evaluation cases concentrate heavily on:

* primes
* perfect squares
* near-square structures

The heuristic widens initial evaluation windows exactly where arithmetic structure predicts difficulty.

---

## Hardness analysis

Strausforge can measure where identities require expanded procedural evaluation.

Export hardness statistics:

```bash
strausforge hardness \
  --identity data/identities.jsonl \
  --n-min 2 \
  --n-max 2000000 \
  --bin-size 5000 \
  --out hardness.csv \
  --plot hardness.png
```

Typical observations:

* most integers resolve immediately via identities,
* expansion pressure forms sparse spikes,
* difficult regions correlate strongly with prime and square inputs.

This converts large computational runs into analyzable experimental data.

---

## Autopilot discovery loop

A deterministic end-to-end exploration cycle:

```bash
strausforge loop \
  --identity data/identities.jsonl \
  --modulus 24 \
  --max-targets 4 \
  --max-per-target 3 \
  --max-new-identities 10 \
  --enable-fit-fallback
```

The loop:

1. finds uncovered residue classes
2. generates targets
3. certifies examples
4. mines identities
5. updates coverage
6. reports structural progress

Some iterations intentionally discover nothing — negative results are informative.

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

Large conjectures often resist direct proof but reveal structure under measurement.

Strausforge explores a simple question:

> How much of the Erdős–Straus conjecture can be explained by explicit arithmetic structure rather than brute force?

The project is released openly so mathematicians, experimenters, and curious builders can push that boundary further.
