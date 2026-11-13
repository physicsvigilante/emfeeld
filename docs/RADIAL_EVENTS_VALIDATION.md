# M2B radial-event qualification — 2026-11-13

## Identity, scope and workflow

Parent commit: `f82df8089541182ddd121fd00fc9aa6d98ad86d9`, tree `2b68256d3f8851bd5ae3b939c3ad5078c9c8ccee`. The user approved extending first-crossing observations to a fixed positive radius about an authored point. This candidate implements that request only; it does not implement turning points, minimum launch speed, closest approach, additional sources or visual polish. PR #1 remains draft and unmerged. This is author-run verification in the chat, not independent review or an autonomous-LLM benchmark.

Plane and radial events now share `event_core.py`: native terminal search, refinement, state/energy extraction, local errors and caching. `plane_events.py` is a geometry/compatibility adapter; the new `radial_events.py` supplies the radial geometry. Existing plane request bindings and test instrumentation remain intact. The observation parser admits the new data-only condition. No source law, original integrator, saved-sample adapter, scene-v1, viewer, playback or dependency was changed.

## Executed checks

| Check | Result |
|---|---|
| Unchanged parent cumulative suite | **496 passed**, no skips |
| Initial radial tests before implementation | 25 failed / 34 passed; new valid capability absent, malformed requests already rejected |
| Initial plane + radial implementation tests | 142 passed |
| Final new radial tests | **108 passed** |
| Complete cumulative suite, warnings as errors | **604 passed, no skips** |
| Actual command-line packets and JSON round trips | **9 packets / 22 requests checked** |
| Accepted radial event states | **14** |
| Explicit no-event outcomes in example packets | **2** |
| Other successful mixed measurements | 1 saved speed, 1 static potential |
| Deliberate local failures | 1 initial_condition_error, 1 ambiguous_event, 1 unsupported_trajectory, 1 domain_error |
| Historical observation report objects | **28/28 identical**: 11 static, 9 saved-trajectory, 8 plane-event |
| Additional step-cap sweep | 16 event results matched separate reference values |
| Original pilot, strict mode | **11 PASS / 1 PARTIAL / 0 FAIL / 0 ERROR**, expected exit 1 |
| Original 34-file pilot preservation guard | PASS |
| Compilation | PASS |

The cumulative suite comprises 576 headless/configuration tests, 19 historical pilot guards and nine existing real-PyVista regressions. No prior tests, assertions, tolerances or examples were altered. No skip or xfail was introduced. The deliberate local failures are checked outcomes, not accepted trajectories. The initial unsupported-capability failures and all subsequent logs are retained.

## Representative native measurements

These values came from the real observation CLI, not from substitution of reference answers.

| Scene / event | Time (s) | Speed (m/s) |
|---|---:|---:|
| Existing SC-28 scene: first inward radius 1 m about origin | 18.56062575808735 | 0.08628749437041829 |
| Existing SOL-26: outward radius 4 m about (5,0,0) m | 83.87132242424451 | 0.06703563151850973 |
| Illustrative repulsive solid sphere: inward radius 0.5 m | 0.8391811394151882 | 1.4999999983505683 |
| Original Sun scene, second planet: inward radius 179517444840 m | 9888017.490363868 | 26079.722623100803 |
| Original Sun scene, second planet: outward at the same radius | 27072823.027359594 | 26079.72262310077 |
| Existing two-sphere/uniform-gravity scene: inward radius 0.5 m about equilibrium, either test mass | 5.597800141715063 | 0.13108493761514026 |
| Same gravity composition: first outward crossing | 12.208474527983304 | 0.13108493761514034 |

SC-28, SOL-26, the original Sun scene and the earlier gravitational composition embed the exact existing scenes. SC-28's radius-one request is an additional observation, not the original midpoint question. SOL-26 now uses an actual spherical event, not the previous plane surrogate: its planar zero-potential circle extends to a sphere with the same centre/radius. The reported trajectory still exits at x=9 m. The solid-sphere example uses explicitly illustrative, above-threshold launch parameters; it is not a solution for the minimum launch speed or a tangent turning point.

References were expressed separately from engine trajectories: energy and one-dimensional quadratures for SC-28/SOL-26; a radial energy quadrature plus interior asinh expression for solid-sphere penetration; Kepler eccentric-anomaly formulas for the inclined Sun orbit; and an analytic harmonic vector solution plus a scalar root for the gravity composition. The latter observation centre is not either source centre. Both test masses give the same motion. These references were authored by the same assistant, not an independent reviewer or hidden-answer judge.

## Scope of regression and adversarial checks

Tests cover both physical domains, inward/outward/either direction, off-axis passage, arbitrary observation centres, translations/rotations, repeated harmonic crossings, positive-radius launches from a defined centre, on-surface/unresolved launch rejection, strict numeric/schema checks and shared error handling. Inclined elliptical trajectories in both domains match Kepler states. Solid-sphere penetration crosses a continuous density boundary without interpreting it as a collision. A terminal radial-infall measurement completes before a later point-source singularity.

Requested sample density does not affect event state. Exact duplicates reuse two native searches; different radii, centres, directions, particles and tolerances do not collide in caches. Plane/radial/saved requests coexist with separate caches, valid probes survive other failures, and schema validation precedes all physics. Synthetic tests distinguish solver/root-finder failures and bad refinements from unexpected programming exceptions. These synthetic failures are not claimed to have occurred in the physical examples.

A separate step-cap sweep used duration/20, /40, /80 and /400 for SOL-26, solid-sphere penetration, the Sun's inward event and the gravity composition. Each request also applies the shared second-pass halving/tightening. Sixteen resulting states matched their predeclared example reference tolerances. This is bounded numerical evidence, not a global error bound or monotone-convergence guarantee.

### Retained detection limit: a missed entry/exit pair

A deliberately adverse free-motion diagnostic used `x=-2+t`, y=z=0, sphere centre zero and R=0.01 m. Its first inward crossing is analytically at t=1.99 s. With max_step=2.5 s, **both base and refined searches returned no_event**, missing the entry/exit pair inside a step. With max_step=0.005 s, the detected time was **1.990000000000011 s**. Both raw results are retained in `missed_crossing_diagnostic.json`.

This confirms the documented limitation rather than certifying event completeness. `no_event` means no numerical detection, not proof of absence. A step cap appropriate only to the overall simulation duration can be inadequate for a small observation sphere. Tangent contacts and minimum-speed turning points also remain outside scope. The implementation does not add automatic retries or silently replace a missed event with an analytic answer.

## Preservation and environment

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2. Nine existing viewer regressions passed using PyVista 0.48.4 and VTK 9.6.2. Six previously uploaded wheels were checked against their transfer manifest and installed offline into a container-local directory. No user-computer changes, new dependency, license change or Windows interaction test occurred. There is no new screenshot qualification or sphere annotation in the viewer.

The prior evidence archive supplied 102 files, all verified against their Git blob hashes. Those plus four inherited entries reconstruct the pinned published parent tree exactly; all live root/subtree identities were reconciled. This is a verified source copy, not a complete local clone. Ninety-eight reconstructed parent files remain byte-unchanged. Only `plane_events.py`, `observations.py`, `docs/OBSERVATIONS.md` and `docs/observation_contract_v1.json` change. Sixteen files are added. The workflow, gitignore and two inherited historical documents are retained by SHA; the PDF on main is untouched. Historical reports and pilot data remain unchanged.

The published tree is checked against the tested source hashes and unchanged inherited entries before advancing the branch. Full CLI reports, prior/current report comparisons, failure logs, refinement rows, reference-generation/reproduction scripts and verified source copies accompany the chat evidence archive. Earlier evidence is not rewritten into a new pass; SC-158 remains PARTIAL.

## Reproduction and next boundary

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m compileall -q src tests viewer_tests tools pilots
python -m emfeeld.observations examples/radial_events/sol-26.json --output output/radial-sol-26.json
python -m emfeeld.observations examples/radial_events/ideal_sun.json --output output/radial-sun.json
python -m emfeeld.observations examples/radial_events/selection_cases.json --output output/radial-errors.json
python pilots/authorability_v1/run_pilot.py --strict --output output/authorability_v1
```

The final two commands intentionally exit 1. Source-only copies need `PYTHONPATH=src`. The manifest records expected statuses and independent-expression reference values, never substitutes for native measurements. Turning points/closest approach require a separate contract; no new source law or visual feature is needed merely to author another supported radial-crossing arrangement. No merge or independent-review pass is asserted.
