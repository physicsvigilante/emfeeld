# First plane-crossing observations (M2A)

An additive `trajectory_event` request in the existing observation packet measures the first **detected transverse crossing** of an imaginary plane. It works for electric and gravitational test particles using the current continuous prescribed-source models. It is not a collision or a charged-plane source, and does not enable motion involving shell/plane sources.

Use `python -m emfeeld.observations PACKET.json --output RESULT.json`. `--validate-only` performs no physics. The scene-v1 format, saved-sample integrator and viewer are unchanged. This candidate remains on the draft branch, unmerged, under the chat-only author-verification policy.

## Authoring request

Add this request to a packet's `observations` array; the packet must also contain its complete existing scene:

```json
{
  "id": "first_x_crossing",
  "type": "trajectory_event",
  "particle_index": 0,
  "condition": {
    "type": "plane",
    "point_m": [0, 0, 0],
    "normal": [1, 0, 0],
    "direction": "negative"
  },
  "occurrence": "first",
  "max_step_s": 0.1,
  "min_normal_speed_m_s": 1e-7,
  "accuracy": {
    "time_atol_s": 1e-6,
    "position_atol_m": 1e-6,
    "velocity_atol_m_s": 1e-7,
    "rtol": 1e-7
  }
}
```

All shown fields are required. `particle_index` refers to the zero-based particle list, not sources. The normal is finite, nonzero and normalized by the parser. The oriented signed distance is `dot(position - point_m, unit_normal)`. Positive means negative-to-positive signed distance; negative means positive-to-negative; either admits both. Reversing the normal reverses those meanings. No executable expressions, paths or arbitrary callbacks can be embedded.

`max_step_s` is a numerical step cap, **not an animation sampling interval**. It must be positive, at most the duration, and at least duration/10000 in this bounded implementation. Its halved value must be representable. Both searches have a 500000-RHS-evaluation safety budget. These are execution limits, not physical laws. Excessive stiffness, very short timescales and extreme magnitudes require separate qualification rather than hiding the limit.

The three absolute accuracy values are strictly positive in the named SI units; relative tolerance is nonnegative. They compare the event states from two runs. Position absolute tolerance also bounds the plane residual and the admitted coordinate roundoff allowance. `min_normal_speed_m_s` is a positive, authored transversality threshold: detected contacts at or below it are rejected as ambiguous, not counted as crossings. It changes admission, never forces or positions.

No `quantity`, `expectation`, `time_s`, nearest-sample policy, second occurrence, radial condition or turning-point request is admitted for this first event contract. Multiple measurements are supplied together in the returned event state. Analytic checks for examples are in their manifest, not used to generate the measured output.

## Search and initial conditions

The search starts at physical time zero and ends at `scene.duration_s`, stopping earlier at the first solver-detected root in the specified direction. A launch on the plane, or with numerically unresolved side, returns `initial_condition_error` without integrating. This avoids inventing a later crossing or silently counting launch as an event. The coordinate filter is scale-aware; it does not shift the particle or plane. It is not an exact geometric predicate.

The optional event adapter integrates the existing equations `r'=v`, `v'=(q/m) E` or `v'=g` with SciPy DOP853. It does not alter `dynamics.integrate`, `Scene.trajectories`, their saved arrays or their defaults. Each unique event request performs two terminal searches: first with the established rtol=1e-10, position atol=1e-9 m and velocity atol=1e-9 m/s; then with these three tolerances divided by ten and `max_step_s` halved. No automatic retries are made. An early known failure can end the attempt before the second search.

Root location uses native `solve_ivp(events=...)`, including its continuous-output root evaluation and `y_events`. It is **not nearest-frame selection or fitting to saved trajectory samples**. The existing solver's continuous interpolation is numerical, not an exact analytic orbit.

For matching detections, compare time, position and velocity componentwise using `abs(base-refined) <= absolute_tolerance + rtol*max(abs(base),abs(refined))`. Accept only if both roots also meet the plane residual and transversality checks. The refined state is returned. If event presence differs, or the state comparisons fail, report `convergence_error` with no accepted state. Energy diagnostics compare initial and event energies only; they are not whole-trajectory maxima or certified error bounds.

A terminal solve may finish before a later singular encounter, but trial solver stages may go beyond a root before it is found. This is not collision protection or a guarantee of avoiding all singularities. Existing source domain errors remain errors, without softening.

## Results, statuses and reuse

Successful `state` contains `time_s`, `position_m`, `velocity_m_s`, `speed_m_s`, `kinetic_J`, `potential_J` and `total_energy_J`; a `units` map supplies s, m, m/s and J. The report includes normalized plane geometry, particle identity, interval, two pass summaries, refinement differences/tolerances, signed residual, normal speed and energy change. Original authored inputs and scene/packet hashes remain attached. `error_bound` is null.

| Status | Meaning |
|---|---|
| ok | Two searches agree and the detected crossing meets the declared checks |
| no_event | Both successful searches reached the horizon without detecting a qualifying root |
| initial_condition_error | Launch is on or numerically unresolved relative to the plane |
| ambiguous_event | Detected root is too slow/grazing, geometry insufficiently resolved, or horizon ends too near the plane without a located root |
| convergence_error | Presence, time, state or plane residual failed comparison checks |
| unsupported_trajectory | Existing shell/plane-source dynamics prohibition remains in force |
| domain_error | A source evaluation is singular or unresolved |
| numerical_error | Nonfinite output, malformed solver result or known root-finder failure |
| integration_error | Solver failure or evaluation budget exhausted |

Non-success event states are null, with local error details except for the expected `no_event` outcome. Valid probes and other particles remain available. Exact duplicate validated geometry/settings requests share one cached result, including known failures; ids may differ. Caches are packet-local. Different planes/directions/settings get separate searches. Saved-state requests continue to reuse their separate one-run-per-particle cache: mixing events and samples does **not** imply a shared integration. Unrequested particles are not integrated.

For event packets, CLI exit 0/aggregate ok means every request completed with `ok` or `no_event`, and any old static/sample expectations passed. It does not mean every requested crossing exists. A local failure yields exit 1 and a full report; schema/I/O errors yield exit 2. Invalid request schemas reject the entire packet before physics. Known native root failures are reported locally; unexpected programming exceptions propagate.

## Crucial numerical limitation

SciPy detects event sign changes over integration steps; multiple crossings inside one step can be missed. Two step caps agreeing is useful evidence, **not a mathematical guarantee that no earlier crossing was missed**. `no_event` means no detection at the two recorded resolutions, not a proof of physical absence. Tangential touches and zero-normal-speed crossings are not qualified. A tangent that is never detected can therefore appear as `no_event`, which must not be interpreted as "never touches the plane."

Choose a step cap appropriate to the shortest physical timescale, inspect all statuses, and use additional refinements/reference checks for a new arrangement. No scalar expectation or known textbook answer is substituted for a failed event measurement. The fixed numerical tolerance settings and float64 limitations are not certified for atomic scales, arbitrary exponents, singular close encounters or long-duration orbits.

## Examples and reproduction

`examples/plane_events/manifest.json` records eight packets and separately expressed analytic expectations. SC-28 and SOL-26 reuse their prior numerical pilot scenes exactly. For SOL-26, the plane x=9 identifies one on-axis intersection with the zero-potential circle; this is not a general circle/sphere event. The original Sun scene and the previously authored gravitational composition are reused unchanged. Other cases are explicitly illustrative or deliberate failures, not additional textbook coverage or a blind LLM reliability benchmark.

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m emfeeld.observations examples/plane_events/sc-28.json --output output/sc-28-event.json
python -m emfeeld.observations examples/plane_events/ideal_sun.json --output output/sun-events.json
python -m emfeeld.observations examples/plane_events/selection_cases.json --output output/event-errors.json
```

The final command intentionally exits 1. Source-only execution needs `PYTHONPATH=src`. No new dependency, UI feature, radial event, turning point, global minimum search, conductor response or mixed electric/gravity coupling is introduced. SC-158's original flux result remains PARTIAL. See `PLANE_EVENTS_VALIDATION.md` for executed evidence.

Primary API reference: https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html (events, direction, terminal and multiple-roots-per-step limitation). Executed runtime is recorded separately; a documentation citation is not runtime evidence.
