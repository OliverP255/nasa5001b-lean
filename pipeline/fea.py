"""
pipeline/fea.py

FEA stage: STEP → Gmsh mesh → CalculiX solve → the exact discrete model.

Unlike a conventional FEA driver, this stage does not produce "the answer".
It produces an exactly-specified discrete problem together with CalculiX's
*proposed* solution, so that Lean can check the proposal for itself:

  1. Mesh (Gmsh): import STEP, generate a C3D4 tetrahedral mesh.
  2. Snap: round every node coordinate to an integer number of micrometres.
     The snapped coordinates are what gets written to CalculiX, so the solver
     and Lean are talking about the same mesh rather than two mesh-shaped
     objects that differ in the last few bits.
  3. Solve (CalculiX): assemble the .inp deck, run ccx, read back both the
     displacement field and the solver's own stresses.
  4. Snap again: round displacements to an integer number of picometres.

Boundary conditions are selected by exact integer comparison on the snapped
coordinates: the fixed face is `z == z_min` and the loaded face is `z == z_max`.
A tolerance-based selection would silently capture a different node set on a
different mesh, which would change the problem being certified.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

import gmsh

from .cad_model import BracketGeometry, Material

# Path to CalculiX binary.  FreeCAD bundles a copy.
_CCX_DEFAULT = "/Applications/FreeCAD.app/Contents/Resources/bin/ccx"
CCX_PATH = os.environ.get("CCX_PATH", _CCX_DEFAULT)

#: Node coordinates are stored as integer multiples of this many mm.
COORD_SCALE = Fraction(1, 1000)          # micrometres
#: Nodal displacements are stored as integer multiples of this many mm.
DISP_SCALE = Fraction(1, 10 ** 12)       # picometres

IVec3 = tuple[int, int, int]


@dataclass(frozen=True)
class FEAResult:
    """The discrete problem, plus CalculiX's proposed solution.

    Coordinates are integer multiples of `COORD_SCALE` mm and displacements
    integer multiples of `DISP_SCALE` mm, so that every number reaching Lean
    is an integer.
    """
    coords: dict[int, IVec3]
    elements: dict[int, tuple[int, ...]]
    disps: dict[int, IVec3]
    fixed_nodes: list[int]
    loaded_nodes: list[int]
    load_per_node: Fraction          # N, applied in −y at each loaded node
    sigma_max_solver: float          # CalculiX's own peak von Mises, MPa
    ccx_version: str
    min_quality: float               # worst element quality in the mesh

    @property
    def n_nodes(self) -> int:
        return len(self.coords)

    @property
    def n_elements(self) -> int:
        return len(self.elements)

    @property
    def free_nodes(self) -> list[int]:
        """Nodes whose equilibrium is checked: everything but the fixed face.

        Constrained nodes carry an unknown reaction, so their equilibrium
        equation contains an unknown and says nothing about the solution.
        """
        fixed = set(self.fixed_nodes)
        return sorted(n for n in self.coords if n not in fixed)

    @property
    def fext(self) -> dict[int, tuple[Fraction, Fraction, Fraction]]:
        """The applied load vector: −y at each loaded node, zero elsewhere."""
        return {n: (Fraction(0), -self.load_per_node, Fraction(0))
                for n in self.loaded_nodes}

    def to_model(self, lame) -> "object":
        """Wrap this result as a `fem_reference.DiscreteModel`."""
        from .fem_reference import DiscreteModel
        return DiscreteModel(
            coords=self.coords, elems=self.elements, disps=self.disps,
            fext=self.fext, free=self.free_nodes, mat=lame,
            cs=COORD_SCALE, ds=DISP_SCALE)


# ---------------------------------------------------------------------------
# Stage 1: mesh
# ---------------------------------------------------------------------------

def _mesh(step_path: Path, inp_path: Path, mesh_size_mm: float) -> None:
    """Import STEP, generate a linear C3D4 mesh, write it as ABAQUS .inp.

    Mesh optimisation is essential here, not cosmetic.  A constant-strain
    tetrahedron recovers stress from a single gradient, so a sliver element —
    one nearly flat, with a tiny Jacobian — reports a wildly wrong stress.
    Without optimisation, coarse meshes of this bracket put their peak stress
    on a sliver sitting at the neutral axis, where the bending stress should
    be zero.  `check_mesh_quality` guards against what optimisation misses.
    """
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("bracket")
        gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size_mm)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size_mm / 2.0)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(1)
        gmsh.model.mesh.optimize("Netgen")
        gmsh.write(str(inp_path))
    finally:
        gmsh.finalize()


def element_quality(p: list[IVec3]) -> float:
    """Normalised tetrahedron quality: 1.0 is regular, 0.0 is degenerate.

    `6√2·V / ℓ_rms³`, where ℓ_rms is the root-mean-square edge length.  A
    regular tetrahedron has volume a³/(6√2), so this is 1 for a regular
    element and tends to 0 as the element flattens into a sliver.
    """
    c1 = [p[1][r] - p[0][r] for r in range(3)]
    c2 = [p[2][r] - p[0][r] for r in range(3)]
    c3 = [p[3][r] - p[0][r] for r in range(3)]
    cr = (c2[1] * c3[2] - c2[2] * c3[1],
          c2[2] * c3[0] - c2[0] * c3[2],
          c2[0] * c3[1] - c2[1] * c3[0])
    vol = abs(c1[0] * cr[0] + c1[1] * cr[1] + c1[2] * cr[2]) / 6.0
    edges = [[p[b][r] - p[a][r] for r in range(3)]
             for a in range(4) for b in range(a + 1, 4)]
    msq = sum(e[0] ** 2 + e[1] ** 2 + e[2] ** 2 for e in edges) / 6.0
    if msq <= 0:
        return 0.0
    return 6.0 * math.sqrt(2.0) * vol / msq ** 1.5


def _parse_gmsh_inp(inp_path: Path) -> tuple[dict[int, tuple[float, float, float]],
                                             dict[int, tuple[int, ...]]]:
    """Parse nodes and C3D4 elements from a Gmsh-generated ABAQUS .inp."""
    nodes: dict[int, tuple[float, float, float]] = {}
    elements: dict[int, tuple[int, ...]] = {}
    section = None

    for raw in inp_path.read_text().splitlines():
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

        parts = [p.strip() for p in line.split(",")]
        try:
            if section == "NODE" and len(parts) == 4:
                nodes[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif section == "C3D4" and len(parts) == 5:
                elements[int(parts[0])] = tuple(int(p) for p in parts[1:])
        except ValueError:
            continue

    if not nodes or not elements:
        raise RuntimeError(f"No C3D4 mesh parsed from {inp_path}")
    return nodes, elements


def _snap_coords(nodes: dict[int, tuple[float, float, float]]) -> dict[int, IVec3]:
    """Round every coordinate to an integer multiple of `COORD_SCALE` mm."""
    inv = 1 / float(COORD_SCALE)
    return {n: (round(x * inv), round(y * inv), round(z * inv))
            for n, (x, y, z) in nodes.items()}


def _orient(coords: dict[int, IVec3],
            elements: dict[int, tuple[int, ...]]) -> dict[int, tuple[int, ...]]:
    """Give every tetrahedron a positive Jacobian, as CalculiX requires.

    Snapping can in principle flip a nearly-degenerate element, so this is
    done on the snapped coordinates that both solvers actually see.
    """
    out: dict[int, tuple[int, ...]] = {}
    for eid, conn in elements.items():
        p = [coords[n] for n in conn]
        c1 = [p[1][r] - p[0][r] for r in range(3)]
        c2 = [p[2][r] - p[0][r] for r in range(3)]
        c3 = [p[3][r] - p[0][r] for r in range(3)]
        cr = (c2[1] * c3[2] - c2[2] * c3[1],
              c2[2] * c3[0] - c2[0] * c3[2],
              c2[0] * c3[1] - c2[1] * c3[0])
        det = c1[0] * cr[0] + c1[1] * cr[1] + c1[2] * cr[2]
        if det == 0:
            raise RuntimeError(f"Element {eid} is degenerate after snapping")
        out[eid] = conn if det > 0 else (conn[0], conn[1], conn[3], conn[2])
    return out


# ---------------------------------------------------------------------------
# Stage 2: CalculiX deck
# ---------------------------------------------------------------------------

def _write_ccx_inp(path: Path, coords: dict[int, IVec3],
                   elements: dict[int, tuple[int, ...]],
                   fixed_nodes: list[int],
                   cloads: dict[int, tuple[Fraction, Fraction, Fraction]],
                   mat: Material) -> None:
    """Write a complete CalculiX .inp deck for the snapped mesh and a given RHS."""
    scale = float(COORD_SCALE)
    with path.open("w") as f:
        f.write("*NODE, NSET=NALL\n")
        for n, c in sorted(coords.items()):
            f.write(f"{n}, {c[0] * scale:.6f}, {c[1] * scale:.6f}, {c[2] * scale:.6f}\n")

        f.write("*ELEMENT, TYPE=C3D4, ELSET=EALL\n")
        for eid, conn in sorted(elements.items()):
            f.write(f"{eid}, {', '.join(str(n) for n in conn)}\n")

        f.write(f"*MATERIAL, NAME={mat.name}\n*ELASTIC\n{float(mat.E):.10g}, {float(mat.nu):.10g}\n")
        f.write(f"*SOLID SECTION, ELSET=EALL, MATERIAL={mat.name}\n1.0\n")

        f.write("*NSET, NSET=FIXED\n")
        for i in range(0, len(fixed_nodes), 8):
            f.write(", ".join(str(n) for n in sorted(fixed_nodes)[i:i + 8]) + ",\n")
        f.write("*BOUNDARY\nFIXED, 1, 3, 0.0\n")

        f.write("*STEP\n*STATIC\n*CLOAD\n")
        for n in sorted(cloads):
            for dof in (1, 2, 3):
                v = cloads[n][dof - 1]
                if v != 0:
                    f.write(f"{n}, {dof}, {float(v):.12g}\n")
        f.write("*NODE PRINT, NSET=NALL\nU\n")
        f.write("*EL PRINT, ELSET=EALL\nS\n")
        f.write("*END STEP\n")


def _ccx_version() -> str:
    try:
        out = subprocess.run([CCX_PATH, "-v"], capture_output=True, text=True, timeout=30)
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", (out.stdout or "") + (out.stderr or ""))
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


def _run_ccx(inp_path: Path) -> Path:
    """Invoke CalculiX; return the path to its .dat output."""
    stem = inp_path.stem
    result = subprocess.run([CCX_PATH, stem], cwd=inp_path.parent,
                            capture_output=True, text=True)
    dat = inp_path.parent / f"{stem}.dat"
    if not dat.exists():
        raise RuntimeError(
            f"CalculiX produced no {dat.name}.\n"
            f"stdout: {result.stdout[-800:]}\nstderr: {result.stderr[-800:]}")
    if dat.stat().st_size == 0:
        raise RuntimeError(f"CalculiX wrote an empty {dat.name} — the solve failed.")
    return dat


# ---------------------------------------------------------------------------
# Stage 3: read the solver's output
# ---------------------------------------------------------------------------

def _dat_block(text: str, header: str) -> str:
    """Extract the rows following a CalculiX .dat block header."""
    pat = re.compile(header + r".*?\n(.*?)(?:\n\s*\n|\Z)", re.IGNORECASE | re.DOTALL)
    m = pat.search(text)
    if not m:
        raise RuntimeError(f"No '{header}' block in the CalculiX .dat output")
    return m.group(1)


_NUM = r"([-+]?\d+\.?\d*(?:[EeDd][-+]?\d+)?)"


def _parse_displacements(dat_path: Path) -> dict[int, IVec3]:
    """Read the displacement field and snap it to integer picometres."""
    block = _dat_block(dat_path.read_text(), r"displacements\s*\(")
    row = re.compile(r"^\s*(\d+)\s+" + _NUM + r"\s+" + _NUM + r"\s+" + _NUM,
                     re.MULTILINE)
    inv = 1 / float(DISP_SCALE)
    out: dict[int, IVec3] = {}
    for m in row.finditer(block):
        vals = [float(m.group(i).replace("D", "E").replace("d", "e")) for i in (2, 3, 4)]
        out[int(m.group(1))] = tuple(round(v * inv) for v in vals)
    if not out:
        raise RuntimeError("Parsed no displacement rows from the CalculiX output")
    return out


def _parse_von_mises(dat_path: Path) -> float:
    """CalculiX's own peak von Mises stress, used only as a cross-check."""
    block = _dat_block(dat_path.read_text(), r"stresses\s*\(elem")
    row = re.compile(r"^\s*\d+\s+\d+\s+" + r"\s+".join([_NUM] * 6), re.MULTILINE)
    best = 0.0
    for m in row.finditer(block):
        sxx, syy, szz, sxy, sxz, syz = (
            float(m.group(i).replace("D", "E").replace("d", "e")) for i in range(1, 7))
        vm = math.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
                              + 6 * (sxy ** 2 + sxz ** 2 + syz ** 2)))
        best = max(best, vm)
    if best == 0.0:
        raise RuntimeError("Parsed no stress rows from the CalculiX output")
    return best


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _solve(work_dir: Path, tag: str, coords: dict[int, IVec3],
           elements: dict[int, tuple[int, ...]], fixed_nodes: list[int],
           cloads: dict[int, tuple[Fraction, Fraction, Fraction]],
           mat: Material) -> tuple[dict[int, IVec3], Path]:
    """One CalculiX solve; returns displacements snapped to picometres."""
    inp = work_dir / f"{tag}.inp"
    _write_ccx_inp(inp, coords, elements, fixed_nodes, cloads, mat)
    dat = _run_ccx(inp)
    disps = _parse_displacements(dat)
    missing = set(coords) - set(disps)
    if missing:
        raise RuntimeError(f"CalculiX reported no displacement for {len(missing)} nodes")
    return disps, dat


def run_fea(step_path: Path, geom: BracketGeometry, mat: Material,
            limit_load_n: Fraction, work_dir: Path,
            mesh_size_mm: float, refine: int = 1) -> FEAResult:
    """Mesh, solve, and return the exact discrete problem with the solver's `u`.

    `limit_load_n` is the Limit Load of §3.2; the solve is performed at exactly
    this load, because the Margin of Safety is defined in terms of the stress
    at limit load.

    Iterative refinement (`refine` extra solves)
    --------------------------------------------
    CalculiX prints displacements to seven significant figures, which by itself
    leaves a residual of order 1 N — far too coarse to be a meaningful check.
    So we compute the exact residual `r = K u − f` and ask CalculiX to solve
    `K δ = −r`, then take `u + δ`.  Because `δ` is small, seven significant
    figures of `δ` are many more significant figures of `u`, and each pass
    reduces the residual by roughly three orders of magnitude.

    This is still only the solver proposing a correction: the refined `u` is no
    more trusted than the original, and Lean checks it exactly the same way.
    """
    from . import fem_reference as fr

    work_dir.mkdir(parents=True, exist_ok=True)

    gmsh_inp = work_dir / "mesh.inp"
    _mesh(step_path, gmsh_inp, mesh_size_mm)
    raw_nodes, raw_elements = _parse_gmsh_inp(gmsh_inp)

    coords = _snap_coords(raw_nodes)
    elements = _orient(coords, raw_elements)

    # Exact face selection on the snapped integer coordinates.
    zs = [c[2] for c in coords.values()]
    z_min, z_max = min(zs), max(zs)
    fixed_nodes = sorted(n for n, c in coords.items() if c[2] == z_min)
    loaded_nodes = sorted(n for n, c in coords.items() if c[2] == z_max)
    if not fixed_nodes or not loaded_nodes:
        raise RuntimeError("Could not identify the fixed and loaded faces")

    load_per_node = Fraction(limit_load_n) / len(loaded_nodes)
    zero = (Fraction(0), Fraction(0), Fraction(0))
    applied = {n: (Fraction(0), -load_per_node, Fraction(0)) for n in loaded_nodes}

    disps, dat = _solve(work_dir, "bracket", coords, elements, fixed_nodes,
                        applied, mat)
    sigma_solver = _parse_von_mises(dat)

    result = FEAResult(
        coords=coords, elements=elements, disps=disps,
        fixed_nodes=fixed_nodes, loaded_nodes=loaded_nodes,
        load_per_node=load_per_node, sigma_max_solver=sigma_solver,
        ccx_version=_ccx_version(),
        min_quality=min(element_quality([coords[n] for n in conn])
                        for conn in elements.values()),
    )

    lame = fr.lame_from(mat.E, mat.nu)
    for it in range(refine):
        model = result.to_model(lame)
        res = fr.residuals(model)
        correction = {n: (-res[n][0], -res[n][1], -res[n][2]) for n in res
                      if any(c != 0 for c in res[n])}
        if not correction:
            break
        delta, _ = _solve(work_dir, f"refine{it}", coords, elements, fixed_nodes,
                          {**{n: zero for n in coords}, **correction}, mat)
        result = replace(result, disps={
            n: tuple(result.disps[n][r] + delta[n][r] for r in range(3))
            for n in coords})

    return result
