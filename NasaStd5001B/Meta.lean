/-
  NasaStd5001B.Meta
  Theorems about the structure of NASA-STD-5001B itself.

  These results hold for ALL designs, not just one specific bracket.
  They fall into two groups:

  A. CONCRETE — facts about the numeric values in Table 1.
     Proved by `decide +kernel` or `rfl`, so they are checked by the Lean
     kernel itself and rest on no axiom beyond the standard three.

  B. GENERAL — mathematical properties of the Margin of Safety formula
     and the compliance predicate.  Proved with Mathlib tactics.
     These are the load-bearing formal results for the essay.

  Ground truth: NASA-STD-5001B.md in this repository.
  Each theorem cites the standard section it formalises.
-/

import NasaStd5001B.Defs
import Mathlib.Tactic

namespace NasaStd5001B

-- ===========================================================================
-- A. CONCRETE META-THEOREMS  (Table 1 values)
-- ===========================================================================

/-- Both verification approaches require the same ultimate design factor (7/5 = 1.4).

    Table 1, §4.2.1: Ultimate Design Factor is 1.4 for both prototype and protoflight.
    The choice of approach has NO effect on the ultimate strength requirement;
    the tradeoff concerns yield analysis and qualification testing only. -/
theorem metallic_ult_factors_equal :
    designFactor .prototype .ultimate = designFactor .protoflight .ultimate := by rfl

/-- The prototype approach requires more demanding qualification testing than protoflight.

    Table 1, §4.2.1: prototype QTF = 7/5 (1.4) > protoflight QTF = 6/5 (1.2).
    Prototype offloads yield conservatism onto the test programme. -/
theorem prototype_higher_qual :
    qualTestFactor .protoflight < qualTestFactor .prototype := by decide +kernel

/-- The protoflight approach requires a higher yield design factor than prototype.

    Table 1, §4.2.1: protoflight YDF = 5/4 (1.25) > prototype YDF = 1 (1.0).
    Protoflight compensates for not testing to ultimate loads by requiring higher
    yield margins analytically, to protect the flight hardware during qualification. -/
theorem protoflight_higher_yield :
    designFactor .prototype .yield < designFactor .protoflight .yield := by decide +kernel

/-- Every design factor in Table 1 is strictly positive. -/
theorem all_design_factors_pos : ∀ a : TestApproach, ∀ m : FailureMode,
    0 < designFactor a m := by
  intro a m; cases a <;> cases m <;> decide +kernel

/-- Every qualification test factor is strictly positive. -/
theorem all_qual_factors_pos : ∀ a : TestApproach, 0 < qualTestFactor a := by
  intro a; cases a <;> decide +kernel

/-- Every design factor in Table 1 is at least 1.

    The prototype yield factor of exactly 1.0 is the minimum.
    Factors of safety do not reduce loads. -/
theorem all_design_factors_ge_one : ∀ a : TestApproach, ∀ m : FailureMode,
    1 ≤ designFactor a m := by
  intro a m; cases a <;> cases m <;> decide +kernel

/-- The proof test factor (1.05) exceeds 1.

    Table 1 footnote **, §4.2.1: proof tests load hardware above limit load. -/
theorem proofTestFactor_gt_one : 1 < proofTestFactor := by decide +kernel

-- ===========================================================================
-- B. GENERAL THEOREMS  (Margin of Safety formula)
-- ===========================================================================

/-- CORE CORRECTNESS THEOREM.

    MS ≥ 0  ⟺  allowable ≥ factored stress  (⟺  §4.2d is satisfied)

    Machine-checks that `marginOfSafety` faithfully implements §4.2d:
    "The factored stresses shall not exceed material allowable stresses." -/
theorem margin_nonneg_iff {allowable limitStress df : ℚ}
    (hσ : 0 < limitStress) (hdf : 0 < df) :
    0 ≤ marginOfSafety allowable limitStress df ↔ limitStress * df ≤ allowable := by
  simp only [marginOfSafety, sub_nonneg, one_le_div (mul_pos hσ hdf)]

/-- Higher material allowable stress yields a higher (better) margin, all else equal.

    §4.2d: stronger materials are more likely to satisfy the factored stress requirement.

    NOTE: `hσ` and `hdf` are mathematically required — `a/b` is monotone in `a` only when
    `b > 0`; for `b ≤ 0` the direction reverses (or `b = 0` gives 0/0 = 0 in ℚ). -/
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

/-- A more conservative design factor (larger DF) yields a lower margin, all else equal.

    §4.2a: "design factors...are the minimum required values."  Higher factors are
    more conservative and harder to satisfy. -/
theorem margin_antitone_factor {allowable limitStress df₁ df₂ : ℚ}
    (hσ : 0 < limitStress) (hdf₁ : 0 < df₁) (hallow : 0 ≤ allowable)
    (h : df₁ ≤ df₂) :
    marginOfSafety allowable limitStress df₂ ≤ marginOfSafety allowable limitStress df₁ := by
  unfold marginOfSafety; gcongr

/-- Protoflight yield compliance is strictly stronger than prototype yield compliance.

    Because protoflight yield DF (5/4) > prototype yield DF (1), any design that
    passes the protoflight yield check also passes the prototype yield check. -/
theorem proflight_yield_implies_proto_yield {s : StructuralCheck}
    (hσ : 0 < s.σ_max)
    (hallow : 0 ≤ s.σ_yield_allow)
    (h : 0 ≤ s.yieldMargin)
    (happroach : s.approach = .protoflight) :
    0 ≤ ({ s with approach := .prototype } : StructuralCheck).yieldMargin := by
  simp only [StructuralCheck.yieldMargin, happroach] at h
  simp only [StructuralCheck.yieldMargin]
  -- prototype DF (1) ≤ protoflight DF (5/4), so margin at prototype ≥ margin at protoflight ≥ 0
  exact le_trans h (margin_antitone_factor hσ (by decide +kernel) hallow (by decide +kernel))

/-- Structural monotonicity: reducing stress cannot turn a compliant design non-compliant.

    §4.2d: if σ₁ satisfies factored_stress ≤ allowable, then σ₂ ≤ σ₁ does too. -/
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
  closed under square roots.  These two lemmas move between a bound on the
  square and the compliance predicate, which is what lets a certificate state
  its stress bound as `maxVonMisesSq ≤ σ²` and still conclude about §4.2d.

  They are the reason the certified quantity may be an *upper* bound on the
  real peak stress rather than the peak stress itself: compliance is antitone
  in stress, so proving it at a bound proves it at the truth.
-/

/-- If the design is compliant at `s.σ_max`, it is compliant at any smaller
    positive stress — stated on squares, as the FEM side produces them. -/
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

/-- Contrapositive: if the design already fails at `s.σ_max`, it fails at any
    larger stress.  This is what a non-compliance certificate needs, since
    there the certified quantity is a *lower* bound on the peak stress. -/
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
