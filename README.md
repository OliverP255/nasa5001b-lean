# NASA-STD-5001B in Lean 4

A pipeline that takes a CAD part and a limit load and produces a Lean 4 certificate of whether the part does, or does not, satisfy the strength requirements of NASA-STD-5001B. Both the FEA physics simulation and the safety-test computations are checked in Lean.

![Pipeline: CAD model → mesh → FEA simulation → structural analysis](pipeline.svg)

## Background

NASA's standards set the expectations for how the aerospace industry design, test and manufacture hardware.

NASA-STD-5001B in particular is NASA's standard for structural design, testing, and service-life requirements. It tells us the minimum loads (in terms of design factors and test factors) that parts must withstand to be adequate.

For example, we might perform a structural analysis of a protoflight nose cone. Protoflight means we intend to use it in flight after the test. Among other things, the standard tells us to demonstrate that the design doesn't yield at a load of $1.25\times$ the expected maximum load that will be experienced during flight.

## Why formalise it?

Formalising an engineering standard gives three things:

- **It removes ambiguity.** The same standards can be re-implemented throughout a project, organisation and across many different tools. NASA's standards are used throughout the aerospace industry.

- **Requirements compose.** NASA often has hundreds of engineers working on the same project. They don't all speak to each other and they need to balance their separate design requirements. Formalisation provides a ground truth for those requirements.

- **It makes our informal assumptions explicit.** Formalisation forces us to specify the boundary of what is proved and what is assumed.

I've formalised the structural analysis tests as in NASA-STD-5001B and verified the correctness of the FEA computation. This is just one part of a much larger system. There are still untrusted (unformalised) inputs e.g. the meshing process and the material model still need to be verified and validated.

## Project

### 1. Formalising NASA-STD-5001B

I formalised the structural analysis tests in NASA-STD-5001B. This repo focuses on §3.2, Table 1, and §4.2d.

NasaStd5001B/Meta.lean proves properties of the standard itself, including the main theorem about the correctness of the requirements:

$$MS \geq 0 \iff \sigma_{\text{factored}} \leq \sigma_{\text{allowable}}$$

We also show, for example, that the margin of safety is monotonic since lower stress or a stronger material never results in a lower margin of safety.

### 2. Formalising FEA Simulation

The stress used in the structural analysis comes from a finite-element analysis (FEA) simulation. The physics solver in the pipeline is untrusted because the exact software used by the engineer will vary (we cannot formally verify every simulation engine). So instead, we formally check the correctness of the stress computation that is performed.

Lean assembles the stiffness system $K u = f$ in exact rational arithmetic. The solver (CalculiX) then proposes a solution $u$, and Lean proves that $u$ satisfies the system Lean assembled, to within a tolerance $\varepsilon$. From that verified $u$, Lean computes the stress in every element and takes the maximum. That maximum is the value passed into the structural analysis tests.

By doing this, we split the inputs to the system into the trusted parts (the FEA computation and the structural analysis tests) and the untrusted parts (everything else: mesh quality, material models, etc.).

## In context

This repo is part of a larger aim to make engineering compliance machine-checkable by formalising engineering standards and tools in Lean 4.

To make this possible, the next steps are to formally verify the inputs to the system as best as we can. That means verifying the 3D design, meshing process, the boundary conditions and material model. 

Verifying the 3D design means formalising the geometric dimensioning and tolerancing (GD&T) of the CAD model. If we do that, definitions from the standard such as "detrimental yielding" (as in §3.2) can be made rigorous. I have already worked on formalising tolerancing in my own repo [formal-gdt](https://github.com/OliverP255/formal-gdt).

Complementary to this aim, I’ve written [a short essay](https://www.oliverpryce.xyz/what-happens-when-design-becomes-automated/), discussing what this formal approach to design would look like. 



