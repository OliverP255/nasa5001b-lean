"""
pipeline/run.py

Orchestrator: CAD → mesh → FEA → generated Lean → lake build → axiom audit.

  python -m pipeline                          # 800 N, protoflight, Al 6061-T6
  python -m pipeline --limit-load 2000        # overloaded bracket
  python -m pipeline --approach prototype     # prototype verification approach
  python -m pipeline --mesh-size 6            # finer mesh (slower to check)

`--limit-load` is the Limit Load of NASA-STD-5001B §3.2
"the maximum anticipated load ... that a structure may experience during its design service
life under all expected conditions of operation."  

The FEA is run at exactly this load, because the Margin of Safety is defined in terms of the stress at
the limit load. 

Exit code 0 means the pipeline ran and Lean checked the certificate. 1 means
the certificate says the design does not comply, or something failed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from .cad_model import AL_6061_T6, DEFAULT_GEOMETRY, export_step
from .fea import run_fea
from .generate_lean import generate

REPO_ROOT = Path(__file__).parent.parent
DATA_LEAN = REPO_ROOT / "NasaStd5001B" / "Generated" / "BracketData.lean"
THM_LEAN = REPO_ROOT / "NasaStd5001B" / "Generated" / "Bracket.lean"
AXIOM_LEAN = REPO_ROOT / "Scripts" / "Axioms.lean"

#: Default element size, in mm.
#:
#: This is the main speed/accuracy dial.  The kernel has to evaluate every
#: element of the model in exact rational arithmetic, so checking time grows
#: roughly linearly with element count: ~680 elements check in about two
#: minutes, ~1150 in about three and a half.  The certificate is a statement
#: about whichever discrete model it is given, so a coarser mesh does not make
#: it less true, it makes it a claim about a cruder model, and widens the gap
#: to beam theory that each certificate reports.
DEFAULT_MESH_SIZE_MM = 10.0

#: Axioms a certificate may legitimately depend on.  `ofReduceBool` would mean
#: `native_decide` crept in, trusting the compiler, `sorryAx` an open goal.
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
BANNED_AXIOMS = {"ofReduceBool", "ofReduceNat", "sorryAx", "Lean.ofReduceBool"}


def _lake() -> str | None:
    found = shutil.which("lake") or str(Path.home() / ".elan" / "bin" / "lake")
    return found if Path(found).exists() else None


def _run_lake(args: list[str]) -> subprocess.CompletedProcess:
    lake = _lake()
    if lake is None:
        raise RuntimeError("'lake' not found, add ~/.elan/bin to PATH")
    return subprocess.run([lake] + args, cwd=REPO_ROOT, capture_output=True, text=True)


def _audit_axioms() -> tuple[bool, str]:
    """Run the axiom audit and check nothing banned appears.

    A certificate that type-checks can still rest on `native_decide`, which
    asks the kernel to believe the compiler.  This makes that visible.
    """
    if not AXIOM_LEAN.exists():
        return True, "skipped (Scripts/Axioms.lean not present)"
    result = _run_lake(["env", "lean", str(AXIOM_LEAN)])
    out = result.stdout + result.stderr
    if result.returncode != 0:
        return False, f"axiom audit failed to run:\n{out[-800:]}"
    hits = sorted(a for a in BANNED_AXIOMS if a in out)
    if hits:
        return False, f"certificate depends on banned axioms: {', '.join(hits)}"
    return True, out.strip()


def run(limit_load_n: Fraction, approach: str, mesh_size_mm: float,
        refine: int, skip_build: bool) -> int:
    geom, mat = DEFAULT_GEOMETRY, AL_6061_T6

    print()
    print("=" * 68)
    print("  NASA-STD-5001B compliance pipeline")
    print("=" * 68)
    print(f"  Geometry   : {float(geom.width):.0f}×{float(geom.height):.0f}"
          f"×{float(geom.length):.0f} mm  ({mat.name})")
    print(f"  Limit load : {float(limit_load_n):.0f} N   (§3.2)")
    print(f"  Approach   : {approach}   (§4.1.1, Table 1)")
    print()

    with tempfile.TemporaryDirectory(prefix="nasa5001_") as work_str:
        work = Path(work_str)

        print("[1/5] Building CAD geometry ...")
        step = work / "bracket.step"
        export_step(geom, step)
        print(f"      STEP exported ({step.stat().st_size} bytes)")

        print(f"[2/5] Meshing and solving (Gmsh → CalculiX, {refine} refinement "
              f"pass{'es' if refine != 1 else ''}) ...")
        fea = run_fea(step, geom, mat, limit_load_n, work, mesh_size_mm, refine)
        print(f"      Mesh        : {fea.n_nodes} nodes, {fea.n_elements} C3D4 "
              f"elements, min quality {fea.min_quality:.3f}")
        print(f"      CalculiX    : v{fea.ccx_version}, peak von Mises "
              f"{fea.sigma_max_solver:.4f} MPa")
        if fea.min_quality < 0.10:
            print("      WARNING: sliver elements present, a constant-strain")
            print("               tetrahedron reports nonsense stress on those.")

        print("[3/5] Generating the Lean certificate ...")
        gen = generate(geom, mat, approach, limit_load_n, fea, DATA_LEAN, THM_LEAN)
        rel = float(gen.residual / fea.load_per_node)
        print(f"      Checked     : {gen.n_checked_nodes} free nodes, "
              f"{gen.n_incidences} incidences")
        print(f"      Residual    : ‖K u − f‖_∞ = {float(gen.residual):.3e} N "
              f"({rel:.1e} of the nodal load)")
        print(f"      Certifying  : ‖K u − f‖_∞ ≤ {float(gen.epsilon):.0e} N")
        print(f"      Peak stress : in [{float(gen.sigma_lo):.4f}, "
              f"{float(gen.sigma_hi):.4f}] MPa, certified at "
              f"{float(gen.sigma_bound):.4f} MPa")
        print(f"      Written     : {DATA_LEAN.name}, {THM_LEAN.name}")

        if skip_build:
            print("[4/5] lake build ... skipped (--skip-build)")
            print("[5/5] axiom audit ... skipped")
            return 0 if gen.compliant else 1

        print("[4/5] Checking the proof (lake build) ...")
        built = _run_lake(["build"])
        if built.returncode != 0:
            print("  ERROR: lake build FAILED, the certificate does not hold.")
            print((built.stdout + built.stderr)[-3000:])
            return 1
        print("      lake build: OK")

        print("[5/5] Auditing the axioms the certificate rests on ...")
        ok, detail = _audit_axioms()
        for line in detail.splitlines():
            if line.strip():
                print(f"      {line.strip()}")
        if not ok:
            print("  ERROR: axiom audit FAILED")
            return 1

    df = {"prototype": ("1.00", "1.40"), "protoflight": ("1.25", "1.40")}[approach]
    print()
    print("=" * 68)
    print(f"  RESULT: {'COMPLIANT' if gen.compliant else 'NON-COMPLIANT'}"
          f"  (§4.2d, {approach})")
    print("=" * 68)
    print(f"  Certified stress            : {float(gen.sigma_bound):.4f} MPa "
          f"({'upper' if gen.compliant else 'lower'} bound)")
    print(f"  MS_yield (DF={df[0]})           : {float(gen.ms_yield):+.4f}  "
          f"[{'OK' if gen.ms_yield >= 0 else 'FAIL'}]")
    print(f"  MS_ult   (DF={df[1]})           : {float(gen.ms_ult):+.4f}  "
          f"[{'OK' if gen.ms_ult >= 0 else 'FAIL'}]")
    print(f"  Equilibrium residual        : ≤ {float(gen.epsilon):.0e} N, "
          f"kernel-checked")
    print("  Untrusted: mesh, discretisation error, boundary conditions,")
    print("             material values and allowables, the limit load itself.")
    print("=" * 68)
    print()
    return 0 if gen.compliant else 1


def main() -> None:
    p = argparse.ArgumentParser(
        description="NASA-STD-5001B compliance pipeline: CAD → FEA → Lean certificate")
    p.add_argument("--limit-load", type=Fraction, default=Fraction(800),
                   dest="limit_load",
                   help="Limit load in newtons (§3.2). Default: 800.")
    p.add_argument("--approach", choices=["prototype", "protoflight"],
                   default="protoflight",
                   help="Verification approach per §4.1.1. Default: protoflight.")
    p.add_argument("--mesh-size", type=float, default=DEFAULT_MESH_SIZE_MM,
                   dest="mesh_size",
                   help=f"Target element size in mm. Default: {DEFAULT_MESH_SIZE_MM}. "
                        "Smaller means a better model and a slower kernel check.")
    p.add_argument("--refine", type=int, default=1,
                   help="Iterative-refinement passes recovering precision lost in "
                        "the solver's text output. Default: 1.")
    p.add_argument("--skip-build", action="store_true",
                   help="Generate the Lean files but do not check them.")
    a = p.parse_args()
    sys.exit(run(a.limit_load, a.approach, a.mesh_size, a.refine, a.skip_build))


if __name__ == "__main__":
    main()
