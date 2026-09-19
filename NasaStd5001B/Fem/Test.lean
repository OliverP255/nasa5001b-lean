/-
  NasaStd5001B.Fem.Test

  Checks on the element formulation itself, against values worked out by hand.

  These matter because everything downstream is only as meaningful as the
  definition of `K`.  A certificate proving `‖K u − f‖ ≤ ε` for the *wrong* `K`
  proves nothing about the bracket, and that error would be invisible in the
  generated file — it would still build.  So the properties a linear-elastic
  constant-strain tetrahedron must have are pinned down here, on elements
  small enough to check by hand.

  `tests/test_fem_reference.py` checks the same properties on the Python
  mirror of these definitions, including a full multi-element patch test.

  Every proof is `decide +kernel`: the Lean kernel evaluates the definitions
  and compares, so these tests rest on no axiom beyond the standard three.
-/

import NasaStd5001B.Fem.Assembly

namespace NasaStd5001B.Fem.Test

open NasaStd5001B.Fem

/-- A material with small round constants, so the expected values below can be
    read off by hand.  The real material is generated with λ, μ from E and ν. -/
def m : Material := ⟨2, 3⟩

-- ---------------------------------------------------------------------------
-- The reference tetrahedron
-- ---------------------------------------------------------------------------

/-- Unit tetrahedron on the coordinate axes, with `u = (x, 0, 0)`. -/
def uniaxial : Elem :=
  { p0 := ⟨0, 0, 0⟩, p1 := ⟨1, 0, 0⟩, p2 := ⟨0, 1, 0⟩, p3 := ⟨0, 0, 1⟩
    u0 := ⟨0, 0, 0⟩, u1 := ⟨1, 0, 0⟩, u2 := ⟨0, 0, 0⟩, u3 := ⟨0, 0, 0⟩ }

/-- The Jacobian determinant of the reference tetrahedron is 1. -/
theorem ref_det : uniaxial.kinematics.2.2.2.2 = 1 := by decide +kernel

/-- Shape-function gradients on the reference tetrahedron: `∇N₁ = e₁` and so on,
    with `∇N₀ = −(1,1,1)` since `N₀ = 1 − x − y − z`. -/
theorem ref_gradients :
    uniaxial.kinematics.1 = ⟨-1, -1, -1⟩ ∧
    uniaxial.kinematics.2.1 = ⟨1, 0, 0⟩ ∧
    uniaxial.kinematics.2.2.1 = ⟨0, 1, 0⟩ ∧
    uniaxial.kinematics.2.2.2.1 = ⟨0, 0, 1⟩ := by decide +kernel

/-- Uniaxial *strain* (not stress): ε = (1,0,0,0,0,0), so Hooke's law gives
    σ_xx = λ + 2μ = 8 and σ_yy = σ_zz = λ = 2, with no shear. -/
theorem uniaxial_stress : uniaxial.stress m 1 1 = ⟨8, 2, 2, 0, 0, 0⟩ := by decide +kernel

/-- For that state von Mises reduces to 2μ·ε, so its square is (2·3)² = 36. -/
theorem uniaxial_vm : uniaxial.elemVonMisesSq m 1 1 = 36 := by decide +kernel

-- ---------------------------------------------------------------------------
-- A deliberately distorted element
-- ---------------------------------------------------------------------------

/-- An irregular tetrahedron.  The patch-test property of a constant-strain
    element is shape-independent, so the expected values below hold for *this*
    element exactly as they do for the reference one — which is what makes
    these checks sensitive to an error in the Jacobian or the gradients. -/
def skewP (u0 u1 u2 u3 : Vec3) : Elem :=
  { p0 := ⟨0, 0, 0⟩, p1 := ⟨3, 1, 0⟩, p2 := ⟨1, 4, 1⟩, p3 := ⟨0, 2, 5⟩
    u0 := u0, u1 := u1, u2 := u2, u3 := u3 }

/-- Linear field `u = (2x, 0, 0)` sampled at the nodes: strain must come out as
    exactly ε_xx = 2, giving σ = (16, 4, 4, 0, 0, 0). -/
def skewStretch : Elem := skewP ⟨0, 0, 0⟩ ⟨6, 0, 0⟩ ⟨2, 0, 0⟩ ⟨0, 0, 0⟩

theorem skew_stretch_stress :
    skewStretch.stress m 1 1 = ⟨16, 4, 4, 0, 0, 0⟩ := by decide +kernel

theorem skew_stretch_vm : skewStretch.elemVonMisesSq m 1 1 = 144 := by decide +kernel

/-- Linear field `u = (y, 0, 0)`: pure shear, γ_xy = 1, so σ_xy = μ = 3 and
    every normal stress vanishes.  Von Mises squared is 3μ² = 27. -/
def skewShear : Elem := skewP ⟨0, 0, 0⟩ ⟨1, 0, 0⟩ ⟨4, 0, 0⟩ ⟨2, 0, 0⟩

theorem skew_shear_stress :
    skewShear.stress m 1 1 = ⟨0, 0, 0, 3, 0, 0⟩ := by decide +kernel

theorem skew_shear_vm : skewShear.elemVonMisesSq m 1 1 = 27 := by decide +kernel

-- ---------------------------------------------------------------------------
-- Invariants that must hold for any displacement
-- ---------------------------------------------------------------------------

/-- Rigid-body translation produces no strain, and hence no stress. -/
def translated : Elem := skewP ⟨5, -3, 7⟩ ⟨5, -3, 7⟩ ⟨5, -3, 7⟩ ⟨5, -3, 7⟩

theorem translation_is_stress_free :
    translated.stress m 1 1 = ⟨0, 0, 0, 0, 0, 0⟩ := by decide +kernel

/-- An infinitesimal rotation about the z-axis, `u = (−y, x, 0)`, is also
    stress-free: the antisymmetric part of the displacement gradient drops out
    of the strain. -/
def rotated : Elem := skewP ⟨0, 0, 0⟩ ⟨-1, 3, 0⟩ ⟨-4, 1, 0⟩ ⟨-2, 0, 0⟩

theorem rotation_is_stress_free :
    rotated.stress m 1 1 = ⟨0, 0, 0, 0, 0, 0⟩ := by decide +kernel

/-- An element exerts no net force on itself: `Σ_a (K_e u_e)_a = 0`.

    This is Newton's third law for the element, and it holds for any
    displacement whatever.  It is the check that catches a wrong volume
    factor or a mismatched gradient in the force contraction. -/
def loaded : Elem := skewP ⟨13, -7, 2⟩ ⟨40, 15, -9⟩ ⟨-6, 32, 11⟩ ⟨8, -4, 27⟩

theorem element_self_equilibrates :
    Vec3.add (Vec3.add (loaded.nodalForce m 1 1 0) (loaded.nodalForce m 1 1 1))
      (Vec3.add (loaded.nodalForce m 1 1 2) (loaded.nodalForce m 1 1 3))
      = ⟨0, 0, 0⟩ := by decide +kernel

/-- The unit scales cancel correctly: stating the same physical element in
    micrometres and picometres gives the same stress as stating it in
    millimetres.  A scale slip here would silently rescale every certificate. -/
theorem scales_cancel :
    ({ p0 := ⟨0, 0, 0⟩, p1 := ⟨3000, 1000, 0⟩, p2 := ⟨1000, 4000, 1000⟩,
       p3 := ⟨0, 2000, 5000⟩,
       u0 := ⟨0, 0, 0⟩, u1 := ⟨6 * 10 ^ 12, 0, 0⟩, u2 := ⟨2 * 10 ^ 12, 0, 0⟩,
       u3 := ⟨0, 0, 0⟩ } : Elem).stress m (1 / 1000) (1 / 10 ^ 12)
      = skewStretch.stress m 1 1 := by decide +kernel

end NasaStd5001B.Fem.Test
