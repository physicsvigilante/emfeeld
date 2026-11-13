# Initial candidate validation — 2026-11-13

## Identity and status

Scope: first analytic-field foundation for the newly initialized `physicsvigilante/emfeeld` repository. The project-direction bootstrap is commit `fe896cafc49a73ac95f988f83cdf5fda111cd73f`. Implementation is proposed on a separate branch, not approved for merge merely by this report.

This is an **author-run test report and self-review**, not independent review. No claim is made that the user's Windows machine was changed or that the desktop viewer ran.

## Executed environment

- Linux authoring container; CPython 3.13.5.
- NumPy 2.3.5; SciPy 1.17.0; pytest 9.0.2.
- G = 6.6743e-11 SI; epsilon_0 = 8.8541878188e-12 SI.
- PyVista absent. VTK 9.6.2 present, which does not establish PyVista runtime readiness.

## Executed checks

From the repository root:

```text
python -m pytest -q
python -m compileall -q src tests
PYTHONPATH=src python -m emfeeld run examples/ideal_sun.json --output output/ideal_sun.npz
```

Results: **84 tests passed**, no skipped tests; Python compilation passed. All five authored JSON examples were loaded and executed by the test suite. NPZ export was round-tripped with `allow_pickle=False`, including input JSON and numerical metadata.

Coverage includes both physical kinds, analytic reference values, finite-difference potential gradients, vectorization, translations, rotated line/plane sources, finite potential references, shell/plane discontinuities, singularity rejection, zero-strength behavior, nested and 12-source compositions, invalid geometry/units/schema, constant acceleration, central circular orbit, interior harmonic motion, mass-independent gravitational acceleration, energy conservation, Gaussian flux, an off-center charge plus an external charge, and line-integral convergence/path checks.

In the explicit ideal-Sun run, the first (circular) test orbit returned after one period with final y approximately 5.78e-4 m at orbital radius 1.496e11 m. Maximum normalized energy drift was 6.05e-16 for that orbit and 5.54e-15 for the second test planet. These are observations from this run, not promised accuracy for other trajectories or platforms.

## Not run / not established

- PyVista plotter creation, offscreen rendering, screenshots, desktop interaction and visual inspection.
- Windows installation or desktop launch.
- Independent human/agent review.
- Full dependency-range or supported-Python-version qualification; only the environment above was exercised.
- Collision events, shell/plane crossings, singular close encounters, long-duration orbit accuracy, relativistic motion, conductor responses and many-body dynamics.

A bounded `pip install 'pyvista>=0.46,<0.50'` attempt failed because package-index DNS/network access was unavailable. No successful install or visual pass is inferred from this failure. No additional numerical backends were introduced to bypass it.

## Self-review observations and next gate

The physics core and test suite do not import PyVista. The viewer marks invalid samples as holes, and particle dynamics do not use sampled grids. Authored JSON never executes code. Electric and gravitational potentials are kept dimensionally separate. Display-only truncations do not change source equations.

The main remaining gate is independent review of these contracts and a real PyVista desktop smoke test. The viewer's APIs have been checked against upstream documentation and syntax-compiled, but this is not runtime evidence. After review, test the source shapes, arrows, potential scale, time slider, and both electric and Sun examples on the target Windows machine. Surface events and teaching animations should be separately bounded follow-on work.
