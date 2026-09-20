"""
pipeline/generate_lean.py

Emit the generated Lean certificate from an FEA run.

Two files are written:

  NasaStd5001B/Generated/BracketData.lean
  NasaStd5001B/Generated/Bracket.lean

The generator chooses *which* statement to make, the tolerance ε and the stress bound σ, 
but Lean recomputes both quantities from the model and rejects the file if either claim is false.  
A bug in this generator would produce a certificate that does not build.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path

from . import fem_reference as fr
from .cad_model import BracketGeometry, Material
from .fea import COORD_SCALE, DISP_SCALE, FEAResult

#: Table 1 (§4.2.1) design factors, as exact rationals.
DESIGN_FACTORS = {
    "prototype":   {"yield": Fraction(1), "ultimate": Fraction(7, 5)},
    "protoflight": {"yield": Fraction(5, 4), "ultimate": Fraction(7, 5)},
}


@dataclass(frozen=True)
class GenerateResult:
    """What the generated certificate claims, for the pipeline's report."""
    compliant: bool
    sigma_bound: Fraction        # σ used in the certificate, MPa
    sigma_lo: Fraction           # bracket on the true discrete peak stress
    sigma_hi: Fraction
    residual: Fraction           # exact ‖K u − f‖_∞, N
    epsilon: Fraction            # the tolerance actually stated, N
    ms_yield: Fraction
    ms_ult: Fraction
    n_checked_nodes: int
    n_incidences: int


def _q(f: Fraction) -> str:
    """Format an exact rational as a Lean ℚ literal."""
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"

def _v3(v) -> str:
    return f"⟨{v[0]},{v[1]},{v[2]}⟩"


def _v3q(v) -> str:
    return f"⟨{_q(v[0])},{_q(v[1])},{_q(v[2])}⟩"


def _margin(allowable: Fraction, sigma: Fraction, df: Fraction) -> Fraction:
    return allowable / (sigma * df) - 1


def _compliant_at(sigma: Fraction, mat: Material, approach: str) -> bool:
    df = DESIGN_FACTORS[approach]
    return (sigma > 0
            and _margin(mat.Fty, sigma, df["yield"]) >= 0
            and _margin(mat.Ftu, sigma, df["ultimate"]) >= 0)


def _choose_bound(q: Fraction, mat: Material, approach: str) -> tuple[Fraction, Fraction, Fraction, bool]:
    """Pick the rational stress the certificate will be stated at.

    Returns `(sigma_bound, sigma_lo, sigma_hi, compliant)`.

    √q is irrational in general, so the certificate is stated at a rational
    bracket around it.  To claim compliance we use the *upper* bound, which is
    conservative, to claim non-compliance we use the *lower* bound, which is
    equally conservative in the other direction.  If the two verdicts differ
    the design sits within one grid step of the §4.2d boundary, so we refine
    the grid until they agree.
    """
    grid = 1000
    while True:
        lo, hi = fr.stress_bounds(q, grid)
        if _compliant_at(hi, mat, approach):
            return hi, lo, hi, True
        if not _compliant_at(lo, mat, approach):
            return lo, lo, hi, False
        grid *= 1000
        if grid > 10 ** 15:
            raise RuntimeError(
                "Cannot decide compliance: the peak stress lies within "
                f"1e-15 MPa of the §4.2d limit for {approach}.")


def generate(geom: BracketGeometry, mat: Material, approach: str,
             limit_load_n: Fraction, fea: FEAResult,
             data_path: Path, thm_path: Path) -> GenerateResult:
    """Write both generated Lean files, return what was claimed."""
    lame = fr.lame_from(mat.E, mat.nu)
    model = fea.to_model(lame)
    evals = model.eval_all()

    residual = fr.max_abs_residual(model, evals)
    epsilon = fr.choose_epsilon(residual)
    q = fr.max_von_mises_sq(model, evals)
    sigma_bound, sigma_lo, sigma_hi, compliant = _choose_bound(q, mat, approach)

    df = DESIGN_FACTORS[approach]
    ms_yield = _margin(mat.Fty, sigma_bound, df["yield"])
    ms_ult = _margin(mat.Ftu, sigma_bound, df["ultimate"])

    incidence = model.incidence()
    checked = [n for n in fea.free_nodes if incidence[n]]
    n_incid = sum(len(incidence[n]) for n in checked)

    eids = sorted(fea.elements)
    slot = {eid: i for i, eid in enumerate(eids)}

    _write_data(data_path, geom, mat, lame, fea, checked, incidence, eids, slot)
    _write_theorems(thm_path, geom, mat, approach, limit_load_n, fea, lame,
                    residual, epsilon, q, sigma_bound, sigma_lo, sigma_hi,
                    compliant, ms_yield, ms_ult, len(checked), n_incid)

    return GenerateResult(
        compliant=compliant, sigma_bound=sigma_bound,
        sigma_lo=sigma_lo, sigma_hi=sigma_hi,
        residual=residual, epsilon=epsilon,
        ms_yield=ms_yield, ms_ult=ms_ult,
        n_checked_nodes=len(checked), n_incidences=n_incid)


# ---------------------------------------------------------------------------
# The data file
# ---------------------------------------------------------------------------

def _write_data(path: Path, geom: BracketGeometry, mat: Material, lame,
                fea: FEAResult, checked: list[int],
                incidence: dict[int, list[tuple[int, int]]],
                eids: list[int], slot: dict[int, int]) -> None:
    L: list[str] = [
        "/-",
        "  NasaStd5001B.Generated.BracketData",
        f"  Auto-generated by pipeline/generate_lean.py on {date.today()}.",
        "  DO NOT EDIT, re-run the pipeline to regenerate.",
        "",
        "  The discrete model: node coordinates in micrometres and the solver's",
        "  proposed displacements in picometres, both as exact integers, so that",
        f"  the scales ({_q(COORD_SCALE)} mm and {_q(DISP_SCALE)} mm) are applied",
        "  by `Fem.Element` rather than baked into the literals.",
        "",
        f"  Mesh     : {fea.n_nodes} nodes, {fea.n_elements} C3D4 elements",
        f"  Checked  : {len(checked)} free nodes, "
        f"{sum(len(incidence[n]) for n in checked)} element incidences",
        f"  Material : {mat.name}, E = {_q(mat.E)} MPa, ν = {_q(mat.nu)}",
        "-/",
        "",
        "import NasaStd5001B.Fem.Assembly",
        "",
        "-- The node and element lists below are long, and a list literal",
        "-- elaborates as nested `cons`, so the default recursion limit is far",
        "-- too low to read this file.",
        "set_option maxRecDepth 1000000",
        "",
        "namespace NasaStd5001B.Generated",
        "",
        "open NasaStd5001B.Fem",
        "",
        "/-- Lamé parameters λ and μ, derived exactly from E and ν. -/",
        f"def mat : Material := ⟨{_q(lame.lam)}, {_q(lame.mu)}⟩",
        "",
        "-- The elements, and the state each one contributes.  Naming the state",
        "-- keeps each element's data in the file exactly once, however many",
        "-- nodes refer to it.",
        "",
    ]

    for eid in eids:
        i = slot[eid]
        conn = fea.elements[eid]
        p = "".join(_v3(fea.coords[n]) + "," for n in conn)
        u = ",".join(_v3(fea.disps[n]) for n in conn)
        L.append(f"def e{i} : Elem := ⟨{p}{u}⟩")
        L.append(f"def s{i} : RawState := Elem.rawState e{i} mat")

    L += ["",
          "/-- One equilibrium check per free node.  Nodes on the fixed face are",
          "    omitted: they carry an unknown reaction, so their equilibrium",
          "    equation says nothing about the solution. -/",
          "def nodes : List NodeCheck :="]
    rows = []
    for n in checked:
        inc = ",".join(f"(s{slot[eid]},{a})" for eid, a in incidence[n])
        rows.append(f"  ⟨{_v3q(fea.fext.get(n, (Fraction(0),) * 3))},[{inc}]⟩")
    L.append("  [" + ",\n  ".join(r.strip() for r in rows) + "]")

    L += ["",
          "/-- Every element, for the peak-stress recovery. -/",
          "def elems : List RawState :=",
          "  [" + ", ".join(f"s{slot[e]}" for e in eids) + "]",
          "",
          "/-- The discrete model Lean checks the solver against. -/",
          "def model : Model :=",
          f"  ⟨{_q(COORD_SCALE)}, {_q(DISP_SCALE)}, nodes, elems⟩",
          "",
          "end NasaStd5001B.Generated",
          ""]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------
# The theorem file
# ---------------------------------------------------------------------------

def _write_theorems(path: Path, geom: BracketGeometry, mat: Material,
                    approach: str, limit_load_n: Fraction, fea: FEAResult,
                    lame, residual: Fraction, epsilon: Fraction, q: Fraction,
                    sigma_bound: Fraction, sigma_lo: Fraction,
                    sigma_hi: Fraction, compliant: bool,
                    ms_yield: Fraction, ms_ult: Fraction,
                    n_checked: int, n_incid: int) -> None:
    approach_lean = ".prototype" if approach == "prototype" else ".protoflight"
    sigma_f = math.sqrt(float(q))
    beam = (6 * float(limit_load_n) * float(geom.length)
            / (float(geom.width) * float(geom.height) ** 2))
    gap = (sigma_f - beam) / beam * 100

    head = [
        "/-",
        "  NasaStd5001B.Generated.Bracket",
        f"  Auto-generated by pipeline/generate_lean.py on {date.today()}.",
        "  DO NOT EDIT, re-run the pipeline to regenerate.",
        "",
        f"  Geometry   : {float(geom.width):.0f} × {float(geom.height):.0f} mm section,"
        f" {float(geom.length):.0f} mm cantilever",
        f"  Material   : {mat.name}  (Fty = {_q(mat.Fty)} MPa, Ftu = {_q(mat.Ftu)} MPa)",
        f"  Approach   : {approach} (§4.1.1)",
        f"  Limit load : {float(limit_load_n):.0f} N, applied in −y at the free end",
        "               (§3.2, the solve is performed at exactly this load, because",
        "               the Margin of Safety is defined at limit load)",
        "",
        f"  Mesh       : {fea.n_nodes} nodes, {fea.n_elements} C3D4 elements,"
        f" min quality {fea.min_quality:.3f}",
        f"  Solver     : CalculiX {fea.ccx_version} (untrusted proposal)",
        f"  Checked    : {n_checked} free nodes, {n_incid} element incidences",
        "",
        f"  Residual   : ‖K u − f‖_∞ = {float(residual):.3e} N, certified ≤"
        f" {float(epsilon):.0e} N",
        f"               (nodal load {float(fea.load_per_node):.4f} N, so a relative"
        f" residual of {float(residual / fea.load_per_node):.1e})",
        f"  Peak stress: √(max von Mises²) = {sigma_f:.4f} MPa, bracketed by",
        f"               [{float(sigma_lo):.4f}, {float(sigma_hi):.4f}] MPa",
        f"  Certified σ: {_q(sigma_bound)} MPa"
        f" ({'upper' if compliant else 'lower'} bound, conservative for this verdict)",
        "",
        "  Cross-check (NOT part of the proof):",
        f"    CalculiX's own peak von Mises : {fea.sigma_max_solver:.4f} MPa",
        f"    Euler–Bernoulli 6FL/bh²       : {beam:.4f} MPa  ({gap:+.1f}%)",
        "    The gap to beam theory is discretisation error.  Linear tetrahedra",
        "    are stiff in bending, and this model is outside the proof boundary:",
        "    see the trusted-inputs table in the README.",
        "",
        "  What is proved below is a statement about the *discrete* model, ",
        "  this mesh, these boundary conditions, this material, and not about",
        "  the physical bracket.",
        "-/",
        "",
        "import NasaStd5001B.Generated.BracketData",
        "import NasaStd5001B.Meta",
        "",
        "-- `decide +kernel` unfolds the whole model, which is deeper than the",
        "-- default recursion limit allows.",
        "set_option maxRecDepth 1000000",
        "",
        "namespace NasaStd5001B.Generated",
        "",
        "open NasaStd5001B NasaStd5001B.Fem",
        "",
        "/-- The residual tolerance this certificate claims, in newtons. -/",
        f"def residualTol : ℚ := {_q(epsilon)}",
        "",
        "/-- The rational stress the §4.2d check is performed at, in MPa. -/",
        f"def sigmaBound : ℚ := {_q(sigma_bound)}",
        "",
        "-- ---------------------------------------------------------------------",
        "-- 1. The solver's displacement satisfies the system Lean assembled",
        "-- ---------------------------------------------------------------------",
        "",
        "/-- `‖K u − f‖_∞ ≤ ε` over every free node.",
        "",
        "    `K` and `f` here are the ones Lean builds from the mesh in",
        "    `BracketData`, by `Fem.Assembly`.  CalculiX's `u` is only an input to",
        "    this check, nothing the solver reported about it is taken on trust. -/",
        "theorem residual_ok : model.maxAbsResidual ≤ residualTol := by",
        "  decide +kernel",
        "",
        "-- ---------------------------------------------------------------------",
        "-- 2. The peak stress of that displacement field",
        "-- ---------------------------------------------------------------------",
        "",
    ]

    if compliant:
        body = [
            "/-- The largest von Mises stress over all elements is at most",
            "    `sigmaBound`, stated on squares because ℚ has no square roots. -/",
            "theorem stress_bounded : model.maxVonMisesSq ≤ sigmaBound ^ 2 := by",
            "  decide +kernel",
            "",
            "-- ---------------------------------------------------------------------",
            "-- 3. §4.2d at that stress",
            "-- ---------------------------------------------------------------------",
            "",
            "/-- The design as checked: the certified stress against the material",
            "    allowables, under the Table 1 factors for this approach. -/",
            "def bracket : StructuralCheck :=",
            f"  {{ σ_max         := sigmaBound",
            f"    σ_yield_allow := {_q(mat.Fty)}",
            f"    σ_ult_allow   := {_q(mat.Ftu)}",
            f"    approach      := {approach_lean} }}",
            "",
            f"-- MS_yield = {_q(mat.Fty)} / ({_q(sigma_bound)} × "
            f"{_q(DESIGN_FACTORS[approach]['yield'])}) − 1 = {float(ms_yield):+.4f}",
            f"-- MS_ult   = {_q(mat.Ftu)} / ({_q(sigma_bound)} × "
            f"{_q(DESIGN_FACTORS[approach]['ultimate'])}) − 1 = {float(ms_ult):+.4f}",
            "",
            "/-- §4.2d holds at the certified stress: the factored stresses do not",
            "    exceed the material allowables, for both yield and ultimate. -/",
            "theorem bracket_compliant : bracket.isCompliant := by decide +kernel",
            "",
            "/-- …and therefore at any smaller stress, by monotonicity of the margin.",
            "",
            "    This is what makes certifying an *upper* bound on the stress sound:",
            "    the margin of safety decreases as stress increases, so passing at",
            "    the bound implies passing at the true value. -/",
            "theorem bracket_compliant_below (σ : ℚ) (hσ : 0 < σ) (hle : σ ≤ sigmaBound) :",
            "    (⟨σ, bracket.σ_yield_allow, bracket.σ_ult_allow,",
            "      bracket.approach⟩ : StructuralCheck).isCompliant := by",
            "  have hb : (0 : ℚ) < sigmaBound := by decide +kernel",
            "  have hy : (0 : ℚ) ≤ bracket.σ_yield_allow := by decide +kernel",
            "  have hu : (0 : ℚ) ≤ bracket.σ_ult_allow := by decide +kernel",
            "  exact compliant_of_lower_stress (s := bracket) hσ hb hy hu hle",
            "    bracket_compliant",
            "",
            "-- ---------------------------------------------------------------------",
            "-- The certificate",
            "-- ---------------------------------------------------------------------",
            "",
            "/-- The bracket COMPLIES with NASA-STD-5001B §4.2d, for this discrete",
            "    model, subject to the assumptions recorded in the README.",
            "",
            "    Read the three conjuncts as: the solver's displacement really does",
            "    solve the system Lean assembled, that displacement's peak von Mises",
            "    stress is at most `sigmaBound`, and at `sigmaBound` the factored",
            "    stresses stay within the material allowables. -/",
            "theorem bracket_certificate :",
            "    model.maxAbsResidual ≤ residualTol",
            "  ∧ model.maxVonMisesSq ≤ sigmaBound ^ 2",
            "  ∧ bracket.isCompliant :=",
            "  ⟨residual_ok, stress_bounded, bracket_compliant⟩",
        ]
    else:
        body = [
            "/-- The largest von Mises stress over all elements is at least",
            "    `sigmaBound`, stated on squares because ℚ has no square roots. -/",
            "theorem stress_at_least : sigmaBound ^ 2 ≤ model.maxVonMisesSq := by",
            "  decide +kernel",
            "",
            "-- ---------------------------------------------------------------------",
            "-- 3. §4.2d at that stress",
            "-- ---------------------------------------------------------------------",
            "",
            "/-- The design as checked: the certified stress against the material",
            "    allowables, under the Table 1 factors for this approach. -/",
            "def bracket : StructuralCheck :=",
            f"  {{ σ_max         := sigmaBound",
            f"    σ_yield_allow := {_q(mat.Fty)}",
            f"    σ_ult_allow   := {_q(mat.Ftu)}",
            f"    approach      := {approach_lean} }}",
            "",
            f"-- MS_yield = {_q(mat.Fty)} / ({_q(sigma_bound)} × "
            f"{_q(DESIGN_FACTORS[approach]['yield'])}) − 1 = {float(ms_yield):+.4f}",
            f"-- MS_ult   = {_q(mat.Ftu)} / ({_q(sigma_bound)} × "
            f"{_q(DESIGN_FACTORS[approach]['ultimate'])}) − 1 = {float(ms_ult):+.4f}",
            "",
            "/-- §4.2d FAILS at the certified stress: some factored stress exceeds",
            "    its material allowable. -/",
            "theorem bracket_noncompliant : ¬ bracket.isCompliant := by decide +kernel",
            "",
            "/-- …and therefore at any larger stress, by monotonicity of the margin.",
            "",
            "    This is what makes certifying a *lower* bound on the stress sound",
            "    for a failure verdict: if the design already fails at the bound, it",
            "    fails at the true, larger value too. -/",
            "theorem bracket_noncompliant_above (σ : ℚ) (hσ : 0 < σ)",
            "    (hge : sigmaBound ≤ σ) :",
            "    ¬ (⟨σ, bracket.σ_yield_allow, bracket.σ_ult_allow,",
            "       bracket.approach⟩ : StructuralCheck).isCompliant := by",
            "  intro hc",
            "  have hb : (0 : ℚ) < sigmaBound := by decide +kernel",
            "  have hy : (0 : ℚ) ≤ bracket.σ_yield_allow := by decide +kernel",
            "  have hu : (0 : ℚ) ≤ bracket.σ_ult_allow := by decide +kernel",
            "  -- `s` is given explicitly: inferring it from `bracket_noncompliant`",
            "  -- would leave Lean unifying a record against a projection of one.",
            "  exact bracket_noncompliant (compliant_of_lower_stress",
            "    (s := (⟨σ, bracket.σ_yield_allow, bracket.σ_ult_allow,",
            "            bracket.approach⟩ : StructuralCheck))",
            "    hb hσ hy hu hge hc)",
            "",
            "-- ---------------------------------------------------------------------",
            "-- The certificate",
            "-- ---------------------------------------------------------------------",
            "",
            "/-- The bracket DOES NOT COMPLY with NASA-STD-5001B §4.2d, for this",
            "    discrete model, subject to the assumptions recorded in the README.",
            "",
            "    Read the three conjuncts as: the solver's displacement really does",
            "    solve the system Lean assembled, that displacement's peak von Mises",
            "    stress is at least `sigmaBound`, and at `sigmaBound` some factored",
            "    stress already exceeds its material allowable. -/",
            "theorem bracket_certificate :",
            "    model.maxAbsResidual ≤ residualTol",
            "  ∧ sigmaBound ^ 2 ≤ model.maxVonMisesSq",
            "  ∧ ¬ bracket.isCompliant :=",
            "  ⟨residual_ok, stress_at_least, bracket_noncompliant⟩",
        ]

    tail = ["", "end NasaStd5001B.Generated", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(head + body + tail))
