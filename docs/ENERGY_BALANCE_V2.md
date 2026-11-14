# Sampled energy balance v2 — issue #7

## Scope

This is a numerical-diagnostic correction over main `3948852`, separate from the
particle-visibility PR #6. No force law, potential reference, initial condition,
integrator setting, trajectory array, event search, viewer or dependency is changed.
The branch remains a candidate until accepted and merged. Existing saved reports
are historical evidence and are never rewritten or automatically requalified.

Issue #7 is specifically **K(0)=U(0)=0 with subsequent resolved motion**, not just
zero total energy from cancellation of nonzero K and U. The old denominator
`max(abs(E0), K0, abs(U0), float64.tiny)` used an arbitrary machine magnitude when
both initial components vanished. The reproduced residual 1.29247e-26 J divided
by 2.22507e-308 J became approximately 5.81e281 and blocked a valid refined run.

## Definition and versioning

For the recorded trajectory samples only:

```
dK[i] = K[i] - K[0]
dU[i] = U[i] - U[0]
R = max(abs(dK + dU))
S = max(max(K), max(abs(dU)))
normalized_residual = R / S           when S > 0
```

All energies and S are in joules. S measures kinetic energy or potential-energy
exchange actually present in the recorded interval; it is not an arbitrary 1 J
or a smallest-float substitute. Adding a constant to potential leaves R and S
unchanged in exact arithmetic. Saved potential energy, its reference and forces
are not changed to implement this calculation.

`Trajectory.energy_balance` exposes `version: 2`, `max_residual_J`, `scale_J`,
`normalized_residual`, `resolution_J`, `resolution_ratio`, `zero_exchange` and a
meaning statement. `Trajectory.normalized_energy_drift` now returns this v2 ratio.
New scene-CLI summaries and sample-observation diagnostics include the complete
versioned block. Consumers must not compare v1 and v2 ratios as identical metrics.

`energy_J` and legacy `max_energy_drift_J` remain unchanged. The latter evaluates
`max(abs((K+U)-(K0+U0)))`, so its floating-point value need not equal R. Use the new
block's residual with its scale. Physical state, K, U and total-energy requests
keep their existing meanings and values. The **separate initial-to-event**
`normalized_energy_change` diagnostic is unchanged and still explicitly labelled
potential-reference dependent; this patch does not redefine the event contract.

S is a full-recorded-interval scale, not a local, timestep-independent error bound.
Changing the horizon or saved samples can change it. Relative residuals below an
authored threshold do not prove the equations of motion, source fidelity, local
accuracy, absence of missed events or independent physical verification.

## Finite precision and acceptance

The diagnostic records an eight-ULP indicator at the largest stored magnitude
among K and U (`8 * numpy.spacing(largest_energy)`). This is a conservative signal
for float64 storage/arithmetic resolution, **not a certified bound** on evaluating
a superposed potential or integrating motion. It never increases an allowed error.
Large reference offsets can discard useful differences before subtraction; the
check cannot reconstruct those lost bits and must not claim a reliable pass.

For S > 0, each base/refined trajectory must satisfy both:

- `R/S <= max_normalized_energy_drift` using the existing authored tolerance;
- `resolution_J/S <= max_normalized_energy_drift` at that same tolerance.

A nonfinite resolution ratio is reported as `null` and fails as
`unresolved_precision`. No NaN/Infinity is serialized as success. Invalid shapes,
negative kinetic energies, nonfinite energies and overflowing differences raise
explicit numerical failures. There is **no new absolute-energy allowance**:
`absolute_tolerance_J` is recorded as zero. Normalization changed deliberately;
this is not a claim that the new criterion is universally stricter than v1.

S=0 implies no resolved energy exchange in the arrays, not automatic validation.
The public ratio is zero, with `zero_exchange: true`; the study gate additionally
requires every position identical, every velocity exactly zero, and exactly zero
initial force (zero coupling or zero field). Only then does it report
`stationary_zero_exchange`. Moving or nonzero-force zero-scale cases are rejected
as `unresolved_zero_scale`. This avoids a tiny-energy underflow masquerading as
verified dynamics. The usual independent position/velocity refinement comparisons
are retained for all cases.

The check record includes `energy_check_version: 2` and separate `energy_checks`
for the base and refined trajectories. Outcomes distinguish residual failure,
unresolved precision and stationary zero exchange. A large apparent residual or
lost precision is not a reason to change a physical initial condition, choose
another gauge, relax a tolerance, or silently retry with different physics.

## Reproduction and reference calculation

With existing dependencies installed, from a checkout of this candidate:

```text
python tools/qualify_energy_balance.py --output output/zero-energy-001 --render
python verification/check_zero_energy_run.py output/zero-energy-001 --output output/zero-energy-check-001.json
python -m emfeeld model view output/zero-energy-001/run
```

Use new paths. The qualification driver uses the real native model-run CLI. Its
illustrative physical parameters exactly match issue #7: spheres at x=-1 and +1 m,
radius .25 m, charges +2 and -2 nC; a +1 pC test charge of mass 1e-11 kg released
at the midpoint with zero velocity; 451 samples over .45 s. Original position,
velocity and relative check thresholds remain 1e-7. It requests field/potential
and final state/energy measurements, captures the checked arrays, and optionally
renders those arrays with the unchanged main viewer.

The separate reference file imports no emfeeld code. It regularizes the energy
time integral with x=s^2, uses quadrature and root finding, and compares all 451
sampled positions/velocities and kinetic/potential energies. Exterior validity is
checked (all x < .75 m). It neither fits a trajectory nor changes the launch.
These are separately expressed **same-author** calculations, not independent review.

## Completed local checks

- 1,111 headless tests passed: 1,065 inherited plus 46 new diagnostic/integration cases.
- 18 historical behavioral tests passed. One historical all-file freeze assertion
  was explicitly deselected against changed code; it remains unchanged for its snapshot.
- 25 existing real PyVista tests passed in three completed batches (9 + 9 + 7).
- Total: **1,154 behavioral cases**, warnings treated as errors; no new skipped tests.
- Original v6 replay (10 cases / 58 checks) and discovery replay (2 / 36) passed.
- The native zero-launch run completed and its recorded preview opened successfully.
- All 451 states passed the separate energy/time reference; maximum differences
  were 5.26e-15 m and 7.09e-13 m/s. These observed differences are not promised bounds.
- Replaying the exact archived issue packet against old and new source produced
  identical time, position, velocity, K and U arrays and identical 26 observations.
  Only diagnostics/qualification changed: failed preview -> new checked preview.
- All 110 files of the archived lesson stayed unchanged; its old failure still
  refuses preview. A new run does not erase or relabel historical evidence.

The reproduced new ratio is 8.24907e-16 with S=1.56681e-11 J; its eight-ULP
resolution ratio is 1.64981e-15. Both are below the unchanged 1e-7 threshold.
Tests also cover exact/near-zero and ordinary launches, electric/gravitational
constant acceleration, representable gauge offsets, unresolved large offsets,
consistent energy/coupling rescaling, nonzero-component cancellation, stationary
zero exchange, corrupt energies and preservation of strict authored thresholds.

Local environment: CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2,
PyVista 0.48.4, VTK 9.6.2/software EGL. Viewer wheels were hash-checked and installed
only into a container-local target. No user installation or dependency range changed.
Direct clone failed DNS; reconstructed executable/test/example/CI subtrees matched
main's Git identities. Unrecovered inherited design Markdown is retained by the
remote parent tree, not recreated or edited.

Failure history: 33 of the first 36 new checks failed against the old code (3 passed).
Three existing subprocess checks initially failed because the local harness lacked
PYTHONPATH; setting it correctly produced 284 passes without modifying assertions.
The first wheel manifest read hit its UTF-8 BOM; decoding the manifest correctly
preceded transfer-hash checks. A combined viewer command timed out after progress
without a completion summary; only the subsequent completed batches are counted.
Fresh Windows/Linux CI must be reported separately after its own execution.

## Remaining limits

No event-completeness, arbitrary-scale precision, conductor, collision, radiation,
backreaction, new source support or human Windows desktop qualification is implied.
Energy conservation and two-run agreement cannot detect every wrong physical model
or mutually consistent corruption of all data. Teacher usefulness and interpretation
remain separate assessments. PR #6's marker repair is independent and not merged here.

Primary numerical-interface references (not execution evidence):
- https://numpy.org/doc/stable/reference/generated/numpy.finfo.html
- https://numpy.org/doc/stable/reference/generated/numpy.spacing.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
