"""
Analytic checks on the exact FEM reference implementation.

These are the properties a linear-elastic C3D4 element must have.
These are the same properties NasaStd5001B/Fem/Test.lean checks on the Lean side.

If the two implementations ever drift apart, the generated certificate stops
building.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from pipeline.fem_reference import (
    DiscreteModel, Lame, eval_element, kinematics, lame_from,
    max_abs_residual, stress_bounds,
)

# Reference tetrahedron with unit edges along the axes.
REF_P = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
ONE = Fraction(1)


def test_lame_from_matches_hand_values():
    m = lame_from(Fraction(68900), Fraction(33, 100))
    assert m.lam == Fraction(113685000, 2261)
    assert m.mu == Fraction(3445000, 133)
    # μ = E / (2(1+ν)) recomputed independently
    assert m.mu == Fraction(68900) / (2 * (1 + Fraction(33, 100)))


def test_reference_tet_kinematics():
    g, det = kinematics(REF_P)
    assert det == 1
    assert g[1] == (1, 0, 0) and g[2] == (0, 1, 0) and g[3] == (0, 0, 1)
    assert g[0] == (-1, -1, -1)


def test_uniaxial_strain_stress_and_von_mises():
    """u = (x, 0, 0) gives ε = (1,0,0,0,0,0), so σ = (λ+2μ, λ, λ, 0,0,0)."""
    m = Lame(lam=Fraction(2), mu=Fraction(3))
    u = [(0, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0)]
    ev = eval_element(REF_P, u, m, ONE, ONE)
    assert ev.stress == (8, 2, 2, 0, 0, 0)
    # von Mises of a uniaxial-strain state is 2μ·ε
    assert ev.vm_sq == (2 * m.mu) ** 2 == 36
    assert ev.forces[1] == (Fraction(4, 3), 0, 0)
    assert ev.forces[0] == (Fraction(-4, 3), Fraction(-1, 3), Fraction(-1, 3))


@pytest.mark.parametrize("u", [
    [(5, -3, 7)] * 4,                                    # pure translation
    [(0, 0, 0), (0, 2, 0), (-2, 0, 0), (0, 0, 0)],       # infinitesimal rotation about z
])
def test_rigid_body_motion_is_stress_free(u):
    m = lame_from(Fraction(68900), Fraction(33, 100))
    ev = eval_element(REF_P, u, m, ONE, ONE)
    assert ev.vm_sq == 0
    assert all(c == 0 for c in ev.stress)
    assert all(c == 0 for f in ev.forces for c in f)


def test_element_forces_self_equilibrate():
    """Σ_a (K_e u_e)_a = 0 for any displacement: the element has no net force."""
    m = lame_from(Fraction(68900), Fraction(33, 100))
    p = [(0, 0, 0), (1300, 40, -20), (70, 1100, 30), (-50, 60, 900)]
    u = [(13, -7, 2), (400, 15, -9), (-6, 320, 11), (8, -4, 275)]
    ev = eval_element(p, u, m, Fraction(1, 1000), Fraction(1, 10 ** 9))
    for r in range(3):
        assert sum(f[r] for f in ev.forces) == 0


def _kuhn_box(nx, ny, nz, jitter=True):
    """Structured box meshed into 6 tets per cell, optionally distorted."""
    H = 1000

    def nid(i, j, k):
        return (i * (ny + 1) + j) * (nz + 1) + k

    coords = {}
    for i, j, k in itertools.product(range(nx + 1), range(ny + 1), range(nz + 1)):
        c = [i * H, j * H, k * H]
        if jitter:
            n0 = nid(i, j, k)
            for r, (idx, lim) in enumerate(((i, nx), (j, ny), (k, nz))):
                if 0 < idx < lim:          # keep the outer faces planar
                    c[r] += ((n0 * (31 * r + 17) + 7) % 401) - 200
        coords[nid(i, j, k)] = tuple(c)

    elems, eid = {}, 0
    for i, j, k in itertools.product(range(nx), range(ny), range(nz)):
        for perm in itertools.permutations(range(3)):
            pts, cur = [(i, j, k)], [i, j, k]
            for ax in perm:
                cur[ax] += 1
                pts.append(tuple(cur))
            elems[eid] = tuple(nid(*p) for p in pts)
            eid += 1

    interior = [nid(i, j, k) for i, j, k in
                itertools.product(range(1, nx), range(1, ny), range(1, nz))]
    return coords, elems, interior


def test_patch_test_linear_field_has_zero_residual():
    """A globally linear displacement field must be in exact equilibrium. """
    coords, elems, interior = _kuhn_box(5, 3, 3, jitter=True)
    A = [[3, -1, 2], [1, 4, -2], [-3, 2, 5]]
    disps = {n: tuple(A[r][0] * c[0] + A[r][1] * c[1] + A[r][2] * c[2]
                      for r in range(3))
             for n, c in coords.items()}
    model = DiscreteModel(
        coords=coords, elems=elems, disps=disps,
        fext={}, free=interior,
        mat=lame_from(Fraction(68900), Fraction(33, 100)),
        cs=Fraction(1, 1000), ds=Fraction(1, 10 ** 9),
    )
    assert interior, "the box must have interior nodes to check"
    assert max_abs_residual(model) == 0


def test_stress_bounds_bracket_the_root():
    for q in [Fraction(2), Fraction(123456, 7), Fraction(1), Fraction(10 ** 9, 3)]:
        lo, hi = stress_bounds(q, grid=1000)
        assert lo ** 2 <= q <= hi ** 2
        assert hi - lo == Fraction(1, 1000)


def test_stress_bounds_handles_exact_squares():
    lo, hi = stress_bounds(Fraction(4), grid=1000)
    assert lo == 2 and lo ** 2 == 4
