/-
  NasaStd5001B.Meta
  Theorems about the standard itself.

  They fall into two groups:

  1. CONCRETE, facts about the numeric values in Table 1.
     Proved by 'decide +kernel' or 'rfl', so they are checked only by the Lean
     kernel itself.

  2. GENERAL, mathematical properties of the Margin of Safety formula
     and the compliance predicate.  Proved with Mathlib tactics.

  Ground truth: NASA-STD-5001B.md in this repository.
  Each theorem cites the section of the NASA-STD it formalises.
-/

import NasaStd5001B.Defs
import Mathlib.Tactic

namespace NasaStd5001B


/-- Every design factor in Table 1 is positive. -/
theorem all_design_factors_pos : ∀ a : TestApproach, ∀ m : FailureMode,
    0 < designFactor a m := by
  intro a m; cases a <;> cases m <;> decide +kernel

-- ===========================================================================
-- B. GENERAL THEOREMS  (Margin of Safety formula)
-- ===========================================================================

/-- MS ≥ 0  ⟺  allowable ≥ factored stress  (⟺  4.2d is satisfied)

    Checks that 'marginOfSafety' faithfully implements 4.2d:
    "The factored stresses shall not exceed material allowable stresses." -/
theorem margin_nonneg_iff {allowable limitStress df : ℚ}
    (hσ : 0 < limitStress) (hdf : 0 < df) :
    0 ≤ marginOfSafety allowable limitStress df ↔ limitStress * df ≤ allowable := by
  simp only [marginOfSafety, sub_nonneg, one_le_div (mul_pos hσ hdf)]

/-- Higher material allowable stress yields a higher (better) margin, all else equal.

    §4.2d: stronger materials are more likely to satisfy the factored stress requirement. -/
theorem margin_monotone_allowable {a₁ a₂ limitStress df : ℚ}
    (hσ : 0 < limitStress) (hdf : 0 < df) (h : a₁ ≤ a₂) :
    marginOfSafety a₁ limitStress df ≤ marginOfSafety a₂ limitStress df := by
  unfold marginOfSafety; gcongr


/-- Higher limit stress (worse loading) yields a lower margin, all else equal.

    §3.2: as the limit load increases, the denominator of MS grows, reducing the margin. -/
theorem margin_antitone_stress {allowable σ₁ σ₂ df : ℚ}
    (hσ₁ : 0 < σ₁) (hdf : 0 < df) (hallow : 0 ≤ allowable)
    (h : σ₁ ≤ σ₂) :
    marginOfSafety allowable σ₂ df ≤ marginOfSafety allowable σ₁ df := by
  unfold marginOfSafety; gcongr

/-- A more conservative design factor (larger DF) yields a lower margin with everything else equal. -/
theorem margin_antitone_factor {allowable limitStress df₁ df₂ : ℚ}
    (hσ : 0 < limitStress) (hdf₁ : 0 < df₁) (hallow : 0 ≤ allowable)
    (h : df₁ ≤ df₂) :
    marginOfSafety allowable limitStress df₂ ≤ marginOfSafety allowable limitStress df₁ := by
  unfold marginOfSafety; gcongr

/-- Protoflight yield compliance is strictly stronger than prototype yield compliance. -/

theorem proflight_yield_implies_proto_yield {s : StructuralCheck}
    (hσ : 0 < s.σ_max)
    (hallow : 0 ≤ s.σ_yield_allow)
    (h : 0 ≤ s.yieldMargin)
    (happroach : s.approach = .protoflight) :
    0 ≤ ({ s with approach := .prototype } : StructuralCheck).yieldMargin := by
  simp only [StructuralCheck.yieldMargin, happroach] at h
  simp only [StructuralCheck.yieldMargin]
  exact le_trans h (margin_antitone_factor hσ (by decide +kernel) hallow (by decide +kernel))

/-- Reducing stress cannot turn a compliant design non-compliant. (monotonicity)

    if σ₁ satisfies factored_stress ≤ allowable, and if σ₂ ≤ σ₁, then σ₂ does too. -/
theorem compliant_of_lower_stress {s : StructuralCheck} {σ₂ : ℚ}
    (hσ₂ : 0 < σ₂)
    (_hσ_pos : 0 < s.σ_max)  -- derivable from hc, retained for caller convenience
    (hallow_y : 0 ≤ s.σ_yield_allow)
    (hallow_u : 0 ≤ s.σ_ult_allow)
    (hle : σ₂ ≤ s.σ_max)
    (hc : s.isCompliant) :
    (⟨σ₂, s.σ_yield_allow, s.σ_ult_allow, s.approach⟩ : StructuralCheck).isCompliant := by
  obtain ⟨_, hy, hu⟩ := hc
  simp only [StructuralCheck.yieldMargin, StructuralCheck.ultimateMargin] at hy hu
  constructor
  · exact hσ₂
  constructor
  · show 0 ≤ marginOfSafety s.σ_yield_allow σ₂ (designFactor s.approach .yield)
    -- margin_antitone_stress (hle : σ₂ ≤ s.σ_max) : margin(s.σ_max) ≤ margin(σ₂)
    -- so:  0 ≤ margin(s.σ_max) ≤ margin(σ₂) → 0 ≤ margin(σ₂)
    exact le_trans hy (margin_antitone_stress hσ₂
             (all_design_factors_pos s.approach .yield) hallow_y hle)
  · show 0 ≤ marginOfSafety s.σ_ult_allow σ₂ (designFactor s.approach .ultimate)
    exact le_trans hu (margin_antitone_stress hσ₂
             (all_design_factors_pos s.approach .ultimate) hallow_u hle)

-- ===========================================================================
-- C. BRIDGE TO THE COMPUTED STRESS
-- ===========================================================================

/-
  The finite-element side computes von Mises stress *squared*, because ℚ is not
  closed under square roots.  
  These lemmas mean the certified quantity may be an upper bound on the
  real peak stress rather than the peak stress itself. Compliance is antitone
  in stress, so proving it at a bound proves it at the truth. -/

/-- If the design is compliant at s.σ_max, it is compliant at any smaller
    positive stress. -/
theorem compliant_of_sq_le {s : StructuralCheck} {σ : ℚ}
    (hσ : 0 < σ) (hmax : 0 < s.σ_max)
    (hsq : σ ^ 2 ≤ s.σ_max ^ 2)
    (hallow_y : 0 ≤ s.σ_yield_allow)
    (hallow_u : 0 ≤ s.σ_ult_allow)
    (hc : s.isCompliant) :
    (⟨σ, s.σ_yield_allow, s.σ_ult_allow, s.approach⟩ : StructuralCheck).isCompliant := by
  have hle : σ ≤ s.σ_max := by
    by_contra hgt
    rw [not_le] at hgt
    nlinarith
  exact compliant_of_lower_stress hσ hmax hallow_y hallow_u hle hc

/-- If the design already fails at s.σ_max, it fails at any
    larger stress. -/
theorem not_compliant_of_sq_ge {s : StructuralCheck} {σ : ℚ}
    (hσ : 0 < σ) (hmax : 0 < s.σ_max)
    (hsq : s.σ_max ^ 2 ≤ σ ^ 2)
    (hallow_y : 0 ≤ s.σ_yield_allow)
    (hallow_u : 0 ≤ s.σ_ult_allow)
    (hn : ¬ s.isCompliant) :
    ¬ (⟨σ, s.σ_yield_allow, s.σ_ult_allow, s.approach⟩ : StructuralCheck).isCompliant := by
  intro hc
  have hle : s.σ_max ≤ σ := by
    by_contra hgt
    rw [not_le] at hgt
    nlinarith
  exact hn (compliant_of_lower_stress
    (s := ⟨σ, s.σ_yield_allow, s.σ_ult_allow, s.approach⟩)
    hmax hσ hallow_y hallow_u hle hc)

end NasaStd5001B
