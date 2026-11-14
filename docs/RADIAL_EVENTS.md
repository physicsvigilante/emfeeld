# First radial-crossing observations (M2B)

A `trajectory_event` with `condition.type="radial"` measures the first **detected transverse crossing** of a fixed-radius sphere about an authored centre. It works with the existing electric and gravitational source compositions. The centre need not coincide with any source or symmetry centre. This is an imaginary measurement surface, not a charged shell, material contact, collision response or a new force law.

Use the existing command:

```text
python -m emfeeld.observations PACKET.json --output RESULT.json
```

The packet embeds the unchanged scene-v1 model. `--validate-only` performs no physics. Static, saved-sample, plane and radial requests can be interleaved. Existing request meanings and old report objects are preserved. PR #1 remains draft and unmerged under the chat-only author-verification policy.

## Data-only request

Add this to a complete packet's `observations` array:

```json
{
  "id": "first_inward_radius",
  "type": "trajectory_event",
  "particle_index": 0,
  "condition": {
    "type": "radial",
    "center_m": [0, 0, 0],
    "radius_m": 1,
    "direction": "inward"
  },
  "occurrence": "first",
  "max_step_s": 0.05,
  "min_radial_speed_m_s": 1e-7,
  "accuracy": {
    "time_atol_s": 1e-6,
    "position_atol_m": 1e-6,
    "velocity_atol_m_s": 1e-7,
    "rtol": 1e-7
  }
}
```

All displayed fields are required; numeric settings are illustrative, not universal accuracy choices. Radius is strictly positive and finite. Coordinates are three finite JSON numbers in metres. Particle references are zero-based. Unknown keys, booleans as numbers, executable expressions, second occurrences, zero-radius targets and moving centres are rejected before any request is evaluated.

The signed event function is `s = norm(position - center_m) - radius_m`. Inward means positive-to-negative s; outward means negative-to-positive; either permits both. At the located event, radial speed is `dot((position-center)/distance, velocity)`. Its sign is distinct from total speed. Only the declared direction and radial speed above the strictly positive `min_radial_speed_m_s` threshold are accepted. The threshold changes admission, never forces or states.

Launch on the sphere, or with a numerically unresolved inside/outside classification, gives `initial_condition_error`. A launch at the observation **centre** is permitted when the source field is defined there: s=-R is valid. The radial unit vector is needed only at a located positive-radius event, not at every integration stage.

## Numerical search and reuse

The common event core now handles both planes and spheres. Condition adapters supply signed separation, crossing speed and metadata; the shared machinery handles native searches, root-state extraction, error handling, refinement, energy diagnostics and packet-local caching. The plane entry point retains its request/report semantics and test injection bindings. Source laws, `dynamics.integrate`, saved-sample integration, scene-v1 and viewer/playback are unchanged.

Each distinct request runs terminal SciPy DOP853 twice over `[0, scene.duration_s]`, stopping at the first detected root in the specified direction. The second pass halves `max_step_s` and tightens all three established solver tolerances tenfold. Initial values are rtol=1e-10, position atol=1e-9 m, velocity atol=1e-9 m/s. Root values come from native `t_events` and `y_events`, not saved-frame lookup. The solver's own continuous interpolation is numerical, not an analytic solution.

The step cap must lie between duration/10000 and duration, and its half must be representable. Each pass retains the 500000 RHS-evaluation budget. There are no automatic retries. These are execution limits, not physical laws.

Both passes must agree on event presence. Their time, position and velocity must satisfy the authored componentwise absolute-plus-relative comparison. Each root must satisfy the absolute radial residual and coordinate-resolution checks and the radial-speed threshold. The refined state is returned only after those checks. Authored accuracy values are comparisons between two runs, not certified error bounds.

Exact duplicate radial geometry/settings requests share results (including known failures); ids do not affect computation. Different radii, centres, directions, particles or accuracy settings receive separate searches. Plane-event and saved-state caches remain separate. No old NPZ trajectory is consumed and no saved-sample integration is reused as an event search.

## Results and failures

Successful state fields are `time_s`, `position_m`, `velocity_m_s`, `speed_m_s`, `kinetic_J`, `potential_J`, and `total_energy_J`, with explicit SI units. Diagnostics include two pass records, radial speed, signed radial residual, coordinate uncertainty, refinement differences and initial-to-event energy change. Energy change is potential-reference dependent and is not a whole-trajectory maximum or error bound. `error_bound` remains null.

Statuses retain the event vocabulary: `ok`, `no_event`, `initial_condition_error`, `ambiguous_event`, `convergence_error`, `unsupported_trajectory`, `domain_error`, `numerical_error`, and `integration_error`. Non-success states are null. Known local failures preserve unrelated valid measurements; unexpected programming errors propagate. A malformed packet is rejected in its entirety before physics evaluation.

CLI exit 0 means each request completed with `ok` or `no_event` and old authored expectations passed. It does **not** mean every requested event exists. Local failures return exit 1 with the complete report; schema and file errors return exit 2. Radial packets identify `radial_event_contract: 1`; mixed plane/radial packets identify both contracts.

## Geometry and limits

For p, centre c, distance r and requested R, the roundoff filter uses

```text
s = hypot(p-c) - R
e_s = 2*eps*hypot(abs(p)+abs(c)) + 8*eps*(r+R)
```

`eps` is float64 machine epsilon. Initially `abs(s) <= e_s` is unresolved. At a found root, e_s must not exceed the absolute position tolerance. There is no arbitrary physical length floor, shifted surface, softened field, or use of squared distances that can overflow earlier than the norm. This is conservative floating-point filtering, not adaptive exact geometry or certification of extreme exponents.

**First detected does not mean proven first.** SciPy detects sign changes over accepted steps. A straight path can enter and leave a small sphere within one step with the same sign at both endpoints. Both the base and halved-step searches can miss that pair. A retained diagnostic uses free motion `x=-2+t`, R=0.01 m: max_step=2.5 s gives `no_event` in both passes, whereas max_step=0.005 s finds the inward root at 1.99 s. The analytic crossing exists in both cases. Choose the cap for the shortest crossing timescale, not the total duration alone, and verify new arrangements with further refinement or reference checks.

`no_event` is therefore **no detection at the recorded resolutions**, not proof of no intersection or tangential contact. Tangencies, zero-radial-speed contacts, circular-on-surface motion, minimum launch speed, turning points, closest approach and a global minimum distance are not supplied by this contract. A minimum-energy trajectory may only touch a target radius; this is not an accepted transverse crossing.

Existing shell/plane-source trajectory restrictions, singular-source errors, float64 scale limitations and nonrelativistic/test-particle assumptions remain. Trial solver stages can extend past a detected root; terminal measurement is not collision protection. No conductor response, mixed electric/gravity coupling, feedback or radiation is added. The viewer does not draw these observation spheres or annotate event states.

## Reproduction

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m emfeeld.observations examples/radial_events/sol-26.json --output output/radial-sol-26.json
python -m emfeeld.observations examples/radial_events/ideal_sun.json --output output/radial-sun.json
python -m emfeeld.observations examples/radial_events/selection_cases.json --output output/radial-errors.json
```

The last command intentionally exits 1. Source-only execution requires `PYTHONPATH=src`. The nine packets and their separately expressed references are indexed in `examples/radial_events/manifest.json`. See `RADIAL_EVENTS_VALIDATION.md` for actual execution evidence. This is not an autonomous-LLM reliability measurement or independent review.

API reference (not runtime evidence): https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html — event direction, terminal roots, y_events and multiple-crossings-per-step limitation. Runtime qualification used SciPy 1.17.0; the live documentation may describe a newer version.
