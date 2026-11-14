# M2A plane-event qualification — 2026-11-13

## Identity, scope and acceptance

Parent: `75a07505b66e4afe4ccb67ab2e180f885264ee84`, tree `9f59e5be39300bd6ebf35861f8feda1c167a32a8`. The user approved M2A and then requested continuation after the interrupted response. This task adds the first detected transverse plane-crossing request, not radial events, turning points or additional source physics. PR #1 remains draft and unmerged. This is author verification in the current chat, not independent review, autonomous-LLM reliability measurement or Windows qualification.

The existing observation command dispatches a new event adapter. That adapter uses native SciPy DOP853 terminal events and the same qE/m or g equation. The old integrator and saved-sample adapter are byte-unchanged. Event searches do not use animation frames. Separate base/refined integrations are explicit in the contract; they do not share the saved-sample solve.

## Results

| Executed check | Result |
|---|---|
| Unchanged parent cumulative suite | 413 passed, no skips |
| New contract tests before implementation | 28 failed / 23 passed (new capability absent; invalid-input rejections already worked) |
| Initial implementation test group | 51 passed |
| Final new plane-event tests | 83 passed |
| Final cumulative suite with warnings as errors | **496 passed, no skips** |
| Real CLI packets and JSON round trips | **8 packets / 16 requests checked** |
| Located plane crossings | 9 accepted event states |
| No-event outcome | 1 explicit no_event |
| Other valid measurements in mixed packets | 1 saved speed, 1 static potential |
| Deliberate local failures | 1 initial_condition_error, 1 ambiguous_event, 1 unsupported_trajectory, 1 domain_error |
| Old report-object comparisons | **20/20 identical**: 11 static and 9 saved-trajectory packets |
| Additional step-cap sweep | 16 event results checked against analytic/reference values |
| Original authorability pilot, strict mode | 11 PASS / 1 PARTIAL / 0 FAIL / 0 ERROR; expected exit 1 |
| Compilation | PASS |

The 496 cases comprise the unchanged 413-test baseline plus 83 new cases. Nine existing real-PyVista regressions are included in the baseline. No old test, assertion, acceptance tolerance, example or pilot outcome was changed; no skip or xfail was introduced. The step-cap sweep used duration/20, /40, /80 and /400, each with the adapter's additional halving and tenfold solver-tolerance refinement. Errors approached floating-point floors and need not decrease monotonically there; no global accuracy guarantee is inferred.

## Representative measured results

These are the existing illustrative numerical instantiations, not new givens from symbolic textbook statements.

| Existing authored scene / event | Time (s) | Speed (m/s) |
|---|---:|---:|
| SC-28: first negative y=0 crossing | 27.320139193856054 | 0.1340712630370193 |
| SOL-26: first positive x=9 crossing | 83.87132242424451 | 0.06703563151850973 |
| Ideal Sun, first planet: first negative x=0 crossing | 7889429.7182414215 | 29785.142169221024 |
| Ideal Sun, second planet: first negative x=0 crossing | 13272273.006342277 | 31958.80592199414 |
| Overlapping massive spheres + uniform field, each test mass | 8.832926363946662 | 0.15681042972189455 |

SC-28 and SOL-26 event speeds were checked against energy formulas. Their times were checked by independently expressed one-dimensional quadratures with substitutions removing the release-point square-root singularity, not by another call to the engine. Sun event times/speeds used Kepler expressions. The gravity composition used its harmonic solution while particles remain inside both spheres. The reference expressions were written by the same assistant, not a separate reviewer.

The four prior pilot/original scene objects reused by event packets (SC-28, SOL-26, ideal Sun and the earlier gravitational composition) are unchanged. The original four-body/general composition capability is not inferred merely from a central orbit. An additional translated/rotated two-charge case passed event-time and vector-state covariance checks. A plane at x=9 in SOL-26 is an on-axis surrogate for that trajectory's circle intersection, not a new spherical/circle event capability.

## Other acceptance checks

Tests cover electric and gravitational coupling, oblique normals and translations, normal scaling/reversal, both crossing directions, earliest qualifying crossing among repeated harmonic passages, no event, initial-on-plane and unresolved geometry, near-grazing rejection, terminal search before a later singularity, source domain errors, solver failure, known root-finder failure, nonfinite/invalid results and strict JSON validation before physics. Injected-failure tests are identified as synthetic; they do not claim those failures occurred in the physical examples.

Exact duplicate event requests perform only two searches. Cache lifetime is one packet; different particles and conditions are independent. Mixed packets preserve valid probes and sample observations. Static/sample-only packets do not invoke the event solver. Saved sample count does not change the measured free-motion event, including a crossing between output frames. Event searches import no viewer. Existing playback and visuals were not extended.

Launch on an observation plane is explicitly rejected, rather than counted as a future hit. The physical shell/plane-source trajectory restriction remains intact even though imaginary plane observations now work. Both searches must agree and satisfy declared state/residual checks for acceptance. no_event is no detection at those numerical resolutions, not a proof that the trajectory never intersects or touches the plane. Tangencies, multiple roots per step, extreme scales and singular encounters retain the limits in `PLANE_EVENTS.md`.

## Environment and preservation

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and pytest 9.0.2. Previously uploaded wheels were transfer-hash checked and installed offline into a container-local directory for existing viewer regressions (PyVista 0.48.4, VTK 9.6.2). No user-computer changes, dependency additions, license changes or new screenshot/Windows qualification occurred.

The earlier evidence archive supplied 88 source/report/configuration files. Their Git blob hashes plus four inherited parent entries reconstruct exactly the live pinned parent tree. This is a verified source copy, not a full local clone. Source laws, dynamics, integrals, scene schema, saved-sample adapter, viewer/playback, dependencies, all historical pilot data and prior tests/reports remain unchanged. Only the existing observation entry point and its two live descriptive documents change; fourteen files are added. The original 34-file pilot freeze check still passes. The source PDF on main is not touched.

The evidence archive includes original and final test logs, CLI reports, the old-report compatibility check, the step-cap sweep, pilot rerun, reference/example generation scripts, a source snapshot and file/tree hashes. Publication checks bind the candidate to those tested files and inherited parent entries. No independent-review pass is claimed.

## Reproduction

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m compileall -q src tests viewer_tests tools pilots
python -m emfeeld.observations examples/plane_events/sc-28.json --output output/sc-28-event.json
python -m emfeeld.observations examples/plane_events/ideal_sun.json --output output/sun-events.json
python -m emfeeld.observations examples/plane_events/selection_cases.json --output output/event-errors.json
python pilots/authorability_v1/run_pilot.py --strict --output output/authorability_v1
```

The selection-cases and strict historical pilot commands intentionally exit 1. Source-only execution requires `PYTHONPATH=src`. The manifest provides expected statuses and separately expressed reference values, never replacements for native measurements. The next distinct candidate may generalize the event contract to radial crossings; no such extension or merge is part of M2A.
