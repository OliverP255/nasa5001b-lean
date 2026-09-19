/-
  NasaStd5001B.Defs
  Formalisation of NASA-STD-5001B, "Structural Design and Test Factors of Safety
  for Spaceflight Hardware", approved 08-06-2014.

  This module encodes:
    · §3.2  Definitions (Margin of Safety formula)
    · §4.2.1 Table 1  Minimum Design and Test Factors for Metallic Structures
    · §4.2d  Compliance criterion: factored stress ≤ allowable

  All numeric factors are represented as exact rationals (ℚ).

  Ground truth: NASA-STD-5001B.md in this repository.
-/

import Mathlib.Data.Rat.Lemmas

namespace NasaStd5001B

-- ---------------------------------------------------------------------------
-- §4.1.1  Verification approaches
-- ---------------------------------------------------------------------------

/-- The two structural verification approaches defined in §4.1.1.
    · Prototype:   dedicated test article tested to ultimate loads.
    · Protoflight: flight hardware tested above limit load but below yield. -/
inductive TestApproach
  | prototype
  | protoflight
  deriving DecidableEq, Repr

/-- The two failure modes for which margins must be checked (§4.2d). -/
inductive FailureMode
  | yield
  | ultimate
  deriving DecidableEq, Repr

-- ---------------------------------------------------------------------------
-- §4.2.1 Table 1  Minimum Design and Test Factors for Metallic Structures
-- ---------------------------------------------------------------------------

/-- Ultimate and yield design factors from Table 1 (§4.2.1).

    | Approach     | Ultimate DF | Yield DF  |
    |--------------|-------------|-----------|
    | Prototype    | 7/5  (1.4)  | 1   (1.0)*|
    | Protoflight  | 7/5  (1.4)  | 5/4 (1.25)|

    * Footnote: structure must still be assessed to prevent detrimental yielding
      during its design service life, acceptance, or proof testing (§4.2e).
      The numeric factor is 1; this does not waive the assessment obligation. -/
def designFactor : TestApproach → FailureMode → ℚ
  | .prototype,   .ultimate => 7 / 5   -- 1.4
  | .prototype,   .yield    => 1       -- 1.0  (see footnote above)
  | .protoflight, .ultimate => 7 / 5   -- 1.4
  | .protoflight, .yield    => 5 / 4   -- 1.25

/-- Qualification test factors from Table 1 (§4.2.1).

    | Approach    | Qual TF    |
    |-------------|------------|
    | Prototype   | 7/5  (1.4) |
    | Protoflight | 6/5  (1.2) | -/
def qualTestFactor : TestApproach → ℚ
  | .prototype   => 7 / 5   -- 1.4
  | .protoflight => 6 / 5   -- 1.2

/-- Proof test factor from Table 1 footnote ** (§4.2.1).

    Table 1: "N/A or 1.05 — Propellant tanks and SRM cases only."

    This value (1.05) applies ONLY to propellant tanks and solid rocket motor (SRM)
    cases.  For all other metallic structures the proof test factor is N/A — no proof
    test is required.  Using this value for general metallic structures would be an
    error; consult §4.2.1 before applying. -/
def proofTestFactor : ℚ := 21 / 20   -- 1.05  (propellant tanks and SRM cases only)

-- ---------------------------------------------------------------------------
-- §3.2  Margin of Safety
-- ---------------------------------------------------------------------------

/-- Margin of Safety as defined in §3.2:

      MS = Allowable / (Limit × FoS) − 1

    where "Load may refer to force, stress, or strain."

    Parameters:
      · allowable   : material allowable stress (Fty or Ftu)
      · limitStress : stress computed by FEA at the limit load (§3.2 Limit Load)
      · df          : design factor (from Table 1 via `designFactor`)

    NOTE: `limitStress` MUST be the stress under the limit load specifically.
    Passing FEA results at any other load value violates the MS definition. -/
def marginOfSafety (allowable limitStress df : ℚ) : ℚ :=
  allowable / (limitStress * df) - 1

-- ---------------------------------------------------------------------------
-- Structural compliance check
-- ---------------------------------------------------------------------------

/-- All inputs needed to check structural adequacy against NASA-STD-5001B §4.2d.

    Fields:
      · σ_max         : conservative upper bound on max von Mises stress at limit
                        load (MPa). Must satisfy σ_max ≥ actual FEA stress.
      · σ_yield_allow : material yield allowable Fty (MPa).
      · σ_ult_allow   : material ultimate allowable Ftu (MPa).
      · approach      : prototype or protoflight verification approach. -/
structure StructuralCheck where
  σ_max         : ℚ
  σ_yield_allow : ℚ
  σ_ult_allow   : ℚ
  approach      : TestApproach

/-- Yield Margin of Safety, using the yield design factor from Table 1. -/
def StructuralCheck.yieldMargin (s : StructuralCheck) : ℚ :=
  marginOfSafety s.σ_yield_allow s.σ_max (designFactor s.approach .yield)

/-- Ultimate Margin of Safety, using the ultimate design factor from Table 1. -/
def StructuralCheck.ultimateMargin (s : StructuralCheck) : ℚ :=
  marginOfSafety s.σ_ult_allow s.σ_max (designFactor s.approach .ultimate)

/-- A design is compliant with §4.2d iff the stress is positive and both margins are non-negative.

    §4.2d: "The factored stresses shall not exceed material allowable stresses
           (yield and ultimate) under the expected temperature, pressure, and
           other operating conditions."

    MS ≥ 0  ⟺  allowable / (limit × DF) ≥ 1  ⟺  limit × DF ≤ allowable
              ⟺  factored stress ≤ allowable  ✓

    The `0 < s.σ_max` guard is required because ℚ division by zero returns 0, making
    marginOfSafety return −1 for any σ_max = 0.  Physically, σ_max = 0 under nonzero
    load indicates a FEA failure; we make this a non-compliance condition explicitly. -/
def StructuralCheck.isCompliant (s : StructuralCheck) : Prop :=
  0 < s.σ_max ∧ 0 ≤ s.yieldMargin ∧ 0 ≤ s.ultimateMargin

instance (s : StructuralCheck) : Decidable s.isCompliant :=
  inferInstanceAs (Decidable (0 < s.σ_max ∧ 0 ≤ s.yieldMargin ∧ 0 ≤ s.ultimateMargin))

end NasaStd5001B
