# Working on emfeeld

## Goal
A new arrangement of supported sources must be a model-authoring task, not a change to engine dispatch or a new apparatus profile. A new physical law may justify a reusable, tested extension. Favor a small composable physics core; keep visualization independent.

## Required safeguards
- Read README.md, docs/PHYSICS.md and docs/VALIDATION.md before changing physics or reporting capability.
- Preserve explicit SI units, potential references, source assumptions, and domain errors.
- Do not mix electric potential (V) and gravitational potential (J/kg) by adding them. Test-particle coupling is explicit.
- Do not treat a conductor as a prescribed uniform sphere in an external field. Do not claim moving test charges constitute full electrodynamics.
- Never infer forces from the display grid or modify physical values to improve appearance. Label schematic markers and truncated infinite geometry.
- Add cumulative tests with independent analytic expectations, including rejection cases and unfamiliar compositions. Keep old acceptance evidence intact.
- Report tested environment, exact commands, skips, failures and unrun checks. A self-review is not an independent review. A passing numerical suite is not visual qualification.
- Work on a branch. Request independent review before merging implementation candidates. Do not install tools on the user's computer, change licenses, or introduce large dependencies without authorization.

## Current slice
See docs/VALIDATION.md. Initial core tests passed in a Linux Python environment. Optional PyVista runtime, Windows installation, and independent review are pending. Avoid broadening scope until these facts are reconciled and the current candidate is reviewed.
