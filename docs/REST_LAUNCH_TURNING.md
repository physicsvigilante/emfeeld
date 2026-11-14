# Later radial turning observations from a genuine rest launch

This is an **opt-in extension** to the existing data-only observation command:

```text
python -m emfeeld.observations examples/rest_turning/sc28_later_maximum.json --output output/later-turn.json
```

Add `"initial_policy": "exclude_rest_launch"` to a `trajectory_event` request whose condition is `radial_turning`. Omit that key to retain the original policy, including its rejection of initial radial stationarity. All old inputs/reports remain valid and unchanged. The policy is not accepted for plane, radial-crossing, sample or static requests.

## Request

```json
{
  "id": "later_maximum",
  "type": "trajectory_event",
  "particle_index": 0,
  "condition": {
    "type": "radial_turning",
    "center_m": [0, 0, 0],
    "extremum": "maximum"
  },
  "initial_policy": "exclude_rest_launch",
  "occurrence": "first",
  "max_step_s": 0.1,
  "min_distance_m": 1e-8,
  "min_radial_acceleration_m_s2": 1e-6,
  "accuracy": {
    "time_atol_s": 1e-7,
    "position_atol_m": 1e-7,
    "velocity_atol_m_s": 1e-7,
    "radial_speed_atol_m_s": 1e-8,
    "rtol": 1e-8
  }
}
```

Embed this request alongside the unchanged scene-v1 object. These are illustrative settings, not safe universal defaults. `minimum`, `maximum`, and `either` select the first detected qualifying **positive-time local** extremum. A maximum that happens after the declared duration is not measured by extending the duration automatically.

Eligibility requires **all three initial velocity components exactly zero**, an initial distance above the authored minimum and coordinate uncertainty, and a resolved nonzero initial radial acceleration above the acceleration threshold. There is no epsilon-velocity coercion. Equilibrium launches, initially transverse acceleration with zero radial component, and nonzero-speed orbital apsides remain outside this policy. For those cases no state nudge or hidden time advance is performed.

## How the launch root is excluded

Write `d = position - center`, `r0 = |d(0)| > 0`, and `vr = d.v/|d|`. The new adapter supplies the solver with

```text
h(t, state) = dot(d, velocity)/(r0*t),   t > 0
h(0, initial_state) = initial radial acceleration
```

For an exact rest launch, `velocity(t) = acceleration(0)*t + higher-order terms`, so the displayed value at zero is the continuous limit **along the trajectory**. It must be resolved and nonzero. For positive time and positive radius, `h = |d|*vr/(r0*t)`; the factor is positive, so later roots and their crossing directions are unchanged. This removes only the zero at launch. It is not a finite exclusion interval, replacement initial condition, artificial force, warm-up integration, or change to the physical time origin.

The existing shared event core still makes two native DOP853 terminal searches: the second halves `max_step_s` and tightens solver tolerances tenfold. Each begins at time zero with the exact authored position and velocity. The adapter adds a time-dependent event-predicate hook; the original physical integrator and all other event adapters are unchanged. Accepted states come from native `y_events`, not saved frames. No automatic retry or tolerance relaxation is added.

At a positive-time candidate, the original radial-speed residual, position/time/velocity refinement and nondegenerate radial-acceleration checks still apply. A candidate within the authored absolute time resolution of launch is rejected as ambiguous, rather than skipped. The minimum-distance and acceleration settings reject measurements; they do not soften or clip forces.

## Observation-centre transit is not a source collision

The numerator `d.v` is defined at the observation centre. A particle may pass through that **imaginary point** before a later requested maximum when its physical field is defined there. Such a passage is not automatically a collision. If a requested root is itself at or too close to the observation centre, the radial-direction measurement is rejected as nonsmooth/unresolved; it is not accepted or skipped to manufacture a later minimum. A minimum/either request on the centre-passing SC-28 example demonstrates this rejection.

A physical point-source singularity is different and is not regularized. Shell/plane-source trajectories remain unqualified. There is no collision detection, conductor response, source feedback or mixed electric/gravity coupling.

## Results and limits

Results retain time, position, velocity, speed, kinetic/potential/total energy, distance, radial speed, radial acceleration, extremum, SI units and both numerical search records. They add `initial_policy`, a `rest_launch_turning_contract` report marker, and per-pass `launch_exclusion` diagnostics recording the exact starting state, initial radial acceleration and zero skipped time. Exact duplicate requests share their packet-local pair of searches; legacy, saved-state and different event conditions remain separate.

Known eligibility errors are local `initial_condition_error` results. Source-domain, ambiguity, numerical, integration and refinement failures preserve other valid requests. `no_event` means no detection at the two recorded resolutions, **not proof of absence**. Sign-change event detection can miss multiple roots inside one solver step. Two-pass agreement is not completeness, an earliest-root proof, a global error bound, or a guarantee that a local minimum is the global closest approach. Extremely small/large scales remain limited by float64; overflow/nonfinite arithmetic is rejected. This policy does not find a minimum launch speed.

## Demonstrated SC-28 distinction

The historical pilot-v2 L01 packet remains byte-unchanged and rejected under its original policy. A new packet with the opt-in policy and the **same 40 s scene** returns `no_event`. The later maximum occurs at approximately **54.64027839 s**, so a second explicitly authored packet sets the horizon to **70 s**. It preserves every source and both initial position and velocity. It returns approximately **1.732050808 m** from the origin, at position `(0, -sqrt(3), 0)` m and approximately zero speed. That extra observation is not the original textbook midpoint question.

See [qualification](REST_LAUNCH_TURNING_VALIDATION.md), [descriptive contract](rest_launch_turning_contract_v1.json), and `examples/rest_turning/manifest.json`. This is same-chat author verification, not an independent review or blind reliability benchmark.

The historical pilot-v2 all-file hash guard is intentionally tied to its frozen engine. Reproduce it at commit `c6b5299` (or its documented engine parent); do not update its hashes to bless new source. `tests/test_authorability_v2_compatibility.py` separately replays the unchanged packets and reference checks against the live engine. Historical evidence is not relabelled as a new run.

Upstream API reference (not validation evidence): https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html . The implementation here used installed SciPy 1.17.0; no library upgrade was made.
