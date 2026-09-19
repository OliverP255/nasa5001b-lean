import Lake
open Lake DSL

package «nasa5001b-lean» where
  leanOptions := #[⟨`autoImplicit, false⟩]

-- Pinned to an exact revision, not `master`.  A certificate is a claim about
-- what a particular Lean and a particular Mathlib accept, so the build has to
-- be reproducible: floating the dependency would mean the proof that was
-- checked and the proof a reader checks are not necessarily the same proof.
require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "8018f6ac06b3ea23aa6f142703ab17a71e57dbe8"

@[default_target]
lean_lib NasaStd5001B where
  roots := #[`NasaStd5001B]
