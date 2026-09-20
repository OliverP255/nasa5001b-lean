"""
pipeline/fem_reference.py

An exact-rational mirror of `NasaStd5001B/Fem/*.lean`.

Every function here computes, in Python `Fraction` arithmetic, exactly what the
corresponding Lean definition computes.  It has two jobs:

  1. Choose the constants that go into the certificate, the residual tolerance
     ε and the stress bounds σ_lo, σ_hi, which requires evaluating the model
     before Lean does.
  2. Serve as a cross-check: the values it produces must agree with Lean's
     (verified by the pipeline) and its stresses must agree with CalculiX's own
     (verified by `check_against_solver`).

Scaling convention (must match Fem/Types.lean):
  · node coordinates are integers in units of `cs` mm
  · nodal displacements are integers in units of `ds` mm
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Sequence

Vec3 = tuple[Fraction, Fraction, Fraction]
IVec3 = tuple[int, int, int]


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Lame:
    """Isotropic elastic constants as exact rationals (MPa)."""
    lam: Fraction
    mu: Fraction


def lame_from(E: Fraction, nu: Fraction) -> Lame:
    """λ = Eν/((1+ν)(1−2ν)),  μ = E/(2(1+ν)), exactly."""
    return Lame(lam=E * nu / ((1 + nu) * (1 - 2 * nu)),
                mu=E / (2 * (1 + nu)))


# ---------------------------------------------------------------------------
# Small integer vector helpers (mirroring Vec3 in Lean)
# ---------------------------------------------------------------------------

def _sub(a: Sequence[int], b: Sequence[int]) -> IVec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Sequence[int], b: Sequence[int]) -> IVec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: Sequence[int], b: Sequence[int]) -> int:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# ---------------------------------------------------------------------------
# Element kernel, mirrors Fem/Element.lean
# ---------------------------------------------------------------------------

def kinematics(p: Sequence[IVec3]) -> tuple[list[IVec3], int]:
    """Unscaled shape-function gradients ĝ_a and det J (all integers)."""
    c1, c2, c3 = _sub(p[1], p[0]), _sub(p[2], p[0]), _sub(p[3], p[0])
    g1, g2, g3 = _cross(c2, c3), _cross(c3, c1), _cross(c1, c2)
    g0 = (-(g1[0] + g2[0] + g3[0]),
          -(g1[1] + g2[1] + g3[1]),
          -(g1[2] + g2[2] + g3[2]))
    return [g0, g1, g2, g3], _dot(c1, g1)


def strain_sums(g: Sequence[IVec3], u: Sequence[IVec3]) -> tuple[int, ...]:
    """S = Σ_a ĝ_a ⊗ u_a in Voigt order with engineering shear."""
    xx = sum(g[a][0] * u[a][0] for a in range(4))
    yy = sum(g[a][1] * u[a][1] for a in range(4))
    zz = sum(g[a][2] * u[a][2] for a in range(4))
    xy = sum(g[a][1] * u[a][0] + g[a][0] * u[a][1] for a in range(4))
    yz = sum(g[a][2] * u[a][1] + g[a][1] * u[a][2] for a in range(4))
    zx = sum(g[a][2] * u[a][0] + g[a][0] * u[a][2] for a in range(4))
    return (xx, yy, zz, xy, yz, zx)


def hooke_raw(m: Lame, s: Sequence[int]) -> tuple[Fraction, ...]:
    """Stress divided by k = ds/(cs·det J); denominator is only that of λ, μ."""
    tr = s[0] + s[1] + s[2]
    lt = m.lam * tr
    return (lt + 2 * m.mu * s[0],
            lt + 2 * m.mu * s[1],
            lt + 2 * m.mu * s[2],
            m.mu * s[3], m.mu * s[4], m.mu * s[5])


def von_mises_sq(s: Sequence[Fraction]) -> Fraction:
    return (((s[0] - s[1]) ** 2 + (s[1] - s[2]) ** 2 + (s[2] - s[0]) ** 2) / 2
            + 3 * (s[3] ** 2 + s[4] ** 2 + s[5] ** 2))


def _contract(g: IVec3, s: Sequence[Fraction]) -> Vec3:
    return (g[0] * s[0] + g[1] * s[3] + g[2] * s[5],
            g[1] * s[1] + g[0] * s[3] + g[2] * s[4],
            g[2] * s[2] + g[1] * s[4] + g[0] * s[5])


@dataclass(frozen=True)
class ElemEval:
    """Everything computed for one element."""
    stress: tuple[Fraction, ...]     # true Cauchy stress, MPa
    vm_sq: Fraction                  # von Mises squared, MPa²
    forces: list[Vec3]               # internal nodal forces, N
    det: int


def eval_element(p: Sequence[IVec3], u: Sequence[IVec3],
                 m: Lame, cs: Fraction, ds: Fraction) -> ElemEval:
    """Evaluate one C3D4 element exactly, mirroring Fem/Element.lean."""
    g, det = kinematics(p)
    raw = hooke_raw(m, strain_sums(g, u))
    k = ds / (cs * det)
    stress = tuple(k * c for c in raw)
    scale = cs * ds / (6 * abs(det))
    forces = [tuple(scale * c for c in _contract(g[a], raw)) for a in range(4)]
    return ElemEval(stress=stress, vm_sq=k ** 2 * von_mises_sq(raw),
                    forces=forces, det=det)


# ---------------------------------------------------------------------------
# Assembly, mirrors Fem/Assembly.lean
# ---------------------------------------------------------------------------

@dataclass
class DiscreteModel:
    """The discrete problem, in the integer scaling the certificate uses."""
    coords: dict[int, IVec3]          # node id → integer coords (units of cs mm)
    elems: dict[int, tuple[int, ...]]  # element id → 4 node ids
    disps: dict[int, IVec3]           # node id → integer displacement (units of ds mm)
    fext: dict[int, Vec3]             # node id → applied load, N
    free: list[int]                   # nodes whose equilibrium is checked
    mat: Lame
    cs: Fraction
    ds: Fraction

    def incidence(self) -> dict[int, list[tuple[int, int]]]:
        """node id → list of (element id, local index)."""
        inc: dict[int, list[tuple[int, int]]] = {n: [] for n in self.coords}
        for eid, conn in self.elems.items():
            for a, n in enumerate(conn):
                inc[n].append((eid, a))
        return inc

    def eval_all(self) -> dict[int, ElemEval]:
        return {eid: eval_element([self.coords[n] for n in conn],
                                  [self.disps[n] for n in conn],
                                  self.mat, self.cs, self.ds)
                for eid, conn in self.elems.items()}


def residuals(model: DiscreteModel,
              evals: dict[int, ElemEval] | None = None) -> dict[int, Vec3]:
    """r_i = (K u)_i − f_i at each checked node, in N."""
    ev = evals if evals is not None else model.eval_all()
    inc = model.incidence()
    out: dict[int, Vec3] = {}
    for n in model.free:
        acc = [Fraction(0), Fraction(0), Fraction(0)]
        for eid, a in inc[n]:
            f = ev[eid].forces[a]
            for r in range(3):
                acc[r] += f[r]
        fe = model.fext.get(n, (Fraction(0),) * 3)
        out[n] = tuple(acc[r] - fe[r] for r in range(3))
    return out


def max_abs_residual(model: DiscreteModel,
                     evals: dict[int, ElemEval] | None = None) -> Fraction:
    res = residuals(model, evals)
    return max((max(abs(c) for c in v) for v in res.values()), default=Fraction(0))


def max_von_mises_sq(model: DiscreteModel,
                     evals: dict[int, ElemEval] | None = None) -> Fraction:
    ev = evals if evals is not None else model.eval_all()
    return max((e.vm_sq for e in ev.values()), default=Fraction(0))


# ---------------------------------------------------------------------------
# Certificate constants
# ---------------------------------------------------------------------------

def choose_epsilon(exact: Fraction) -> Fraction:
    """Smallest power of ten strictly above the exact residual."""
    if exact <= 0:
        return Fraction(1, 10 ** 12)
    e = math.floor(math.log10(float(exact)))
    cand = Fraction(10) ** (e + 1)
    while cand <= exact:          # guard against float log10 edge cases
        cand *= 10
    while cand / 10 > exact:
        cand /= 10
    return cand


def stress_bounds(q: Fraction, grid: int = 1000) -> tuple[Fraction, Fraction]:
    """Rational σ_lo ≤ √q ≤ σ_hi on a 1/`grid` MPa lattice.

    ℚ is not closed under square roots, so the certificate compares squares.
    These bracket the true discrete peak stress to within 1/`grid` MPa.
    """
    if q <= 0:
        return Fraction(0), Fraction(0)
    n = math.isqrt(q.numerator * grid * grid // q.denominator)
    while Fraction(n, grid) ** 2 > q:
        n -= 1
    while Fraction(n + 1, grid) ** 2 <= q:
        n += 1
    return Fraction(n, grid), Fraction(n + 1, grid)


# ---------------------------------------------------------------------------
# Cross-check against the solver's own stress output
# ---------------------------------------------------------------------------

def check_against_solver(model: DiscreteModel,
                         solver_vm_max: float,
                         evals: dict[int, ElemEval] | None = None) -> float:
    """Relative difference between our peak von Mises stress and the solver's"""
    q = max_von_mises_sq(model, evals)
    ours = math.sqrt(float(q))
    if solver_vm_max == 0:
        return math.inf if ours else 0.0
    return abs(ours - solver_vm_max) / solver_vm_max
