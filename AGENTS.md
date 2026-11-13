# Working on emfeeld

## Goal
A new arrangement of supported sources must be a model-authoring task, not a change to engine dispatch or a new apparatus profile. A new physical law may justify a reusable, tested extension. Favor a small composable physics core; keep visualization independent.

## Required safeguards
- Read README.md, docs/PHYSICS.md, docs/VALIDATION.md, docs/CHAT_WORKFLOW_DECISION.md, docs/VIEWER_QUALIFICATION.md and docs/PLAYBACK.md before changing physics or reporting capability.
- Preserve explicit SI units, potential references, source assumptions, and domain errors.
- Do not mix electric potential (V) and gravitational potential (J/kg) by adding them. Test-particle coupling is explicit.
- Do not treat a conductor as a prescribed uniform sphere in an external field. Do not claim moving test charges constitute full electrodynamics.
- Never infer forces from the display grid or modify physical values to improve appearance. Label schematic markers and truncated infinite geometry.
- Add cumulative tests with independent analytic expectations, including rejection cases and unfamiliar compositions. Keep old acceptance evidence intact.
- Report tested environment, exact commands, skips, failures and unrun checks. A self-review is not an independent review. A passing numerical suite is not visual qualification.
- Work on a branch. Follow the explicit acceptance gate in docs/CHAT_WORKFLOW_DECISION.md: documented author verification plus user acceptance for this candidate, not a mandatory Codex handoff or a claim of independent review. Keep the PR unmerged until that acceptance is given. Do not install tools on the user's computer, change licenses, or introduce large dependencies without authorization.

## Current slice
Sample-based playback is implemented and qualified in the recorded Linux environments; see docs/PLAYBACK.md. Source formulas and the solver remain unchanged. Preserve the distinction between display time and physical time. PR #1 remains draft and unmerged.

See docs/VIEWER_QUALIFICATION.md. The numerical suite and real Linux/PyVista offscreen captures passed in the recorded environment. Programmatic VTK time events and image inspection are not Windows desktop/mouse qualification. The preview remains a candidate awaiting user acceptance; no independent review is claimed. Preserve historical evidence and do not broaden physics scope as part of this qualification.
