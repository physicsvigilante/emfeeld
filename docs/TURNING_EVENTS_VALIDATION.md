# M2C radial turning-point qualification — 2026-11-13

## Identity and scope

Parent: `0831b67538f431aa05ff47f1e1a2cc5223801c90`, tree `1e46853b18ff67a17d1d0118fc7d3d7d3451abf3`. The user approved radial turning-point observations in the existing chat-only workflow. This implements the first detected nondegenerate local distance minimum/maximum, not global closest approach or minimum launch speed. PR #1 remains draft and unmerged. This is author verification, not independent review or an autonomous-LLM benchmark.

The event core now accepts a state-dependent condition adapter in addition to spatial surfaces. The new adapter supplies radial velocity, its derivative and explicit validity checks. The core still owns terminal DOP853 searches, refinement, cache, energy extraction and known failures. Existing plane/radial adapters, source laws, original integrator, saved-sample adapter, scene schema, viewer/playback and dependencies remain unchanged.

## Executed checks

| Check | Result |
|---|---|
| Unchanged parent cumulative suite | 604 passed, no skips |
| New contract tests before implementation | 34 failed / 32 passed; valid new requests unsupported |
| First plane/radial/turning implementation group | 252 passed / 5 new fixture failures |
| New turning tests after fixture repair and extended coverage | 102 passed |
| Full cumulative suite, warnings as errors | **706 passed, no skips** |
| Actual CLI JSON round trips | 10 packets / 26 requests checked |
| Accepted local turning states | 15, including an exact duplicate request |
| Other valid measurements | 1 saved speed, 3 static potentials |
| No-event outcome | 1 explicit no_event |
| Deliberate local failures | 2 ambiguous, 2 initial-condition, 1 source-domain, 1 unsupported-motion |
| Historical report objects | **37/37 identical**: 11 static, 9 saved, 8 plane, 9 radial |
| Additional 16-setting step-cap sweep | 15 accepted/reference-checked; 1 explicit convergence rejection |
| Separate finer-cap follow-up to rejection | Accepted and reference-checked, tolerance unchanged |
| Original pilot, strict mode | 11 PASS, 1 PARTIAL, 0 FAIL, 0 ERROR; expected exit 1 |
| Original 34-file pilot freeze guard | PASS |
| Compilation | PASS |

The 706 tests include all previous 604 tests plus 102 additions. The prior nine real-PyVista tests are included. No old test, tolerance or historical result changed; no skip or xfail was introduced. The five initial new fixture failures were caused by NumPy scalar values in Python-authored JSON dictionaries; those fixtures now use built-in floats/lists. The strict input policy was not relaxed. All logs, including failures, are retained.

## Representative native results

All new packets are explicitly illustrative, not new textbook givens or corpus coverage. References were separately expressed by this same assistant.

| Scene | Local event time (s) | Distance (m) | Speed (m/s) |
|---|---:|---:|---:|
| Free flyby | 1.9999999999999982 | 1 | 1 |
| Repulsive point source | 1.6232252401402296 | 1 | approximately zero |
| Repulsive solid sphere, inside turn | 2.189076712799237 | 0.4999999996722222 | approximately zero |
| Inclined electric/gravitational ellipse, minimum | 3.0286693757852716 | approximately 1 | 1.2247448713915894 |
| Same ellipse, maximum | 11.914435252102043 | approximately 3 | 0.40824829046386163 |
| Two massive spheres + uniform gravity, either test mass, minimum | 0.7853981633974482 | approximately 1 | 2 |
| Same composition, maximum | 2.3561944901923444 | approximately 2 | 1 |

References use free kinematics, uniform acceleration, a Coulomb radial energy integral, an exterior energy integral plus interior hyperbolic solution for the sphere, Kepler eccentric anomaly for rotated ellipses, and a harmonic vector solution for the overlapping-sphere composition. The composition's observation centre is not a source centre. Minima/ maxima are found in both domains without adding source types. The ellipse launches at a nonstationary phase; it is not a silent modification of the original Sun example.

A deliberate non-global example has three stationary distances along a uniformly accelerated parabola. The first local minimum is **1.4701691877741672 m**, while the later minimum is **1.19214407235232 m**. The returned time is the first local event, **1.6415138041150865 s**, not the global answer. The separate polynomial stationary-point calculation is retained.

## Numerical rejection retained

For sphere penetration with max_step = duration/400 = 0.0125 s, the two searches returned times 2.189076465967414 and 2.1890767142077583 s, differing by **2.4824e-7 s**. Their radial distances differed by **1.0751e-7 m**. These exceeded the existing authored comparison thresholds, so the request returned `convergence_error` and no accepted state. The sweep's first driver stopped at that unexpected rejection; its log and script are retained. The completed sweep records the rejection rather than changing tolerances or counting it as a successful measurement.

A separately recorded duration/800 request passed at 2.1890767124851567 s and 0.4999999998082241 m. It is a manual qualification follow-up, not an automatic runtime retry. Neither this result nor the two-pass comparison guarantees monotonic convergence, global accuracy or detection of every extremum. Earlier radial missed-entry/exit evidence remains untouched.

## Additional safeguards checked

Tests cover arbitrary centres, translations/rotations, wrong extremum direction, multiple orbital/harmonic passages, no detection, initial stationarity, a defined-field centre launch, centre passage, actual flat quartic minimum, requested distance/acceleration limits, strict schemas and finite arithmetic. A radial minimum with nonzero tangential velocity is distinguished from a stop. Circular starts remain rejected rather than declared isolated events.

Duplicate conditions share two native searches; changed centres, kinds, particles and numerical settings do not alias. Caches are packet-local and failures are cached. Mixed plane/radial/turning/sample/static requests keep separate searches and preserved input/order. Event states do not depend on saved sample density. Known solver/root failures and synthetic bad refinements reject measurements, while unexpected programming errors propagate. A singular particle and unsupported shell motion do not discard valid unrelated requests.

## Preservation and environment

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and pytest 9.0.2. Existing viewer regressions used PyVista 0.48.4 and VTK 9.6.2. The six previously uploaded wheels were transfer-hash checked and installed offline only in a container-local directory. No user-machine installation, new dependency, license change, new screenshot qualification or Windows interaction test occurred.

118 reconstructed parent files matched their Git blob hashes; together with four inherited entries they reproduce the published parent root. All live root/subtree identities were reconciled. This is a verified source copy, not a complete Git clone. Four existing files change: event_core.py, observations.py and two live observation documents. Sixteen files are added. 114 reconstructed parent files and four inherited entries are unchanged. Original formulas, solver, examples/tests and historical reports/pilot remain intact. The source PDF/main branch is untouched. Publication identity is checked against the tested file hashes plus inherited entries.

## Reproduce

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m compileall -q src tests viewer_tests tools pilots
python -m emfeeld.observations examples/turning_events/sphere_penetration.json --output output/turn.json
python -m emfeeld.observations examples/turning_events/inclined_gravity_orbit.json --output output/orbit-extrema.json
python -m emfeeld.observations examples/turning_events/selection_cases.json --output output/errors.json
python pilots/authorability_v1/run_pilot.py --strict --output output/authorability_v1
```

The final two commands intentionally exit 1. Source-only execution requires PYTHONPATH=src. Full source copies, raw reports, failed logs, compatibility results, analytic reference generation and step sweeps accompany the chat evidence bundle. SC-158 remains PARTIAL. No independent-review pass or merge is asserted. The next useful task is another frozen-engine, end-to-end authoring pilot, not automatic expansion of physical laws or claims of a blind test in this source-aware chat.
