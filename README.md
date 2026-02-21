# strausforge

`strausforge` is a lightweight computational and symbolic Python toolkit for exploring the Erdős–Straus conjecture by verifying and searching identities of the form `4/n = 1/x + 1/y + 1/z` with exact rational arithmetic.

The project now includes a faster deterministic solver path and JSONL certificates for reproducible runs, basic coverage reporting, and simple benchmarking views.

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

Generate certificates for a range:

```bash
strausforge certify --start 2 --end 100 --out certs.jsonl
```

Print aggregate statistics from certificates:

```bash
strausforge stats --in certs.jsonl
```

### Certificate format

Each `certify` record is one JSON line with solver output and exact verification status.

Example JSONL line:

```json
{"elapsed_ms": 0.031, "method": "search_v1", "n": 17, "residue": {"n_mod_12": 5, "n_mod_24": 17, "n_mod_4": 1}, "verified": true, "x": 5, "y": 34, "z": 170}
```

Certificates are *proof-carrying* in the practical sense that each line carries concrete `(x, y, z)` values plus a `verified` bit from exact rational equality checking. This is not a formal proof assistant artifact.


## Identity Mining

An **identity** in `strausforge` is a residue-class lemma: a parametric triple `(x(n), y(n), z(n))` that proves
`4/n = 1/x + 1/y + 1/z` for values of `n` in selected congruence classes.

Mining is deterministic (not ML):
- load verified certificates,
- group by modulus/residue,
- fit small template families (affine, quotient-linear, bilinear),
- apply built-in family templates (including `odd4_family` for `n ≡ 5 (mod 8)` and `odd4_mod12_r9` for `n ≡ 9 (mod 12)`, both within `n ≡ 1 (mod 4)`),
- verify candidates empirically with exact rationals,
- then attempt symbolic verification with SymPy.

Run mining:

```bash
strausforge mine --in certs.jsonl --out data/identities.jsonl --max-identities 50
```

Check which identity applies at one `n`:

```bash
strausforge id-check --identity data/identities.jsonl --n 35
```

Empirically verify all stored identities over a range:

```bash
strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500
```


Coverage check example:

```bash
strausforge id-targets --identity data/identities.jsonl --modulus 48
```


## Autopilot Loop

Use the loop command to run one deterministic end-to-end mining iteration:
1. compute uncovered residues at a chosen modulus,
2. generate deterministic target `n` values,
3. certify those examples,
4. mine identities from those certificates,
5. append newly discovered identities (including any built-in family templates that verify),
6. recompute and print coverage delta.

Example:

```bash
strausforge loop --identity data/identities.jsonl --modulus 24 --max-targets 4 --max-per-target 3 --max-new-identities 10
```

What to expect:
- The command prints a before/after coverage summary and a delta line.
- Certificates are written to `data/certs_targets_m<M>.jsonl`.
- Some runs may add zero identities (exit code 1 in that case); increase range pressure via larger `--max-targets` and `--max-per-target`.

## Scope

This project provides a clean foundation for computational experimentation and symbolic verification around Erdős–Straus instances. It does **not** claim a proof or disproof of the conjecture.
