"""
pipeline/run.py

Orchestrator: CAD → FEA → generate Lean → lake build → report.

Usage:
  python -m pipeline                          # 800 N, protoflight, Al 6061-T6
  python -m pipeline --limit-load 2000        # overloaded bracket
  python -m pipeline --approach prototype     # prototype verification approach
  python -m pipeline --limit-load 800 --approach prototype

The --limit-load value is the Limit Load per NASA-STD-5001B §3.2:
"the maximum anticipated load...that a structure may experience during its
design service life under all expected conditions of operation."

FEA is run at exactly this load.  Using any other load value would violate
the Margin of Safety definition.
"""

from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .cad_model import DEFAULT_GEOMETRY, AL_6061_T6, export_step
from .fea import run_fea
from .generate_lean import generate


REPO_ROOT  = Path(__file__).parent.parent
BRACKET_LEAN = REPO_ROOT / "NasaStd5001B" / "Generated" / "Bracket.lean"


def _beam_theory_sigma(geom, limit_load_n: float) -> float:
    """σ = 6·F·L / (b·h²) — Euler-Bernoulli cantilever bending stress (MPa)."""
    F = limit_load_n
    L = float(geom.length)
    b = float(geom.width)
    h = float(geom.height)
    return 6 * F * L / (b * h**2)


def run(limit_load_n: float, approach: str) -> int:
    """
    Execute the full pipeline.  Returns 0 on success, 1 on failure.
    """
    geom = DEFAULT_GEOMETRY
    mat  = AL_6061_T6

    print(f"\n{'='*60}")
    print(f"  NASA-STD-5001B Compliance Pipeline")
    print(f"{'='*60}")
    print(f"  Geometry : {float(geom.width):.0f}×{float(geom.height):.0f}×{float(geom.length):.0f} mm  ({mat.name})")
    print(f"  Limit load: {limit_load_n:.0f} N")
    print(f"  Approach  : {approach}")
    print()

    with tempfile.TemporaryDirectory(prefix="nasa5001_fea_") as work_str:
        work_dir = Path(work_str)

        # ------------------------------------------------------------------
        # Step 1: CAD → STEP
        # ------------------------------------------------------------------
        print("[1/4] Building CAD geometry...")
        step_path = work_dir / "bracket.step"
        export_step(geom, step_path)
        print(f"      STEP exported ({step_path.stat().st_size} bytes)")

        # ------------------------------------------------------------------
        # Step 2: FEA
        # ------------------------------------------------------------------
        print("[2/4] Running FEA (Gmsh → CalculiX)...")
        fea_result = run_fea(step_path, geom, mat, limit_load_n, work_dir)
        print(f"      Mesh      : {fea_result.n_nodes} nodes, "
              f"{fea_result.n_elements} C3D4 elements")
        print(f"      σ_max FEA : {fea_result.sigma_max_float:.4f} MPa")
        print(f"      σ_max bound: {fea_result.sigma_max_rational} MPa  (conservative)")

        # Cross-check against beam theory
        sigma_beam = _beam_theory_sigma(geom, limit_load_n)
        error_pct  = abs(fea_result.sigma_max_float - sigma_beam) / sigma_beam * 100
        print(f"      Beam theory: {sigma_beam:.4f} MPa  (error: {error_pct:.1f}%)")
        if error_pct > 30:
            print(f"  WARNING: FEA/beam-theory discrepancy {error_pct:.1f}% > 30%.")
            print("           Check mesh quality, BCs, and load application.")

        # ------------------------------------------------------------------
        # Step 3: Generate Lean
        # ------------------------------------------------------------------
        print("[3/4] Generating Lean compliance certificate...")
        gen = generate(geom, mat, approach, limit_load_n, fea_result, BRACKET_LEAN)
        print(f"      Written: {BRACKET_LEAN}")

        # Show the generated compliance theorem
        text = BRACKET_LEAN.read_text()
        for line in text.splitlines():
            if "theorem bracket_" in line and ":=" not in line.split("theorem")[0]:
                print(f"      {line.strip()}")

        # ------------------------------------------------------------------
        # Step 4: lake build
        # ------------------------------------------------------------------
        print("[4/4] Running lake build (Lean type-checker)...")
        lake_bin = shutil.which("lake") or str(Path.home() / ".elan" / "bin" / "lake")
        if not Path(lake_bin).exists():
            print("  ERROR: 'lake' not found. Add ~/.elan/bin to PATH or set CCX_PATH.")
            return 1
        lake_result = subprocess.run(
            [lake_bin, "build"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if lake_result.returncode != 0:
            print("  ERROR: lake build FAILED")
            print(lake_result.stdout)
            print(lake_result.stderr)
            return 1

        print("      lake build: OK")

    # ------------------------------------------------------------------
    # Report  (margins already computed by generate(); use them directly)
    # ------------------------------------------------------------------
    if approach == "prototype":
        df_y, df_u = "1.00", "1.40"
    else:
        df_y, df_u = "1.25", "1.40"

    print()
    print(f"{'='*60}")
    verdict = "COMPLIANT ✓" if gen.compliant else "NON-COMPLIANT ✗"
    print(f"  RESULT: {verdict}")
    print(f"{'='*60}")
    print(f"  σ_max (conservative bound) : {float(fea_result.sigma_max_rational):.4f} MPa")
    ms_y_str = f"{float(gen.ms_yield):+.4f}"
    ms_u_str = f"{float(gen.ms_ult):+.4f}"
    y_flag = "OK" if gen.ms_yield >= 0 else "FAIL"
    u_flag = "OK" if gen.ms_ult   >= 0 else "FAIL"
    print(f"  MS_yield  ({approach:>11}, DF={df_y}) : {ms_y_str}  [{y_flag}]")
    print(f"  MS_ult    ({approach:>11}, DF={df_u}) : {ms_u_str}  [{u_flag}]")
    print(f"  Lean verification : machine-checked by lake build")
    print(f"{'='*60}")
    print()

    return 0 if gen.compliant else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NASA-STD-5001B compliance pipeline: CAD → FEA → Lean certificate"
    )
    parser.add_argument(
        "--limit-load", type=float, default=800.0, dest="limit_load",
        help="Limit load in Newtons (§3.2 definition). Default: 800 N.",
    )
    parser.add_argument(
        "--approach", choices=["prototype", "protoflight"], default="protoflight",
        help="Verification approach per §4.1.1. Default: protoflight.",
    )
    args = parser.parse_args()
    sys.exit(run(args.limit_load, args.approach))


if __name__ == "__main__":
    main()
