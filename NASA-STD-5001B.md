# NASA-STD-5001B, Ground Truth for Formalisation

Source: NASA-STD-5001B, *Structural Design and Test Factors of Safety for Spaceflight Hardware*, approved 08-06-2014. This file contains only the definitions and requirements we are formalising. Text is transcribed verbatim from the standard. Editorial notes are marked **[Note:]**.

---

## 3.2 Definitions

**Detrimental Yielding.** Yielding that adversely affects the form, fit, and function, or integrity of the structure.

**Factored Load or Stress.** The limit load or stress multiplied by the appropriate design or test factor.

**Factors of Safety (Safety Factors).** Multiplying factors to be applied to limit loads or stresses for purposes of analytical assessment (design factors) or test verification (test factors) of design adequacy in strength or stability.

**Failure.** Rupture, collapse, excessive deformation, or any other phenomenon resulting in the inability of a structure to sustain specified loads, pressures, and environments or to function as designed.

**Limit Load.** The maximum anticipated load, or combination of loads that a structure may experience during its design service life under all expected conditions of operation.

**Margin of Safety (MS).**

$$\text{MS} = \frac{\text{Allowable Load (Yield or Ultimate)}}{\text{Limit Load} \times \text{Factor of Safety (Yield or Ultimate)}} - 1$$

Note: Load may refer to force, stress, or strain.

**Proof Test.** A test performed on flight hardware to screen for defects in workmanship and material quality, and to verify structural integrity. Note: Proof tests are performed at a load or pressure in excess of limit load or MDP but below the yield strength of the hardware. Proof tests are performed on each flight unit for structures whose strength is workmanship or fabrication dependent.

**Proof Test Factor.** A multiplying factor to be applied to the limit load or MDP to define the proof test load or pressure.

**Protoflight Hardware.** Hardware that is qualified using a protoflight verification approach.

**Protoflight Test.** A test performed on flight or flight-like hardware (i.e. is built with same drawings, materials and processes as the flight unit) to demonstrate that the design meets structural integrity requirements. The test is performed at loads or pressure in excess of limit load or maximum design pressure but below the yield strength of the structure. When performed on flight structure, the test also verifies the workmanship and material quality of the flight build. Note: Protoflight tests combine elements of prototype and acceptance test programs.

**Protoflight Test Factor.** A multiplying factor to be applied to limit load or MDP to define the protoflight test load or pressure.

**Prototype Hardware.** Hardware of a new design that is produced from the same drawings and using the same materials, tooling, manufacturing processes, inspection methods, and personnel competency levels as will be used for the flight hardware. Note: Prototype hardware is dedicated test hardware that is not intended to be used as a flight unit.

**Prototype Test.** A test conducted using prototype hardware to demonstrate that all structural integrity requirements have been met. Note: Prototype testing is performed at load levels sufficient to demonstrate that the test article will not fail at ultimate design loads.

**Qualification Test.** A test performed to qualify the hardware design for flight. Note: Qualification tests are conducted on a flight-quality structure at load levels sufficient to demonstrate that all structural design requirements have been met. Both protoflight and prototype tests are considered qualification tests.

**Qualification Test Factor.** A multiplying factor to be applied to the limit load or MDP to define the qualification test load or pressure.

**Ultimate Design Load.** The product of the ultimate factor of safety and the limit load.

**Ultimate Strength.** The maximum load or stress that a structure or material can withstand without incurring failure.

**Unfactored Load or Stress.** The limit load or stress before application of any design or test factors.

**Yield Design Load.** The product of the yield factor of safety and the limit load.

**Yield Strength.** The maximum load or stress that a structure or material can withstand without incurring detrimental yielding.

---

## 4.1.1 Prototype versus Protoflight Approaches

The standard accepted practice for verification of launch vehicles and human-rated spaceflight hardware is the prototype approach in which a separate, dedicated test structure, identical to the flight structure, is tested to ultimate loads to demonstrate that the design meets both yield and ultimate factor-of-safety requirements.

An acceptable alternative for verification of spacecraft and science payloads is the protoflight approach, wherein the flight structure is tested to levels above limit load but below yield strength to verify workmanship and demonstrate structural integrity of the flight hardware.

The protoflight verification approach has the advantage that a dedicated test unit is not required, because qualification testing can be performed on the flight hardware. However, a protoflight verification approach does require that margin over flight limit loads be demonstrated by test, therefore, higher yield design factors of safety are required to prevent damage to the flight structure. Under a protoflight verification approach, yield and ultimate modes of failure or structural margins are not directly verified by test.

**Requirement (§4.1.1).** A protoflight test shall be followed by inspection and functionality assessment.

---

## 4.1.2.1 Test Methods

**[Note: guidance text.]** Strength verification tests fall into three basic categories: (1) tests to verify strength of the design (qualification), (2) tests to verify strength models, and (3) tests to screen for workmanship and material defects in the flight articles (acceptance or proof).

**Requirement (§4.1.2.1a).** The strength verification program shall be approved by the responsible Technical Authority.

**Requirement (§4.1.2.1b).** The magnitude of the static test loads shall be equivalent to limit loads multiplied by the qualification, acceptance, or proof test factor.

**Requirement (§4.1.2.1c).** Strength model verification, if required, shall be accomplished over the entire load range.

**Requirement (§4.1.2.1d).** The test article shall be instrumented to provide sufficient test data for correlation with the strength model.

**Requirement (§4.1.2.1e).** Each habitable module, propellant tank, and SRM case shall be proof pressure tested.

**Requirement (§4.1.2.1f).** Departures from test plans and procedures, including failures that occur during testing or are uncovered as part of post-test inspection, shall be documented by a non-conformance report per the approved quality assurance plan.

---

## 4.1.2.2 Test versus Design Factors of Safety

**[Note: guidance text.]** When using the prototype structural verification approach, the minimum ultimate design factors are the same as the required qualification test factors for both metallic and composite/bonded structures, except in the case of discontinuity areas of composite/bonded structures used in safety critical applications.

**Requirement (§4.1.2.2a).** When using the prototype structural verification approach, metallic structures shall be verified to have no detrimental yielding at yield design load before testing to full qualification load levels.

**Requirement (§4.1.2.2b).** When using the protoflight structural verification approach, design factors shall be specified to prevent detrimental yielding of the metallic structure or damage to the composite/bonded flight structure during test.

---

## 4.2 Design and Test Factors of Safety

**Requirement (§4.2a).** The design factors of safety and test factors of this Standard are the minimum required values for NASA spaceflight structures and shall be applied to the limit stress condition, including additive thermal or pressure stresses.

**Requirement (§4.2b).** If pressure or temperature has a relieving or stabilizing effect on the mode of failure, then for analysis or test of that failure mode, the unfactored stresses induced by temperature or the minimum expected pressure shall be used in conjunction with the factored stresses from all other loads.

**Requirement (§4.2c).** Material selection and derivation of material design allowables shall follow the requirements defined in NASA-STD-6016.

**Requirement (§4.2d).** The factored stresses shall not exceed material allowable stresses (yield and ultimate) under the expected temperature, pressure, and other operating conditions.

**Requirement (§4.2e).** The hardware shall be designed to preclude any detrimental yielding under limit loads and, where applicable, under protoflight or proof test loads.

**Requirement (§4.2f).** Applications of design and test factors to the development and verification of a structure shall be accepted by the responsible Technical Authority only when all the constraints and preconditions specified in section 1.3 are met.

**[Note: guidance text.]** Factors of safety on yield are not specified for composite/bonded structures, glass, and bonds for structural glass.

---

## 4.2.1 Metallic Structures

**[Note: guidance text.]** Spaceflight metallic structures can be developed using either the prototype or the protoflight approach.

**Requirement (§4.2.1a).** The minimum design and test factors of safety for metallic structures shall be as specified in Table 1.

**Requirement (§4.2.1b).** Workmanship verification shall be performed for the first flight build and follow-on structures under a prototype test approach and for follow-on structures under a protoflight test approach.

**Requirement (§4.2.1c).** The workmanship verification program shall be approved by the responsible Technical Authority.

### Table 1, Minimum Design and Test Factors for Metallic Structures

| Verification Approach | Ultimate Design Factor | Yield Design Factor | Qualification Test Factor | Proof Test Factor |
|-----------------------|------------------------|---------------------|---------------------------|-------------------|
| Prototype             | 1.4                    | 1.0\*               | 1.4                       | N/A or 1.05\*\*   |
| Protoflight           | 1.4                    | 1.25                | 1.2                       | N/A or 1.05\*\*   |

\* Structure has to be assessed to prevent detrimental yielding during its design service life, acceptance, or proof testing.

\*\* Propellant tanks and SRM cases only.

---

## Derived Relationships

**[Note: these are not stated explicitly in the standard but follow directly from the definitions above. They are what we prove in Lean.]**

**Ultimate Design Load** (from §3.2):

$$\text{Ultimate Design Load} = \text{Limit Load} \times \text{Ultimate Design Factor}$$

**Yield Design Load** (from §3.2):

$$\text{Yield Design Load} = \text{Limit Load} \times \text{Yield Design Factor}$$

**Strength Requirement** (from §4.2d combined with §3.2 Margin of Safety):

§4.2d is satisfied exactly when the Margin of Safety is non-negative for both yield and ultimate failure modes.

**[Note:** this is a *necessary* condition for structural adequacy, not a sufficient one. A structure that satisfies §4.2d may still fail to be adequate under §4.2a–c and §4.2e, under the stability and detrimental-yielding requirements, or under the test requirements of §4.1. Only §4.2d is formalised here, the rest are assumptions. Do not read the theorems below as saying a design "is adequate".**]**

That is:

$$\text{MS}_\text{yield} \geq 0 \quad \text{and} \quad \text{MS}_\text{ultimate} \geq 0$$

Equivalently (expanding the MS formula):

$$\sigma_\text{limit} \times \text{DF}_\text{yield} \leq \sigma_\text{yield,allow}$$
$$\sigma_\text{limit} \times \text{DF}_\text{ultimate} \leq \sigma_\text{ultimate,allow}$$
