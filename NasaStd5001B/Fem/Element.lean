/-
  NasaStd5001B.Fem.Element

  The C3D4 element: shape-function gradients, strain, stress, von Mises, and
  the internal nodal forces K_e u_e.  Everything is exact over ℚ.

  Formulation
  -----------
  The element maps the reference tetrahedron by
      x(ξ,η,ζ) = p₀ + ξ(p₁−p₀) + η(p₂−p₀) + ζ(p₃−p₀),
  so with columns c₁ = p₁−p₀, c₂ = p₂−p₀, c₃ = p₃−p₀ the Jacobian is
  J = [c₁ c₂ c₃] and

      det J = c₁ · (c₂ × c₃),
      rows of J⁻¹ = (c₂×c₃, c₃×c₁, c₁×c₂) / det J.

  The reference gradients are ∇N₁ = e₁, ∇N₂ = e₂, ∇N₃ = e₃ and
  ∇N₀ = −(e₁+e₂+e₃), so the physical gradients are the rows of J⁻¹:

      ĝ₁ = c₂×c₃,  ĝ₂ = c₃×c₁,  ĝ₃ = c₁×c₂,  ĝ₀ = −(ĝ₁+ĝ₂+ĝ₃),
      ∇N_a = ĝ_a / det J.

  We keep the *unscaled* ĝ_a because, with integer node coordinates, they are
  integers: the single division by det J is deferred and then cancels against
  the element volume, so each element needs only one rational division.

  Scaling.  Coordinates carry a factor cs (mm per raw unit) and
  displacements a factor ds.  Writing S for the integer strain sums
  Σ_a ĝ_a ⊗ u_a (Voigt, engineering shear), the true strain is

      ε = k·S        with  k = ds / (cs · det J),

  and with V = |det J|·cs³/6 the true internal nodal force is

      f_a = V · Bᵀ_a σ = (sgn(det J) · cs² / 6) · Cᵀ(ĝ_a) σ,

  the volume and one factor of det J having cancelled.
-/

import NasaStd5001B.Fem.Types

namespace NasaStd5001B.Fem

namespace Elem

/-- The four unscaled shape-function gradients ĝ_a together with det J. -/
def kinematics (e : Elem) : Vec3 × Vec3 × Vec3 × Vec3 × ℚ :=
  let c1 := Vec3.sub e.p1 e.p0
  let c2 := Vec3.sub e.p2 e.p0
  let c3 := Vec3.sub e.p3 e.p0
  let g1 := Vec3.cross c2 c3
  let g2 := Vec3.cross c3 c1
  let g3 := Vec3.cross c1 c2
  let g0 := Vec3.neg (Vec3.add g1 (Vec3.add g2 g3))
  (g0, g1, g2, g3, Vec3.dot c1 g1)

/-- The integer strain sums S = Σ_a ĝ_a ⊗ u_a in Voigt order, using
    engineering shear (γ_xy = 2ε_xy). -/
def strainSums (e : Elem) (g0 g1 g2 g3 : Vec3) : Sym6 :=
  { xx := g0.x * e.u0.x + g1.x * e.u1.x + g2.x * e.u2.x + g3.x * e.u3.x
    yy := g0.y * e.u0.y + g1.y * e.u1.y + g2.y * e.u2.y + g3.y * e.u3.y
    zz := g0.z * e.u0.z + g1.z * e.u1.z + g2.z * e.u2.z + g3.z * e.u3.z
    xy := (g0.y * e.u0.x + g0.x * e.u0.y) + (g1.y * e.u1.x + g1.x * e.u1.y)
        + (g2.y * e.u2.x + g2.x * e.u2.y) + (g3.y * e.u3.x + g3.x * e.u3.y)
    yz := (g0.z * e.u0.y + g0.y * e.u0.z) + (g1.z * e.u1.y + g1.y * e.u1.z)
        + (g2.z * e.u2.y + g2.y * e.u2.z) + (g3.z * e.u3.y + g3.y * e.u3.z)
    zx := (g0.z * e.u0.x + g0.x * e.u0.z) + (g1.z * e.u1.x + g1.x * e.u1.z)
        + (g2.z * e.u2.x + g2.x * e.u2.z) + (g3.z * e.u3.x + g3.x * e.u3.z) }

/-- Hooke's law for an isotropic material, applied to the *unscaled* strain
    sums S.  The result is the stress divided by k = ds / (cs · det J),
    its only denominator is the one carried by λ and μ, which keeps the
    numbers small through the contraction below.  scaleOf puts k back. -/
def hookeRaw (m : Material) (s : Sym6) : Sym6 :=
  let tr := s.xx + s.yy + s.zz
  let lt := m.lam * tr
  { xx := lt + 2 * m.mu * s.xx
    yy := lt + 2 * m.mu * s.yy
    zz := lt + 2 * m.mu * s.zz
    xy := m.mu * s.xy
    yz := m.mu * s.yz
    zx := m.mu * s.zx }

/-- The factor k = ds / (cs · det J) relating hookeRaw to the true stress. -/
def scaleOf (cs ds det : ℚ) : ℚ := ds / (cs * det)

/-- The element's unscaled stress, together with its gradients and det J. -/
def rawState (e : Elem) (m : Material) : RawState :=
  let kin := e.kinematics
  let g0 := kin.1
  let g1 := kin.2.1
  let g2 := kin.2.2.1
  let g3 := kin.2.2.2.1
  let det := kin.2.2.2.2
  (hookeRaw m (e.strainSums g0 g1 g2 g3), g0, g1, g2, g3, det)

/-- The element's (constant) Cauchy stress in MPa. -/
def stress (e : Elem) (m : Material) (cs ds : ℚ) : Sym6 :=
  let st := e.rawState m
  let k := scaleOf cs ds st.2.2.2.2.2
  let s := st.1
  ⟨k * s.xx, k * s.yy, k * s.zz, k * s.xy, k * s.yz, k * s.zx⟩

/-- Von Mises stress *squared*, in MPa².

    We keep the square because ℚ is not closed under square roots, the
    comparison against the material allowable is done on squares instead
    (see NasaStd5001B.Meta). -/
def vonMisesSq (s : Sym6) : ℚ :=
  ((s.xx - s.yy) ^ 2 + (s.yy - s.zz) ^ 2 + (s.zz - s.xx) ^ 2) / 2
    + 3 * (s.xy ^ 2 + s.yz ^ 2 + s.zx ^ 2)

/-- Cᵀ(g) σ, the gradient–stress contraction appearing in the nodal force. -/
def contract (g : Vec3) (s : Sym6) : Vec3 :=
  ⟨g.x * s.xx + g.y * s.xy + g.z * s.zx,
   g.y * s.yy + g.x * s.xy + g.z * s.yz,
   g.z * s.zz + g.y * s.yz + g.x * s.zx⟩

end Elem

/-- Von Mises stress squared of an element state, in MPa².

    Von Mises squared is homogeneous of degree 2 in the stress, so it can be
    taken on the unscaled stress and corrected by k² afterwards. -/
def RawState.vonMisesSq (st : RawState) (cs ds : ℚ) : ℚ :=
  Elem.scaleOf cs ds st.2.2.2.2.2 ^ 2 * Elem.vonMisesSq st.1

/-- The internal force (K_e u_e) at local node a of an element state, in N.

    Combining V = |det J|·cs³/6, the gradient ĝ_a / det J and the stress
    factor k = ds/(cs·det J), the volume and two powers of det J cancel
    into the single factor cs·ds / (6·|det J|).

    a is the local node index 0–3, out-of-range indices give the zero vector,
    which cannot arise from a generated model (the generator only ever emits
    0–3) but keeps the function total. -/
def RawState.nodalForce (st : RawState) (cs ds : ℚ) (a : Nat) : Vec3 :=
  let det := st.2.2.2.2.2
  let absDet := if det < 0 then -det else det
  let g := match a with
           | 0 => st.2.1
           | 1 => st.2.2.1
           | 2 => st.2.2.2.1
           | 3 => st.2.2.2.2.1
           | _ => Vec3.zero
  Vec3.smul (cs * ds / (6 * absDet)) (Elem.contract g st.1)

namespace Elem

/-- The element's von Mises stress squared, in MPa². -/
def elemVonMisesSq (e : Elem) (m : Material) (cs ds : ℚ) : ℚ :=
  (e.rawState m).vonMisesSq cs ds

/-- The internal force (K_e u_e) at local node a, in N. -/
def nodalForce (e : Elem) (m : Material) (cs ds : ℚ) (a : Nat) : Vec3 :=
  (e.rawState m).nodalForce cs ds a

end Elem

end NasaStd5001B.Fem
