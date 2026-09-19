# Formally Verified Structural Compliance: NASA-STD-5001B in Lean 4

A proof-of-concept that connects a real FEA pipeline to a Lean 4 compliance certificate, formalising the structural design factors of safety from NASA-STD-5001B ("Structural Design and Test Factors of Safety for Spaceflight Hardware", 2014).

```
build123d CAD  →  Gmsh mesh  →  CalculiX FEA  →  Lean 4 certificate
      STEP           C3D4              σ_max          lake build ✓
```

## What it does

The pipeline takes a cantilever bracket under a user-specified limit load and produces a machine-checked proof that the design either complies or does not comply with §4.2d of NASA-STD-5001B.

```
$ python3 -m pipeline                      # 800 N limit load, protoflight
$ python3 -m pipeline --limit-load 2000    # overloaded bracket
$ python3 -m pipeline --approach prototype
```

On each run:
1. **CAD** — `build123d` constructs a 25×12×150 mm rectangular cantilever and exports STEP.
2. **Mesh** — Gmsh generates a linear tetrahedral (C3D4) mesh.
3. **FEA** — CalculiX solves the static problem; max von Mises stress is extracted.
4. **Conservative bound** — the float result is rounded *up* to the nearest 0.001 MPa (`Fraction(ceil(σ × 1000), 1000)`), so the formal proof is conservative.
5. **Lean certificate** — `NasaStd5001B/Generated/Bracket.lean` is written with the exact rational stress value and either `bracket_compliant` or `bracket_noncompliant` as a theorem.
6. **`lake build`** — Lean's type-checker machine-checks the proof. Exit code 0 = compliant, 1 = non-compliant.

## Lean modules

| File | Contents |
|------|----------|
| `NasaStd5001B/Defs.lean` | §3.2 MS formula, §4.2.1 Table 1 factors, §4.2d compliance predicate (~100 lines) |
| `NasaStd5001B/Meta.lean` | 14 theorems about the standard: 7 concrete (Table 1 values) + 7 general (monotonicity, antitone, core correctness) (~150 lines) |
| `NasaStd5001B/Generated/Bracket.lean` | Auto-generated per run; concrete compliance or noncompliance proof (~55 lines) |

All numeric factors are exact rationals (ℚ): 1.4 = 7/5, 1.25 = 5/4, 1.2 = 6/5, 1.05 = 21/20. Decidable ℚ arithmetic means all concrete proofs close by `native_decide`.

### Key theorem

```lean
-- Core correctness theorem: the MS formula faithfully implements §4.2d
theorem margin_nonneg_iff {allowable limitStress df : ℚ}
    (hσ : 0 < limitStress) (hdf : 0 < df) :
    0 ≤ marginOfSafety allowable limitStress df ↔ limitStress * df ≤ allowable
```

### Trust boundary

Lean verifies the arithmetic given `σ_max`. Correctness of the FEA model (mesh quality, boundary conditions, solver convergence) is established separately by comparison with beam theory σ = 6FL/bh² — the pipeline checks that FEA and beam theory agree within 30%.

## Dependencies

### Lean

- [Lean 4](https://leanprover.github.io/) via [elan](https://github.com/leanprover/elan) — version pinned in `lean-toolchain`
- [Mathlib4](https://github.com/leanprover-community/mathlib4)

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
lake exe cache get   # downloads prebuilt Mathlib oleans (~5 min)
lake build
```

### Python

- [build123d](https://github.com/gumyr/build123d) — parametric CAD
- [gmsh](https://gmsh.info/) — meshing (`pip install gmsh`)
- [CalculiX](https://www.dhondt.de/) — FEA solver (bundled with [FreeCAD](https://www.freecad.org/), or install separately)

```bash
pip install build123d gmsh
# CalculiX: set CCX_PATH if not at /Applications/FreeCAD.app/Contents/Resources/bin/ccx
```

## NASA-STD-5001B

NASA-STD-5001B is a public-domain US government document. Download it free from [standards.nasa.gov](https://standards.nasa.gov). The `NASA-STD-5001B.md` file in this repo contains verbatim excerpts of the sections being formalised, as a ground-truth reference.

## Structure

```
lean-with-sims/
  lakefile.lean              # Lake project config + Mathlib dependency
  lean-toolchain             # Lean version pin
  NasaStd5001B.lean          # Root import
  NasaStd5001B/
    Defs.lean                # The standard encoded
    Meta.lean                # Properties of the standard
    Generated/
      Bracket.lean           # Pipeline output (re-generated on each run)
  pipeline/
    cad_model.py             # build123d bracket geometry
    fea.py                   # Gmsh + CalculiX + von Mises extraction
    generate_lean.py         # FEA results → Lean source
    run.py                   # Orchestrator
  NASA-STD-5001B.md          # Ground-truth quotes from the standard
```

## Background

This project is part of ongoing research into formalising engineering standards and integrating proof assistants with physical simulation tools. The approach is described in an accompanying essay (forthcoming).

The sibling project [`cadcontracts`](https://github.com/oliverpryce/cadcontracts) implements Westman & Nyberg's assume-guarantee contract theory for CAD/simulation pipelines. This project provides the formally verified compliance leaf that plugs into that framework.
