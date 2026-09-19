import Lake
open Lake DSL

package «lean-with-sims» where
  leanOptions := #[⟨`autoImplicit, false⟩]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "master"

@[default_target]
lean_lib NasaStd5001B where
  roots := #[`NasaStd5001B]
