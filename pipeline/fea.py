"""
pipeline/fea.py

FEA pipeline: STEP → Gmsh mesh → CalculiX solve → max von Mises stress.

Stages:
  1. Mesh (Gmsh): import STEP, generate linear C3D4 tetrahedral mesh,
                  export to ABAQUS .inp format.
  2. Solve (CalculiX): assemble full .inp deck (material, BCs, load, output
                       requests), invoke ccx subprocess.
  3. Post-process: parse .dat for stress tensor components per element per
                   integration point; compute von Mises; take the maximum;
                   return a conservative rational upper bound.

Conservative rounding (§3.2 Limit Load / Margin of Safety):
  σ_max_rational = ceil(σ_max_float × 1000) / 1000
  This guarantees σ_max_rational ≥ σ_max_float, so the Lean compliance
  certificate is conservative: if Lean proves MS ≥ 0 using σ_max_rational,
  the design is compliant at the actual (smaller or equal) FEA stress.
"""

from __future__ import annotations
import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import gmsh

from .cad_model import BracketGeometry, Material

# Path to CalculiX binary.  FreeCAD bundles version 2.14.
_CCX_DEFAULT = "/Applications/FreeCAD.app/Contents/Resources/bin/ccx"
CCX_PATH = os.environ.get("CCX_PATH", _CCX_DEFAULT)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FEAResult:
    """Outputs from the CalculiX solve."""
    sigma_max_float:    float     # raw max von Mises (MPa) from .dat
    sigma_max_rational: Fraction  # conservative upper bound (ceil to 0.001 MPa)
    n_nodes:            int
    n_elements:         int


# ---------------------------------------------------------------------------
# Stage 1: Mesh with Gmsh
# ---------------------------------------------------------------------------

def _mesh(step_path: Path, inp_path: Path, geom: BracketGeometry) -> None:
    """Import STEP, generate a C3D4 tetrahedral mesh, write ABAQUS .inp."""
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("bracket")
        gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()

        # Mesh size: ~3 elements across the height for reasonable accuracy
        h = float(geom.height)
        lc = h / 3.0
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", lc)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", lc / 2.0)

        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(1)   # linear C3D4 elements

        gmsh.write(str(inp_path))
    finally:
        gmsh.finalize()


# ---------------------------------------------------------------------------
# Stage 2: Assemble CalculiX input deck and solve
# ---------------------------------------------------------------------------

def _parse_gmsh_inp(inp_path: Path) -> tuple[dict[int, tuple[float,float,float]],
                                              dict[int, tuple[int,...]]]:
    """Parse nodes and C3D4 elements from a Gmsh-generated ABAQUS .inp."""
    nodes: dict[int, tuple[float,float,float]] = {}
    elements: dict[int, tuple[int,...]] = {}

    text = inp_path.read_text()
    lines = iter(text.splitlines())
    section = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*"):
            ul = line.upper()
            if ul.startswith("*NODE") and "PRINT" not in ul and "FILE" not in ul:
                section = "NODE"
            elif "C3D4" in ul:
                section = "C3D4"
            else:
                section = None
            continue

        if section == "NODE":
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 4:
                try:
                    nid = int(parts[0])
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    nodes[nid] = (x, y, z)
                except ValueError:
                    pass

        elif section == "C3D4":
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 5:
                try:
                    eid = int(parts[0])
                    ns = tuple(int(p) for p in parts[1:])
                    elements[eid] = ns
                except ValueError:
                    pass

    return nodes, elements


def _write_ccx_inp(
    ccx_inp_path: Path,
    gmsh_inp_path: Path,
    nodes: dict[int, tuple[float,float,float]],
    elements: dict[int, tuple[int,...]],
    geom: BracketGeometry,
    mat: Material,
    limit_load_n: float,
) -> None:
    """
    Write a complete CalculiX .inp deck.

    Boundary conditions:
      · Fixed face  (z ≈ -L/2): ENCASTRE (all 6 DOFs fixed)
      · Free face   (z ≈ +L/2): distributed concentrated load in -y direction
                                 summing to limit_load_n Newtons total.

    The load is applied in -y (bending the bracket downward).  The bracket's
    height dimension is along y, so this produces maximum bending stress at the
    fixed end, consistent with σ = 6·F·L / (b·h²).
    """
    L_half = float(geom.length) / 2.0
    tol = float(geom.length) * 0.02   # 2% of length as z-coordinate tolerance

    fixed_nodes  = [nid for nid, (x, y, z) in nodes.items() if abs(z - (-L_half)) < tol]
    loaded_nodes = [nid for nid, (x, y, z) in nodes.items() if abs(z - L_half) < tol]

    if not fixed_nodes:
        raise RuntimeError(f"No fixed-face nodes found near z={-L_half:.1f}")
    if not loaded_nodes:
        raise RuntimeError(f"No loaded-face nodes found near z={L_half:.1f}")

    load_per_node = limit_load_n / len(loaded_nodes)

    with ccx_inp_path.open("w") as f:
        # --- Nodes ---
        f.write("*NODE, NSET=NALL\n")
        for nid, (x, y, z) in sorted(nodes.items()):
            f.write(f"{nid}, {x:.10g}, {y:.10g}, {z:.10g}\n")

        # --- Elements ---
        f.write("*ELEMENT, TYPE=C3D4, ELSET=EALL\n")
        for eid, ns in sorted(elements.items()):
            f.write(f"{eid}, {', '.join(str(n) for n in ns)}\n")

        # --- Material (§4.2c, isotropic linear elastic) ---
        f.write(f"*MATERIAL, NAME={mat.name}\n")
        f.write("*ELASTIC\n")
        f.write(f"{mat.E}, {mat.nu}\n")
        f.write("*SOLID SECTION, ELSET=EALL, MATERIAL=" + mat.name + "\n")
        f.write("1.0\n")

        # --- Boundary conditions: fixed end ---
        f.write("*NSET, NSET=FIXED\n")
        for i, nid in enumerate(sorted(fixed_nodes)):
            f.write(str(nid))
            if i < len(fixed_nodes) - 1:
                f.write(", ")
                if (i + 1) % 16 == 0:
                    f.write("\n")
        f.write("\n")
        f.write("*BOUNDARY\n")
        f.write("FIXED, 1, 3, 0.0\n")   # C3D4 solid: 3 translational DOFs only

        # --- Step ---
        f.write("*STEP\n")
        f.write("*STATIC\n")

        # --- Distributed load on free end: -y direction ---
        f.write("*CLOAD\n")
        for nid in loaded_nodes:
            f.write(f"{nid}, 2, {-load_per_node:.10g}\n")   # DOF 2 = y

        # --- Output: stress tensor components per element ---
        f.write("*EL PRINT, ELSET=EALL\n")
        f.write("S\n")

        f.write("*END STEP\n")


def _run_ccx(ccx_inp_path: Path) -> Path:
    """Invoke CalculiX on <stem>.inp; returns path to .dat output file."""
    stem = ccx_inp_path.stem
    work_dir = ccx_inp_path.parent

    result = subprocess.run(
        [CCX_PATH, stem],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    dat_path = work_dir / f"{stem}.dat"
    if not dat_path.exists():
        raise RuntimeError(
            f"CalculiX did not produce {dat_path}.\n"
            f"stdout: {result.stdout[-500:]}\n"
            f"stderr: {result.stderr[-500:]}"
        )
    return dat_path


# ---------------------------------------------------------------------------
# Stage 3: Parse .dat and compute max von Mises
# ---------------------------------------------------------------------------

def _parse_von_mises(dat_path: Path) -> float:
    """
    Parse CalculiX .dat for stress tensor components (sxx,syy,szz,sxy,sxz,syz)
    per element per integration point.  Compute von Mises for each and return
    the maximum.

    CalculiX .dat stress block format (from *EL PRINT, S):
      stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set ... and time ...
      <eid>  <ipt>  <sxx>  <syy>  <szz>  <sxy>  <sxz>  <syz>
    """
    text = dat_path.read_text()

    # Find the stress section header
    stress_pat = re.compile(
        r"stresses\s+\(elem.*?syz\).*?time\s+[\d.E+\-]+\s*\n(.*?)(?:\n\s*\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = stress_pat.search(text)
    if not match:
        raise RuntimeError(
            f"Could not find stress block in {dat_path}.\n"
            f"Content preview:\n{text[:500]}"
        )

    block = match.group(1)

    max_vm = 0.0
    n_parsed = 0
    # Each data line: eid  ipt  sxx  syy  szz  sxy  sxz  syz
    data_pat = re.compile(
        r"^\s*\d+\s+\d+\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)",
        re.IGNORECASE | re.MULTILINE,
    )
    for m in data_pat.finditer(block):
        n_parsed += 1
        sxx, syy, szz, sxy, sxz, syz = (float(m.group(i)) for i in range(1, 7))
        vm = math.sqrt(0.5 * (
            (sxx - syy)**2 + (syy - szz)**2 + (szz - sxx)**2
            + 6 * (sxy**2 + sxz**2 + syz**2)
        ))
        if vm > max_vm:
            max_vm = vm

    if n_parsed == 0:
        raise RuntimeError(f"No stress data rows parsed from {dat_path}")

    return max_vm


def _conservative_rational(sigma_float: float) -> Fraction:
    """
    Return a rational upper bound on sigma_float, rounded UP to 0.001 MPa.

    ceil(σ × 1000) / 1000  guarantees  rational ≥ float.
    """
    return Fraction(math.ceil(sigma_float * 1000), 1000)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_fea(
    step_path: Path,
    geom: BracketGeometry,
    mat: Material,
    limit_load_n: float,
    work_dir: Path,
) -> FEAResult:
    """
    Full FEA pipeline: STEP → mesh → solve → max von Mises → rational bound.

    Parameters
    ----------
    step_path     : STEP file of the bracket geometry.
    geom          : BracketGeometry (dimensions in mm).
    mat           : Material (elastic properties and allowables).
    limit_load_n  : Limit load in Newtons (§3.2).  FEA is run at exactly this
                    load; the resulting σ_max is the stress at limit load.
    work_dir      : Directory for all intermediate FEA files.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: mesh
    gmsh_inp = work_dir / "mesh.inp"
    _mesh(step_path, gmsh_inp, geom)
    nodes, elements = _parse_gmsh_inp(gmsh_inp)

    # Stage 2: solve
    ccx_inp = work_dir / "bracket.inp"
    _write_ccx_inp(ccx_inp, gmsh_inp, nodes, elements, geom, mat, limit_load_n)
    dat_path = _run_ccx(ccx_inp)

    # Stage 3: post-process
    sigma_float = _parse_von_mises(dat_path)
    sigma_rat   = _conservative_rational(sigma_float)

    return FEAResult(
        sigma_max_float=sigma_float,
        sigma_max_rational=sigma_rat,
        n_nodes=len(nodes),
        n_elements=len(elements),
    )
