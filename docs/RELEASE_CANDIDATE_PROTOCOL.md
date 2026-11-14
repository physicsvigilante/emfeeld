# First-release candidate qualification protocol

Goal: qualify a fresh clean checkout of the existing emfeeld candidate; do not expand physics or viewer scope, merge the draft PR, select a license or claim Windows interactive UI qualification.

## Required evidence

1. Identify the candidate commit and Git tree. Prefer the exact source from a fresh GitHub Actions checkout and retain its `git rev-parse HEAD` plus package environment. Prior local reconstruction alone is not a clean-checkout test.
2. Install `.[dev,view]` from declared dependency ranges, not a mock viewer; record actual installed versions and `pip check`. Qualify both Linux and Windows runner paths where possible.
3. Run current headless tests, historical pilot-v1 **behavioural** tests with only the obsolete all-file freeze assertion explicitly excluded, nine existing real-viewer tests, compilation, and the hash-locked v6 published-packet replay. Historical freeze guards must remain pinned to their original snapshots.
4. Validate and execute the ideal Sun example; execute one new electric-field observation packet. Confirm numerical output and no unexplained errors.
5. Render all eight established 3D viewer scenes with actual PyVista/VTK, and exercise the native slider callbacks. Inspect real screenshots separately; an automated render pass is not visual inspection. Offscreen Windows evidence is not live Windows mouse/keyboard qualification.
6. Preserve raw output, failures, environment, source/tree identity and screenshots. Do not combine shared-baseline test counts from different prior pilot archives.

## Acceptance interpretation

- Any failed physics, export, schema, replay, or packaging check is a release blocker until explained and corrected.
- A Windows offscreen rendering failure blocks claims of Windows viewer readiness, but does not negate a Linux-qualified numerical core. Record it without hiding or redefining it.
- Missing source laws (conductor polarization, moving-source backreaction, full EM, cross-domain qE+mg, unqualified source-shell trajectories) are **deliberately out of scope**, not regressions.
- Numerical event detection is not a proof of complete root detection or global closest approach.
- Unselected repository license, unsupported Python/runtime combinations, and untested human desktop interaction remain explicit caveats. This is a candidate/developer preview, not a claim of production-ready general electromagnetic simulation.
- Keep PR #1 draft and unmerged until explicit user acceptance after viewing the evidence.

The workflow `.github/workflows/release-candidate.yml` is read-only with respect to repository contents (it checks out without persisted credentials and uploads evidence artifacts). It installs dependencies only on hosted CI runners, not on the user's computer.
