# M2C: local radial turning-point observations

Use the existing data-only observation packet and command:

```text
python -m emfeeld.observations examples/turning_events/point_repulsion.json --output output/turn.json
```

A `trajectory_event` condition with `type="radial_turning"` observes the **first detected nondegenerate local extremum of distance from a fixed authored point**. It works with supported static electric or gravitational compositions. It is not a global closest-approach search, collision rule, conductor response, or inverse minimum-launch-speed solver. No viewer annotation is added.

## Request

Inside the packet's `observations` array:

```json
{
  "id": "closest_local",
  "type": "trajectory_event",
  "particle_index": 0,
  "condition": {
    "type": "radial_turning",
    "center_m": [0, 0, 0],
    "extremum": "minimum"
  },
  "occurrence": "first",
  "max_step_s": 0.05,
  "min_distance_m": 1e-8,
  "min_radial_acceleration_m_s2": 1e-8,
  "accuracy": {
    "time_atol_s": 1e-7,
    "position_atol_m": 1e-7,
    "velocity_atol_m_s": 1e-7,
    "radial_speed_atol_m_s": 1e-8,
    "rtol": 1e-8
  }
}
```

These settings are illustrative SI values, not universal defaults. Every displayed key is required. Unknown keys, executable expressions, booleans as numbers, nonfinite values, duplicate ids, invalid particle indices and unsupported occurrence modes are rejected before physics runs. `extremum` is `minimum`, `maximum`, or `either`. The observation centre need not coincide with any source. The scene remains unchanged scene-v1, embedded in the packet.

`max_step_s` must lie between duration/10000 and duration. The distance and acceleration thresholds and absolute tolerances are positive; relative tolerance is nonnegative. There is no implicit minimum distance in metres. The thresholds reject **measurements**, not forces: no source softening, clipping or collision response is applied. `accuracy` compares event solutions; it does not replace the fixed solver tolerances.

## Numerical meaning

For d = position - center, r = |d| and n = d/r:

```text
radial_speed = n dot velocity
radial_acceleration = n dot acceleration + |velocity - radial_speed*n|^2 / r
```

The native DOP853 event function is radial speed. A negative-to-positive root identifies a local minimum; a positive-to-negative root identifies a local maximum. The acceleration is the existing qE/m or g, not a new source law. The tangential-speed term is essential: a straight-line flyby has a minimum distance even though acceleration is zero and the particle never stops.

The shared event core performs a terminal search, then a second search with half the step cap and tenfold tighter solver tolerances. States come from native `y_events`, not saved animation frames. Acceptance requires matching event presence/classification, small radial-speed residual, a sufficiently nonzero radial acceleration of the proper sign, and agreement in time, position and velocity. Exact duplicate validated requests reuse their packet-local result. Different conditions and saved-sample requests remain separate solves. There are no automatic retries.

The coordinate/norm allowance comes from the radial-crossing adapter with radius zero. The turning adapter estimates conservative floating-point direction, dot-product and cancellation allowances for radial speed/acceleration. Those are arithmetic filters, **not rigorous trajectory-error estimates or arbitrary-exponent guarantees**. Near the centre, relative direction uncertainty grows; a distance at or below `min_distance_m` plus the coordinate allowance is rejected. Arbitrariness in the physical model is not removed by tightening these thresholds.

## Launch and endpoint policy

A launch at the observation centre is rejected, even when the physical field is defined. A launch whose radial speed is zero or unresolved within `radial_speed_atol_m_s` plus its arithmetic allowance is also rejected. This includes starts from rest, exact orbital apsides and exact circular motion. The adapter does not silently advance time to bypass an initial root. Use an explicitly authored nonstationary initial phase for a later event; do not quietly change a textbook initial condition.

A passage through the observation centre is not a smooth radial extremum and remains unqualified. The root finder can encounter the centre during bracketing; that produces a local ambiguous result rather than a fabricated stop. Circular motion and degenerate/flat extrema are not isolated simple roots. A requested extremum with radial acceleration below its threshold is rejected. A horizon ending near zero radial speed without a detected root is ambiguous.

## Results and failures

Successful results return the existing time, position, velocity, speed and energy fields, plus `distance_m`, `radial_speed_m_s`, `radial_acceleration_m_s2`, the actual `extremum`, units, both search records and comparison diagnostics. Kinetic/potential/total energies are joules. Energy drift is an initial-to-event diagnostic, not a certified bound.

Known local outcomes include `no_event`, `initial_condition_error`, `ambiguous_event`, `convergence_error`, `unsupported_trajectory`, `domain_error`, `numerical_error` and `integration_error`. Non-successful measurements return `state: null`; unrelated valid probes and particles remain available. `no_event` is a completed search outcome (CLI success unless other requests fail), not proof of no physical extremum. The detailed per-request statuses must be read. Structural input errors reject the entire packet. Unexpected programming errors propagate.

## Limits that authors must retain

Native sign-change detection can miss multiple roots within a step. Agreement of two searches is not completeness evidence; the returned root is not guaranteed to be the mathematically earliest. Even a correctly located first local minimum may be larger than a later minimum. Endpoints are not compared to find a global minimum. Minimum launch speed still requires an inverse problem with its own contract. Both fields and trajectories remain subject to float64 and source-domain limits. Shell/plane-source trajectories remain rejected.

A real step-cap sweep found a sphere-penetration request whose base/refined states disagreed and were rejected. A separate finer-cap check passed without changing the tolerance. Smaller caps need not produce monotonic errors, especially across a source formula's branch boundary. Do not loosen a tolerance merely to obtain an `ok` status; retain failures and choose justified numerical settings.

See [validation](TURNING_EVENTS_VALIDATION.md), [descriptive machine-readable contract](turning_event_contract_v1.json), and `examples/turning_events/manifest.json`. Existing static, saved-state, plane and radial reports remain unchanged. No independent review, blind reliability measurement or Windows interaction qualification is claimed. PR #1 stays draft and unmerged.

API reference, not validation evidence: https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html (events, direction, terminal, y_events and missed within-step roots).
