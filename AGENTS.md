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
The physics library and event interfaces support authored field/potential probes,
saved-state measurements and bounded plane/radial/local-turning observations.
Use docs/AUTHORING_WORKFLOW.md, not repeated same-chat pilots labelled "blind".
Validate the exact packet bytes, record their hashes, then execute and verify
explicit outputs. tools/replay_packets.py and verification/v6_published.json
provide a reproducible published-byte regression without a chat attachment.

Historical all-file freeze tests belong on their pinned snapshots. Keep them
unchanged; replay their behavioral cases separately against current code. See
docs/AUTHORING_REPAIR.md for the current suite and exact test-accounting boundary.
New input/path safety checks do not alter physical laws or relax tolerances.
PR #1 is merged. New implementation work belongs on a feature branch and must
remain unmerged until explicit acceptance. Author-run checks do not imply
independent review or human Windows interaction qualification.

## Capability discovery and export integrity
Read docs/CAPABILITIES.md before authoring new packets. Generate the catalogue
with `python -m emfeeld capabilities`; validate the resulting packet normally.
Keep catalogue keys/enums and parser-consistency tests aligned. Never infer a
solved event from CLI exit zero alone. Preserve single-document source provenance
and staged screenshot exports; new capability work must not relax these guards.

## Teaching-first studies
The primary objective is faithful interpretation and verified simulation of
supported systems for teaching and exploration. Textbook answers and their format
are optional, but every explicitly requested supported quantity must be computed
and checked before calling that request answered. Report interpretation fidelity,
physical/numerical correctness, simulation coverage, educational usefulness and
textbook-answer completeness separately; never combine them into one success rate.
Read docs/TEACHING_STUDIES.md. Preserve source givens, assumptions, illustrative
choices, computed inputs and unresolved information separately. A declared
conductor requirement must not become a prescribed uniform sphere silently.
The study V1 variant replaces exactly one source-strength scalar. Do not change
launch conditions, geometry, references or numerical settings to obtain a pass.
Study previews consume recorded arrays, not silently reintegrated trajectories.
Shared potential colour ranges and camera framing are comparison aids; arrows
still show direction only. Teacher acceptance is not inferred from rendering.
Keep historical evidence untouched. CI must cover relevant PRs targeting main
and relevant main pushes; do not return to foundation-branch-only triggers.
