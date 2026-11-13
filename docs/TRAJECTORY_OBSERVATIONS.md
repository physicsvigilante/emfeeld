# Data-only saved-trajectory observations v1

## Scope and command

This is the approved first motion-observation milestone after static probes. An LLM can request time, position, velocity, speed, kinetic energy, potential energy and total energy from existing trajectories as data. No question-number or apparatus dispatch is involved. Source laws, the DOP853 integrator, scene-v1, viewer/playback and old scene CLI are unchanged. Crossings, turning points, closest approach and flux are not implemented by this step.

Use the same packet and command as static observations:

```text
python -m emfeeld.observations examples/trajectory_observations/sc-99.json --output output/motion.json
python -m emfeeld.observations examples/trajectory_observations/ideal_sun.json --validate-only
```

The `observation_schema_version` and result version remain 1: `trajectory_sample` is an additive request type, documented separately in `trajectory_sample_contract_v1.json`. Old packets produce the same static results. The static Python API `evaluate_observations(model, requests)` and its `TYPES` constant remain static-only; a trajectory requires an embedded scene and `run_packet(data)`. The separate descriptive static contract links to this extension. Runtime validation is authoritative, not an executable expression parser.

## Complete example

```json
{
  "observation_schema_version": 1,
  "scene": {
    "schema_version": 1,
    "title": "Charge in a uniform field",
    "kind": "electric",
    "sources": [{"type": "uniform", "field_N_C": [1, 0, 0]}],
    "particles": [{"mass_kg": 1, "charge_C": 1,
                   "position_m": [0, 0, 0], "velocity_m_s": [0, 0, 0]}],
    "duration_s": 2,
    "samples": 9,
    "bounds_m": [-1, 3, -1, 1, -1, 1]
  },
  "observations": [
    {"id": "position_at_middle", "type": "trajectory_sample",
     "particle_index": 0, "quantity": "position", "sample_index": 4},
    {"id": "speed_at_one_second", "type": "trajectory_sample",
     "particle_index": 0, "quantity": "speed", "time_s": 1,
     "time_selection": "exact"},
    {"id": "near_time", "type": "trajectory_sample",
     "particle_index": 0, "quantity": "kinetic_energy", "time_s": 0.26,
     "time_selection": "nearest", "max_time_error_s": 0.02},
    {"id": "static_potential", "type": "potential", "position_m": [1, 0, 0]}
  ]
}
```

The first three requests share one solve. At saved time 1 s, position is approximately [0.5, 0, 0] m and speed 1 m/s. The nearest request explicitly selects 0.25 s, not 0.26 s, with signed offset -0.01 s and kinetic energy approximately 0.03125 J. Static potential at [1, 0, 0] is -1 V. These illustrative numbers are not extra givens from a textbook problem.

## Quantities and identity

| quantity | shape | unit, for either physical domain |
|---|---|---|
| time | scalar | s |
| position | [3] | m |
| velocity | [3] | m/s |
| speed | scalar | m/s |
| kinetic_energy | scalar | J |
| potential_energy | scalar | J |
| total_energy | scalar | J |

`particle_index` is a zero-based index in the embedded `scene.particles`, not a source index. The scene hash binds that identity to the input. Every trajectory result carries the particle index/reference and selection. Successful results also carry the selected `sample_index`, actual `time_s`, `time_offset_s`, value, unit, method and `error_bound: null`. `diagnostics_key` points to `trajectory_runs[str(particle_index)]`, containing mass, charge, initial conditions, solver settings, evaluation count and energy-drift diagnostics. Static results retain electric/gravitational field/potential units, unlike the particle energies.

Kinetic energy is the solver's saved kinetic energy. Potential energy is the saved `q V` or `m Phi`, preserving the source reference choices. Total energy is their sum; speed is the magnitude of the saved velocity. No self-force, backreaction or particle-particle interactions are introduced.

## Explicit sample/time selection

Exactly one selector is required:

* **Index:** `sample_index` is an integer from 0 to `scene.samples - 1`. No time-selection fields are allowed. This is the least ambiguous way to select first, middle or last saved states. `time_offset_s` is null because no physical time was requested.
* **Exact time:** specify `time_s` and `time_selection: "exact"`. The float64 time must equal a saved grid entry; there is no tolerance, rounding or implicit nearest lookup. For example, decimal 0.3 need not equal `linspace(0, 1, 11)[3]`, which is 0.30000000000000004 in the tested environment. Such a request returns `selection_error`; choose index 3 or explicitly authorize nearest selection instead.
* **Nearest time:** specify `time_s`, `time_selection: "nearest"` and nonnegative `max_time_error_s`. The nearest saved time must satisfy the stated maximum difference. Exact ties choose the earlier sample. The report preserves requested and actual times and signed `actual-requested` offset. Comparisons use float64 values without an extra hidden tolerance.

Out-of-interval times, invalid indices, missing policies, duplicate ids, wrong shapes, booleans/numeric strings, nonfinite values and unknown fields are invalid input. Requests are not clamped. All request schemas and references are validated before field evaluation or integration. An otherwise valid time that is not saved, or has no nearest sample within tolerance, is a local `selection_error`; other requests can still succeed. Such failed selections do not trigger a solve.

Multiple measurements/times are expressed as multiple uniquely named requests. Static and trajectory requests may be interleaved; output order matches input order. No extra sample count is inferred from measurement requests.

## Reuse, numerical method and failure isolation

For each referenced particle with an acceptable selection, the packet evaluator calls the existing `integrate` once with the same settings as `Scene.trajectories`: DOP853, rtol 1e-10, position atol 1e-9 m, velocity atol 1e-9 m/s and max_step equal to duration/200. The saved grid is `np.linspace(0, duration_s, samples)`. All that particle's measurements reuse the resulting arrays. A failure is cached too. Unrequested particles are not simulated; caches do not persist between packets.

The entire declared duration is integrated, even for an early sample request. This contract does not return an early state from a run that fails later. It does not load prior NPZ files or provide incremental/streaming integration. Those are separate capabilities.

The observation layer never interpolates between samples. The **existing solver** may use its normal continuous-output interpolation to populate `t_eval`; a saved output time is not necessarily an internal adaptive timestep. This step does not change that numerical method.

A valid-looking but unresolved float64 time grid is reported as a numerical failure without attempting integration. Returned arrays must have the expected shapes, finite values and exact saved grid. Nonfinite total-energy diagnostics are rejected conservatively. No clipping, source softening, or invented positions are used.

| Result status | Meaning |
|---|---|
| ok | A valid measurement returned; an optional authored check may still fail |
| selection_error | Exact time absent, or nearest saved time exceeds allowed difference |
| unsupported_trajectory | Existing source composition is not trajectory-qualified, including shell/plane sources |
| domain_error | A singular/numerically unresolved source evaluation occurred during the trajectory |
| numerical_error | Invalid/nonfinite trajectory, diagnostic or measurement, or unresolved time grid |
| integration_error | Existing native integrator explicitly reported unsuccessful integration |

Failures carry null values and explanations. Valid static probes and other particles remain available. Unexpected programming exceptions propagate rather than becoming purported physical failures. The existing solver has string-based RuntimeError failures; only its documented failure messages are converted by this adapter. No solver API was changed to add typed exceptions in this slice.

No method here finds a crossing, turning point, closest approach or collision. In particular, sample 0 is not a way to bypass the existing rejection of shell/plane trajectories. The SC-158 singular-surface flux limitation is unchanged.

## Diagnostics, checks and CLI outcomes

Energy drift is diagnostic, not a proof of global trajectory accuracy. No global error bound or automatic convergence certification is supplied. Extreme scales, near singularities and long-duration motion retain the existing limitations. Reference tolerances check the returned quantity at the **actual selected sample**, never change integration settings, and do not establish independent correctness. A three-vector expectation cannot broadcast a scalar.

`--validate-only` performs no field evaluation or integration. It does not prove sample availability, supported motion, or accuracy. Exit 0 means all evaluated requests and optional checks succeeded; exit 1 means a complete report contains a local failure or failed authored check; exit 2 denotes invalid input or I/O failure. Existing atomic output writing and input-overwrite guards are retained.

`examples/trajectory_observations/manifest.json` records nine packets. Four reuse historical pilot scenes, one reuses the ideal-Sun scene, one is an illustrative gravitational composition, and three deliberately exercise failure behavior. They are assisted authoring examples, not an autonomous-LLM benchmark or a new gravitational corpus. See `TRAJECTORY_OBSERVATIONS_VALIDATION.md` for executed evidence. PR #1 remains draft and unmerged.
