# NASA-STD-5001B in Lean 4

A pipeline that takes a CAD part and a limit load and produces a Lean 4 certificate that the part does, or does not, satisfy the strength requirement of NASA-STD-5001B. Both the FEA simulation's computations and the safety-test computations are checked in Lean.

<p align="center">
  <img src="pipeline.svg" alt="Pipeline: CAD model → mesh → FEA simulation → structural analysis" width="650">
</p>

## Background

NASA's standards set the expectations for how the aerospace industry must design, test and manufacture hardware.

NASA-STD-5001B is NASA's standard for structural design, testing, and service-life requirements for aerospace hardware. It tells us the minimum loads (in terms of design factors and test factors) that parts must withstand to be considered valid.

For example, we might perform a structural analysis of a protoflight nose cone. Protoflight means we intend to use it in flight after the test. Among other things, the standard tells us to test for yield at a load of 1.25× the expected maximum load that will be experienced during flight.

## Why formalise it?

Formalising an engineering standard gives three things:

- **No ambiguity.** The same clauses can be re-implemented throughout a project, organisation, and tools. NASA's standards are used throughout the aerospace industry.
- **Requirements compose.** NASA often has hundreds of engineers working on the same project. They don't all speak to each other and they need to balance their separate design requirements. Formalisation provides a ground truth for those requirements.
- **An explicit boundary of assurance.** Formalisation forces us to specify the boundary of what is proved and what is assumed.

I've formalised the structural analysis tests as in NASA-STD-5001B and verified the correctness of the FEA computation. This is just one part of a much larger system, and so there are still untrusted inputs — e.g. the mesh, boundary conditions and material model still need to be verified and validated.

What formalisation does is make the boundary between what is assumed and what is verified explicit.

## Project

### 1. The NASA standard

I formalised the structural analysis tests in NASA-STD-5001B. The project focuses on §3.2 (Margin of Safety), Table 1 (§4.2.1, minimum design and test factors), and §4.2d:

> "The factored stresses shall not exceed material allowable stresses (yield and ultimate) under the expected temperature, pressure, and other operating conditions."

`NasaStd5001B/Meta.lean` proves properties of the standard itself, including its main correctness theorem:

```
MS ≥ 0  ⟺  factored stress ≤ allowable
```

We also show, for example, that the margin of safety is monotonic — lower stress or a stronger material never results in a lower margin of safety, and a larger design factor never results in a higher one. That monotonicity is what makes the pipeline sound: it can certify an *upper bound* on the stress rather than the stress itself, because passing at the bound implies passing at the true value.

### 2. The computation

The stress used in the structural analysis comes from a finite-element analysis (FEA) simulation. The exact physics solver we use is untrusted — the engine might change. We formally verify the correctness of the stress computation that is performed.

Lean assembles the stiffness system `Ku = f` in exact rational arithmetic. The solver (CalculiX) then proposes a solution `u`, and Lean proves that `u` satisfies the system Lean assembled, to within a tolerance ε. From that verified `u`, Lean computes the stress in every element and takes the maximum. That maximum is the value passed into the structural analysis tests.

By doing this, we split the inputs to the system into the trusted parts (the FEA computation and the structural analysis) and the untrusted parts (everything else — mesh quality, discretisation error, etc.).

Concretely, for the default run (800 N limit load, protoflight, 25×12×150 mm 6061-T6 cantilever):

| | |
|---|---|
| Discrete model | 224 nodes, 679 C3D4 elements |
| Equilibrium checked at | 211 free nodes, 2624 element incidences |
| Residual `‖Ku − f‖∞` | 2.1 × 10⁻⁶ N — certified ≤ 10⁻⁵ N |
| …as a fraction of the nodal load | 3.5 × 10⁻⁸ |
| Peak von Mises stress | bracketed in [129.1970, 129.1980] MPa |
| Certified at | 129.1980 MPa (upper bound) |
| MS_yield (DF 1.25) / MS_ult (DF 1.40) | +0.709 / +0.714 |
| Verdict | **compliant with §4.2d** |

Every theorem is closed by `decide +kernel`, so the Lean kernel evaluates the model itself. Nothing uses `native_decide`, which would ask the kernel to trust the compiler instead. `Scripts/Axioms.lean` prints what each certificate depends on, and it is `[propext, Classical.choice, Quot.sound]` throughout — the three standard axioms, and nothing else. CI fails the build if that ever stops being true.

### 3. What is assumed

The certificate is a statement about a *discrete model*: this mesh, these boundary conditions, this material. Everything below is an input to that model, not a consequence of it.

| Assumed input | Why it is outside the proof |
|---|---|
| **The mesh** | Generated by Gmsh and taken as given. Lean checks equilibrium on whatever mesh it is handed; it does not check that the mesh represents the CAD part. |
| **Discretisation error** | Linear tetrahedra are stiff in bending. On the default mesh the computed peak stress is about 35% below the Euler–Bernoulli value of 200 MPa, and it moves with mesh size. Each certificate reports this gap in its header. Bounding it is step 3 of the roadmap below. |
| **Boundary conditions** | The clamped face is fully fixed and the load is lumped equally onto the free-end nodes. Both are modelling choices; neither is derived from the part. |
| **Material model** | Isotropic linear elasticity, with E and ν as exact rationals. No plasticity, no temperature or pressure effects, so §4.2b is not addressed. |
| **Material allowables** | Fty = 276 MPa, Ftu = 310 MPa — typical handbook values for 6061-T6. §4.2c requires allowables derived per NASA-STD-6016 (MMPDS), which are generally lower. Substituting them is a one-line change; doing so honestly is not this repo's claim. |
| **The limit load** | §3.2 defines the limit load as the maximum anticipated load. Determining it is a loads analysis, not a strength check. |
| **The rest of the standard** | Only §3.2, Table 1 and §4.2d are encoded. §4.2a–c and §4.2e, detrimental yielding, and the test requirements of §4.1 are not. §4.2d is *necessary* for structural adequacy, not sufficient — see the note in `NASA-STD-5001B.md`. |

What *is* proved, given those inputs: the solver's displacement field really does solve the system Lean assembled, to a stated tolerance; that field's peak von Mises stress is at most the certified value; and at that value the factored stresses stay within the material allowables.

## What's next

This is just one part of a much larger system, and so there are still untrusted inputs: the mesh, boundary conditions and material model still need to be verified and validated. This is what the full process would look like:

1. **Formalise the standard and the certified computation** — what this repo is building.
2. **Formalise the meshing process.**
3. **Verify the bound on the error in the FEM output.** There is still an unformalised error between the FEA simulation and reality — the simulation uses a discretised approximation of the real design, and we should make that error formal.
4. **Formalise the design model.** A compositional formal language for the geometry and tolerances of a part, so that e.g. "detrimental yielding" (§3.2) can be decided against the part's own GD&T rather than asserted. I've already worked on formalising the tolerancing half in my own repo, `formal-gdt`.

I've written a short essay discussing this approach at greater length (forthcoming).

## Lean modules

| File | Contents |
|------|----------|
| `NasaStd5001B/Defs.lean` | §3.2 MS formula, §4.2.1 Table 1 factors, §4.2d compliance predicate |
| `NasaStd5001B/Meta.lean` | 15 theorems about the standard: 7 concrete (Table 1 values), 6 general (monotonicity, antitone, core correctness), 2 bridging a bound on stress² to the compliance predicate |
| `NasaStd5001B/Fem/Types.lean` | `Vec3`, `Elem`, `NodeCheck`, `Model`, and the integer scaling convention |
| `NasaStd5001B/Fem/Element.lean` | C3D4 shape-function gradients, strain, Hooke's law, von Mises, internal nodal forces |
| `NasaStd5001B/Fem/Assembly.lean` | Matrix-free residual `‖Ku − f‖∞` and peak-stress recovery |
| `NasaStd5001B/Fem/Test.lean` | The element formulation against hand-computed values: patch test, rigid-body motions, self-equilibrium, scale cancellation |
| `NasaStd5001B/Generated/BracketData.lean` | Auto-generated per run: the discrete model as exact integers |
| `NasaStd5001B/Generated/Bracket.lean` | Auto-generated per run: the certificate theorems |
| `Scripts/Axioms.lean` | Prints the axioms every certificate rests on |

All numeric factors are exact rationals (ℚ): 1.4 = 7/5, 1.25 = 5/4, 1.2 = 6/5, 1.05 = 21/20.

### Core correctness theorem

```lean
theorem margin_nonneg_iff {allowable limitStress df : ℚ}
    (hσ : 0 < limitStress) (hdf : 0 < df) :
    0 ≤ marginOfSafety allowable limitStress df ↔ limitStress * df ≤ allowable
```

### The certificate

```lean
theorem bracket_certificate :
    model.maxAbsResidual ≤ residualTol
  ∧ model.maxVonMisesSq ≤ sigmaBound ^ 2
  ∧ bracket.isCompliant
```

## Running it

```
$ python3 -m pipeline                      # 800 N limit load, protoflight
$ python3 -m pipeline --limit-load 2000    # overloaded bracket → non-compliant
$ python3 -m pipeline --approach prototype
$ python3 -m pipeline --mesh-size 6        # finer model, slower to check
```

On each run:

1. **CAD** — `build123d` constructs a 25×12×150 mm rectangular cantilever and exports STEP.
2. **Mesh** — Gmsh generates and optimises a C3D4 tetrahedral mesh. Node coordinates are snapped to whole micrometres, and the snapped mesh is what the solver is given, so Lean and CalculiX are talking about the same geometry rather than two that differ in the last few bits.
3. **FEA** — CalculiX solves the static problem. Its text output carries only seven significant figures, which by itself leaves a residual of order 1 N, so the pipeline computes the exact residual and has CalculiX solve `Kδ = −r` for the correction. One such pass takes the residual from ~1 N to ~10⁻⁶ N.
4. **Certificate** — `Generated/BracketData.lean` and `Generated/Bracket.lean` are written, with every quantity an exact integer or rational.
5. **`lake build`** — Lean's kernel checks the proof, then the axiom audit runs. Exit code 0 = compliant, 1 = non-compliant.

The default mesh is sized so the kernel check takes about two minutes. `--mesh-size` is the dial: checking time grows roughly linearly with element count. A coarser mesh does not make the certificate less true — it makes it a claim about a cruder model, and widens the gap to beam theory that each certificate reports.

### Dependencies

Lean:

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
lake exe cache get   # downloads prebuilt Mathlib oleans
lake build
```

The toolchain is pinned in `lean-toolchain` and Mathlib to an exact revision in `lakefile.lean`.

Python:

- [build123d](https://github.com/gumyr/build123d) — parametric CAD
- [gmsh](https://gmsh.info/) — meshing (`pip install gmsh`)
- [CalculiX](https://www.dhondt.de/) — FEA solver (bundled with [FreeCAD](https://www.freecad.org/), or install separately)

```bash
pip install build123d gmsh
# CalculiX: set CCX_PATH if not at /Applications/FreeCAD.app/Contents/Resources/bin/ccx
python3 -m pytest tests/      # exact-arithmetic FEM checks; needs no CAD or solver
```

## NASA-STD-5001B

NASA-STD-5001B is a public-domain US government document. Download it free from [standards.nasa.gov](https://standards.nasa.gov). The `NASA-STD-5001B.md` file in this repo contains verbatim excerpts of the sections being formalised, as a ground-truth reference.

## Structure

```
nasa5001b-lean/
  lakefile.lean              # Lake config; Mathlib pinned to an exact revision
  lean-toolchain             # Lean version pin
  NasaStd5001B.lean          # Root import
  NasaStd5001B/
    Defs.lean                # The standard encoded
    Meta.lean                # Properties of the standard
    Fem/                     # The finite-element model, in exact rationals
      Types.lean  Element.lean  Assembly.lean  Test.lean
    Generated/               # Pipeline output, re-generated on each run
      BracketData.lean  Bracket.lean
  Scripts/Axioms.lean        # Axiom audit
  pipeline/
    cad_model.py             # build123d bracket geometry
    fea.py                   # Gmsh + CalculiX + iterative refinement
    fem_reference.py         # Exact-rational mirror of the Lean element code
    generate_lean.py         # Discrete model → Lean source
    run.py                   # Orchestrator
  tests/                     # Analytic checks on the exact FEM reference
  NASA-STD-5001B.md          # Ground-truth quotes from the standard
```
