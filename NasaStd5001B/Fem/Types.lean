/-
  NasaStd5001B.Fem.Types

  Data types for the linear-elastic C3D4 (4-node tetrahedron) finite element
  model that Lean checks independently of the solver.

  Scaling convention
  ------------------
  Node coordinates and nodal displacements are stored as *integer-valued*
  rationals in scaled units, so that every literal in the generated model file
  is an integer and the kernel never normalises a fraction while reading data:

    · coordinates   `p` are in units of `cs` mm   (cs = 1/1000 ⇒ micrometres)
    · displacements `u` are in units of `ds` mm   (ds = 1/10^9 ⇒ picometres)

  `cs` and `ds` are carried by `Model` and reintroduced by `Fem.Element`, which
  works out the true stresses in MPa and the true nodal forces in N.

  All vector operations are plain functions rather than typeclass instances:
  the kernel has to reduce every one of them during `decide +kernel`, and
  direct definitions reduce far more predictably than instance projections.
-/

import Mathlib.Data.Rat.Lemmas

namespace NasaStd5001B.Fem

/-- A vector in ℝ³, represented exactly over ℚ. -/
structure Vec3 where
  x : ℚ
  y : ℚ
  z : ℚ
  deriving Repr, DecidableEq

namespace Vec3

def zero : Vec3 := ⟨0, 0, 0⟩

def add (a b : Vec3) : Vec3 := ⟨a.x + b.x, a.y + b.y, a.z + b.z⟩

def sub (a b : Vec3) : Vec3 := ⟨a.x - b.x, a.y - b.y, a.z - b.z⟩

def neg (a : Vec3) : Vec3 := ⟨-a.x, -a.y, -a.z⟩

def smul (k : ℚ) (a : Vec3) : Vec3 := ⟨k * a.x, k * a.y, k * a.z⟩

def dot (a b : Vec3) : ℚ := a.x * b.x + a.y * b.y + a.z * b.z

def cross (a b : Vec3) : Vec3 :=
  ⟨a.y * b.z - a.z * b.y,
   a.z * b.x - a.x * b.z,
   a.x * b.y - a.y * b.x⟩

end Vec3

/-- Absolute value on ℚ, written with `<` so the kernel reduces it directly
    rather than through the `Lattice`/`abs` hierarchy. -/
def qabs (a : ℚ) : ℚ := if a < 0 then -a else a

/-- Binary max on ℚ, likewise spelled out for kernel reduction. -/
def qmax (a b : ℚ) : ℚ := if a < b then b else a

/-- The largest absolute component of a vector. -/
def Vec3.maxAbs (a : Vec3) : ℚ := qmax (qabs a.x) (qmax (qabs a.y) (qabs a.z))

/-- Isotropic linear-elastic material, stored as Lamé parameters.

    From Young's modulus `E` and Poisson's ratio `ν`:
      λ = E·ν / ((1+ν)(1−2ν))     μ = E / (2(1+ν))
    The generator computes these exactly and emits them as rationals, so that
    the kernel never has to divide while setting up the material. -/
structure Material where
  lam : ℚ
  mu  : ℚ
  deriving Repr, DecidableEq

/-- A symmetric 3×3 tensor in Voigt order.  Used for both strain (with
    *engineering* shear components, γ = 2ε) and stress. -/
structure Sym6 where
  xx : ℚ
  yy : ℚ
  zz : ℚ
  xy : ℚ
  yz : ℚ
  zx : ℚ
  deriving Repr, DecidableEq

/-- One 4-node linear tetrahedron: its four node positions and the
    displacement proposed by the solver at each of those nodes.

    Node ordering is the standard C3D4/Abaqus ordering, matching the
    `*ELEMENT, TYPE=C3D4` connectivity written to CalculiX. -/
structure Elem where
  p0 : Vec3
  p1 : Vec3
  p2 : Vec3
  p3 : Vec3
  u0 : Vec3
  u1 : Vec3
  u2 : Vec3
  u3 : Vec3
  deriving Repr, DecidableEq

/-- Everything about one element that both the residual and the stress recovery
    need: its unscaled stress, its four shape-function gradients, and `det J`.

    Each element appears in the residual check once per node it touches — four
    times over.  Naming this state lets the generated model bind it to a single
    constant per element, so the kernel evaluates each element once and reuses
    the result, rather than recomputing it at every incident node. -/
abbrev RawState := Sym6 × Vec3 × Vec3 × Vec3 × Vec3 × ℚ

/-- The equilibrium check at a single free node: the externally applied load
    at that node, and every (element state, local node index) pair that
    contributes internal force to it. -/
structure NodeCheck where
  fext  : Vec3
  incid : List (RawState × Nat)

/-- A complete discrete model: unit scales, the per-node equilibrium checks,
    and the element states used for the stress recovery.

    The material enters through the element states, which are computed from the
    elements by `Elem.rawState`, so it is not carried separately here. -/
structure Model where
  cs    : ℚ
  ds    : ℚ
  nodes : List NodeCheck
  elems : List RawState

end NasaStd5001B.Fem
