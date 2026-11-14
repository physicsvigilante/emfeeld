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

## Windows LF/CRLF integrity requirement

The first cross-platform candidate run found that Windows Git checkout converted authored JSON LF to CRLF, causing all 10 exact published-byte SHA256 checks to fail although the other 850 tests passed. The CRLF-transformed SHA256 was reproduced exactly from the original packet on Linux. Enforce canonical LF checkout using `.gitattributes` (`*.json text eol=lf`), not by disabling packet hash validation or rewriting expected hashes. Re-run both clean-install platform gates and retain the failed Windows run as evidence.

## Windows hosted OpenGL probe

The LF correction restored Windows headless regression tests (860 current + 18 historical behavioral checks). A subsequent Windows offscreen-render test crashed inside native VTK at `plot.show()` in a hosted runner, before model playback actions. That is a **Windows CI OpenGL qualification failure**, not proof of a physics error or of failure on an interactive desktop.

A bounded follow-up now uses the pinned upstream PyVista headless-display action (v5.2.0; SHA `10e6efb97af3cd1523828f0e22c39f0e4567f3e4`) to install Mesa3D offscreen rendering **only in Windows CI** and direct VTK to OSMesa. This adds no Python runtime dependency or user-PC installation. Numeric, exact-replay and CLI checks precede graphics so native graphics failures cannot hide their outcomes. Preserve the prior access-violation log and do not claim Windows viewer readiness unless real renders and slider tests complete.

