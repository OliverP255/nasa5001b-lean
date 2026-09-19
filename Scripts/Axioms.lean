/-
  Scripts.Axioms

  Prints the axioms every certificate theorem depends on.

  A Lean proof can be discharged by asking the kernel to believe a compiled
  evaluation rather than checking it, which shows up here as the axiom
  `Lean.ofReduceBool`.  An unfinished proof shows up as `sorryAx`.  Neither is
  visible from a successful `lake build`, so the pipeline runs this and fails
  if either appears, see `BANNED_AXIOMS` in pipeline/run.py.

  The expected output is `[propext, Classical.choice, Quot.sound]` throughout.
-/

import NasaStd5001B

open NasaStd5001B NasaStd5001B.Generated

-- The certificate itself.
#print axioms bracket_certificate
#print axioms residual_ok

-- The properties of the standard the certificate leans on.
#print axioms margin_nonneg_iff
#print axioms compliant_of_lower_stress
#print axioms compliant_of_sq_le
#print axioms not_compliant_of_sq_ge

-- The element formulation.
#print axioms Fem.Test.element_self_equilibrates
#print axioms Fem.Test.skew_shear_stress
#print axioms Fem.Test.scales_cancel
