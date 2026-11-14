# Saved-trajectory observation qualification — 2026-11-13

## Identity, scope and acceptance

Parent: `7eb824aaa3cbe392d9e5591bfa3a9466c36e2202`, tree `e2f8746d4c5fb854aedfc79c88a5c5390a3e8fbd`. This records the approved first milestone: named saved-state measurements through the existing observation packet command. It does not implement event detection or authorize a merge. PR #1 remains draft and unmerged under the approved chat-only acceptance policy. This is author-run verification, not independent review or a blind LLM benchmark.

Production changes are confined to the observation entry point and a new trajectory-sampling adapter. Source formulas, the numerical integrator, scene-v1, old scene CLI, integrals, viewer/playback, dependencies, original examples/tests and historical pilot files remain unchanged. Existing static-only packet reports are preserved. The two live observation documents link to the additive extension; historical validation reports are not rewritten.

## Results

| Check | Result |
|---|---|
| Unchanged parent cumulative suite | 316 passed, no skips |
| First new-test run, before implementation | 46 failed / 38 passed: new capability absent; negative guards already reject |
| First implementation run | 83 passed / 1 new test-fixture failure |
| Final new tests | 97 passed |
| Final cumulative suite, warnings as errors | **413 passed, no skips** |
| Real CLI execution / JSON round trips | 9 packets, 171 requests checked |
| Successful measurements | **166** |
| Deliberate local failures | 2 selection_error, 1 unsupported_trajectory, 2 domain_error |
| Authored reference checks | 129, all passed |
| Integration attempts across the nine packets | 11, including one deliberate singular launch; no per-measurement reruns |
| Prior static reports compared with retained outputs | 11/11 identical JSON objects |
| Original authorability pilot rerun | 11 PASS / 1 PARTIAL / 0 FAIL / 0 ERROR |
| Original pilot strict mode | Exit 1, correctly retaining SC-158 PARTIAL |
| Frozen original pilot files | 34/34 unchanged |
| Compilation | PASS |

The 413 cases comprise 385 normal tests, 19 historical pilot guards and nine existing real-PyVista regressions. All pre-existing assertions and tolerances are retained. No skip or xfail was introduced. The first implementation failure was a new test incorrectly demanding bitwise equality between a numerical free-motion result and an exact analytic integer; its discrepancy was 4.44e-16. That new analytic comparison uses absolute tolerance 1e-13. Bitwise checks against the actual saved numerical arrays remain exact. Failure logs are retained.

## What was checked

Both electric and gravitational scenes were tested against separate uniform-acceleration, central circular-orbit and interior harmonic-oscillator expressions. Recorded packets include SC-99, the inclined MC-36 Coulomb ellipse, the fixed ideal Sun with both independent planets, and a newly authored composition of two overlapping massive spheres plus a uniform gravitational field. The latter uses different test masses and a separately evaluated harmonic solution inside both spheres. No new physical source implementation was needed.

SC-99, MC-36, SC-28 and SOL-26 embed exactly their earlier pilot scenes. The Sun packet embeds exactly the original Sun scene. SC-28/SOL-26 here request saved states, not their crossing events. The new gravitational composition and failure packets are explicitly illustrative, not new PDF/corpus coverage. Uniform/harmonic and Kepler expectations were calculated separately from the engine evaluation, but by the same assistant; they are not independent review.

Repeated position, velocity, speed and energy requests were checked against the existing `Scene.trajectories()` arrays exactly. Instrumented calls establish one integration per selected particle, caching failures as well. Only requested particles are solved; caches are local to each packet. Tests cover multiple times and particles, interleaved static probes, preserved ordering/input data, actual saved times, time offsets, tie-breaking, zero-based references, invalid selectors and quantities, exact-shape expectations, finite output and CLI exit codes.

Exact-time mismatches and nearest-time tolerance failures are explicit and do not integrate. Structural/range errors reject the whole packet before physics runs. Known native solver failure, singular launch, invalid result shapes/times, nonfinite states/diagnostics and unsupported shell/plane motion are reported without discarding unrelated valid results. Unexpected programming RuntimeErrors propagate. Static-only packets and schema-only validation perform no integration; the motion command does not import PyVista or the viewer.

A request for an early sample still depends on a successful run over the declared duration. This step does not salvage partial trajectories, read old NPZ outputs, interpolate new positions, or find crossings/turning points. Solver-native continuous output remains the unchanged mechanism used by DOP853 to fill saved times. Energy diagnostics and authored checks are not certified trajectory error bounds.

## Environment and preservation

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and pytest 9.0.2. The existing optional viewer regressions passed with PyVista 0.48.4 and VTK 9.6.2. The six previously uploaded wheels were verified against their transfer manifest and installed offline only in a container-local directory. No user-machine changes or dependency additions were made. No new screenshot or Windows interaction qualification is claimed.

The prior evidence archive supplied 73 files. Live pinned src, tests, examples, pilots, tools and viewer_tests subtree hashes matched the source copy before edits. Root/document identities were checked against the live tree, with the workflow, gitignore and two historical documents inherited unchanged rather than reconstructed. This is a verified source copy, not a complete Git clone. Seventy reconstructed parent files remain byte-unchanged; only `src/emfeeld/observations.py`, `docs/OBSERVATIONS.md` and `docs/observation_contract_v1.json` change. The repository's original README remains frozen with the pilot. Fifteen files are added. The full tree is verified against the tested files and inherited parent entries before advancing the branch.

## Reproduction and next gate

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m emfeeld.observations examples/trajectory_observations/sc-99.json --output output/sc-99.json
python -m emfeeld.observations examples/trajectory_observations/ideal_sun.json --output output/sun-observations.json
python -m emfeeld.observations examples/trajectory_observations/selection_errors.json --output output/selection-errors.json
python pilots/authorability_v1/run_pilot.py --strict --output output/authorability_v1
```

The selection-errors command intentionally exits 1. The original pilot strict command also intentionally exits 1 for its retained partial flux result. Source-only copies require `PYTHONPATH=src`. Raw logs, outputs, packet-generation/reference script, preservation hashes and source copies are supplied in the chat evidence bundle. Examples carry their expected statuses in the manifest.

The next separate milestone is qualified event/condition observations, not more source laws or visual polish. No claim is made here about closest approach, crossing speed, turning points, autonomous authoring reliability, independent review or Windows mouse/keyboard operation.
