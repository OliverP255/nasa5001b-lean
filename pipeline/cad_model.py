"""
pipeline/cad_model.py

Parametric cantilever L-bracket in build123d.

The bracket is a rectangular cross-section beam fixed at one end, with a
concentrated load applied at the free end.  Geometry is exported to STEP
for meshing by Gmsh.

Ground truth: NASA-STD-5001B.md §3.2 (Limit Load definition).
"""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import build123d as bd


@dataclass(frozen=True)
class BracketGeometry:
    """Cross-section and length of the cantilever bracket (all in mm)."""
    width:  Fraction   # b, cross-section width
    height: Fraction   # h, cross-section height (in bending direction)
    length: Fraction   # L, cantilever length


@dataclass(frozen=True)
class Material:
    """Linear-elastic isotropic material properties.

    `E` and `nu` are exact rationals, not floats: they define the stiffness
    matrix that Lean assembles, so they have to be the same numbers on both
    sides of the pipeline.  They are converted to decimal only when writing
    the solver's input deck.

    `Fty`/`Ftu` are the material allowables of §4.2d.  NOTE: §4.2c requires
    allowables derived per NASA-STD-6016 (MMPDS).  The values below are
    typical handbook properties for the alloy and are an *assumed input* to
    the certificate, see the trusted-inputs table in the README.
    """
    name:    str
    E:       Fraction  # Young's modulus (MPa)
    nu:      Fraction  # Poisson's ratio
    Fty:     Fraction  # Yield allowable (MPa)
    Ftu:     Fraction  # Ultimate allowable (MPa)


# Standard material database
AL_6061_T6 = Material(
    name="Al_6061-T6",
    E=Fraction(68_900),
    nu=Fraction(33, 100),
    Fty=Fraction(276),
    Ftu=Fraction(310),
)


DEFAULT_GEOMETRY = BracketGeometry(
    width=Fraction(25),
    height=Fraction(12),
    length=Fraction(150),
)


def build_bracket(geom: BracketGeometry) -> bd.Solid:
    """Return a build123d Solid for the cantilever bracket."""
    b = float(geom.width)
    h = float(geom.height)
    L = float(geom.length)
    with bd.BuildPart() as part:
        bd.Box(b, h, L)
    return part.part


def export_step(geom: BracketGeometry, path: Path) -> None:
    """Build the bracket and export to STEP format."""
    solid = build_bracket(geom)
    bd.export_step(solid, str(path))
