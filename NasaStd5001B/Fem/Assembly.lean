/-
  NasaStd5001B.Fem.Assembly

  Assembly of the residual r = K u − f and recovery of the peak stress.

  The global stiffness matrix is never formed.  For each free node we gather
  the internal force contributed by every element incident to it and subtract
  the applied load, which gives that node's residual directly.  Constrained
  nodes carry an unknown reaction rather than a known load, so their
  equilibrium says nothing about the solution, the generator omits them.

  Every recursion here is structural on a List.  The kernel has to reduce
  all of it during decide +kernel, and Array operations and well-founded
  recursion do not reduce well there.
-/

import NasaStd5001B.Fem.Element

namespace NasaStd5001B.Fem

/-- Accumulate the internal force at one node over its incident elements. -/
def sumIncident (cs ds : ℚ) : List (RawState × Nat) → Vec3 → Vec3
  | [],            acc => acc
  | (st, a) :: t,  acc => sumIncident cs ds t (Vec3.add acc (st.nodalForce cs ds a))

/-- The residual (K u)_i − f_i at a single node, in N. -/
def nodeResidual (cs ds : ℚ) (n : NodeCheck) : Vec3 :=
  Vec3.sub (sumIncident cs ds n.incid Vec3.zero) n.fext

/-- Running ∞-norm of the residual over a list of nodes. -/
def maxResidual (cs ds : ℚ) : List NodeCheck → ℚ → ℚ
  | [],     acc => acc
  | n :: t, acc => maxResidual cs ds t (qmax acc (nodeResidual cs ds n).maxAbs)

/-- Running maximum of the elementwise von Mises stress, squared. -/
def maxVMSq (cs ds : ℚ) : List RawState → ℚ → ℚ
  | [],      acc => acc
  | st :: t, acc => maxVMSq cs ds t (qmax acc (st.vonMisesSq cs ds))

namespace Model

/-- ‖K u − f‖_∞ over the free nodes, in N.

    This is the quantity the certificate bounds: it measures how far the
    solver's proposed displacement field is from satisfying the discrete
    equilibrium system that Lean itself defines. -/
def maxAbsResidual (M : Model) : ℚ :=
  maxResidual M.cs M.ds M.nodes 0

/-- The largest elementwise von Mises stress over the model, squared (MPa²). -/
def maxVonMisesSq (M : Model) : ℚ :=
  maxVMSq M.cs M.ds M.elems 0

end Model

end NasaStd5001B.Fem
