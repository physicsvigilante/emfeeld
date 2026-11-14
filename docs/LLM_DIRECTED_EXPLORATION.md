# Foundational principle: LLM-directed physical exploration

Status: user-approved project direction, recorded in a documentation-only proposal on 2026-11-14. This principle does not activate new physics or enlarge any qualified regime. Detailed implementation decisions are proposed in [Model Identity and Revision Contract V1](MODEL_IDENTITY_REVISIONS_V1.md).

## User's principle

A physical model must be treated as a reusable, versioned object rather than a one-time computation.

Within the declared and qualified physical regime, an LLM should be able to propose changes to component properties, genuine initial conditions, boundary conditions, external inputs and supported structural relationships using stable physical identities.

The engine validates each change, determines whether it requires numerical parameter updating, model reassembly or a different qualified analysis, and computes and verifies the resulting physical state or behavior.

Changes must preserve the original source model and distinguish teacher-authored hypothetical scenarios from source-given facts.

The system should support comparison of verified scenarios and, where qualified, parameter sweeps and sensitivity exploration.

Do not confuse numerical initial guesses with physical initial conditions, static equilibrium changes with time evolution, or presentation interpolation with simulated dynamics.

An admissible baseline does not imply that every parameter revision is admissible. Every modified system must satisfy its applicable physical, mathematical and numerical contracts.

**The primary educational objective is to let teachers explore many meaningful physical questions using the same reusable model, without reauthoring the system or modifying production code for each investigation.**

## Application to emfeeld

The LLM proposes a physical interpretation, a scenario change and an investigation. Trusted implementation validates the authored facts, evaluates supported laws, performs supported mathematics and records limitations. The renderer presents identified results; it does not turn two separate scenarios into an invented physical transition.

A fixed Sun with a different mass is a separate prescribed-field scenario, not a simulation of accretion. Changing a particle's launch velocity changes its physical initial-value problem, not the integrator's initial guess. Changing a probe, numerical tolerance or camera is not a physical revision.

A stable component identity names the same modeled entity across scenarios; it does not certify that a source was interpreted correctly. Hashes establish artifact integrity, not physical correctness or independent review. Hypothetical descendants may differ from the source, provided the source-grounded root is preserved and the divergence is explicit.

Report interpretation fidelity, physical/numerical correctness, simulation coverage, educational usefulness and textbook-answer completeness separately. The last is optional. An explicitly requested supported measurement must still be computed and checked before being reported as fulfilled. A correct refusal, a partial simulation and an incorrect physical interpretation are different outcomes.

These provisions supplement the existing composability and safety guidance. They do not replace historical contracts, change old evaluation scores or constitute merge approval for Teaching Study V1. The shared architectural-review framework supplied by the user remains supporting guidance; its read-only review was a separate completed task.
