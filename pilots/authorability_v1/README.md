# Source-aware LLM authorability pilot v1

## Result and scope

**12 authored models validated and ran without modifying the engine. Eleven passed the requested numerical checks; SC-158 is PARTIAL because its requested flux is outside the qualified quadrature domain.** This is not a 12/12 problem-solving claim.

Frozen engine: `619147110557cc4fcd339ac014703b7702faf90c`, tree `1c54d0b8cad9637b43415e0c006448d7d93cbd93`. All additions in this task are confined to `pilots/authorability_v1/`. No production source, viewer, original example, dependency declaration, or previous test/report was changed. PR #1 stays draft and unmerged. The PDF on main is not modified.

The user approved this experiment after selecting the PDF shortlist. This is a **source-aware, assisted authoring feasibility pilot in the same chat**, not a blind autonomous-agent benchmark, independent review, or measured reliability on unseen problems. The earlier shortlist already supplied component hints, and source solutions were visible. Analytic references were implemented separately from engine evaluation, but written by the same assistant.

## Source and numerical choices

Source: `01_emfields.pdf`, 100 pages, Git blob `6870cfb3c5bd33f9800eb851ad1fe4c6b4106787`. The attached bytes match that blob. Page numbers below are one-based PDF pages, followed by printed book pages. Numbers restart across sections.

`input_benchmark_v1.json` retains the previously approved selection unchanged. `cases.json` records source identity, each problem's interpretation, supplied/derived/representative parameters, requested observations, caveats, and each scene's hash. SC-55 and NUM-31 retain supplied numerical data (with SI conversion). Other cases instantiate symbolic problems with explicitly labelled representative values; a numerical pass is not a proof for every parameter value.

| ID | PDF / book page | Model and requested check | Result |
|---|---|---|---|
| SC-55 | 27 / 1.167 | Source and probe coordinates; vector force and magnitude | PASS |
| SC-35 | 25 / 1.165 | Three signed infinite sheets; field between sheets | PASS |
| SC-96 | 32 / 1.172 | Mixed-sign square; zero potential with nonzero field | PASS |
| SC-122 | 35 / 1.175 | Two concentric shells with equal surface densities | PASS |
| MC-33 | 48 / 1.188 | Four sources; field and potential on perpendicular axis | PASS |
| SC-158 | 40 / 1.180 | Offset line; pointwise field works, intersecting-sphere flux unqualified | PARTIAL |
| SC-99 | 32 / 1.172 | Uniform-field launch; parabola and total kinetic energy | PASS |
| SC-28 | 24 / 1.164 | Negative charge under two fixed charges; midpoint speed | PASS |
| SOL-26 | 18-19 / 1.158-1.159 | Unequal charges; zero-potential circle and crossing speed | PASS |
| NUM-31 | 71 / 1.211 | Eccentric cavity by density subtraction; potential at P | PASS |
| ARCH-ADV-MC-05 | 87 / 1.227 | Unequal-radius, equal/opposite-density overlapping spheres | PASS |
| MC-36 | 48 / 1.188 | Classical test-charge ellipse; Kepler reference and invariants | PASS |

PASS here means the declared numerical instantiation and observation checks passed. It does not mean every requested scalar or geometric annotation exists in the native JSON/viewer interface. The four moving cases are SC-99, SC-28, SOL-26 and MC-36; the other eight are static field/potential models.

## Findings

### Composition works without apparatus-specific code

The cavity is authored as the original charged sphere plus a smaller **negative density contribution**. It is not a separate physical negative object. NUM-31 gave **35.11136897797393 V**, or **35 V** to the requested nearest integer. The overlap case uses charges proportional to each sphere's volume; equal densities do not mean equal total charges when radii differ. Its field was constant at 100 sampled overlap points while its potential varied, agreeing with choices C and D.

For SC-55 the force magnitude is **0.008987551786170797 N**, consistent with the printed 9 mN option. The representative SC-28 midpoint speed is **0.13407126303701727 m/s**; SOL-26's circle-crossing speed is **0.06703563151855425 m/s**. Their parameters are illustrative, not extra givens from the book. Crossings were estimated from saved position/velocity samples with a bracketed cubic-Hermite interpolant, then checked against a finer run. This is authored postprocessing, not a native stop-surface event.

### SC-158 corrects a readiness overstatement in the original shortlist

The line pierces the Gaussian sphere at two points. `docs/PHYSICS.md` does not certify quadrature for such surfaces. Avoiding exact singular quadrature nodes does not establish accuracy.

For lambda = 1 nC/m, offset = 0.6 m and R = 1 m, the analytic Gauss-law reference is **180.70545065722885 N m^2/C**. Native default quadrature returned **178.16454990592482**, an error of **1.4061%**. Rotating the offset around the same z-parallel line direction changed default error to **3.1060%**. Refinement was nonmonotonic. At 384 x 768 points the relative errors were about **5.99e-5** and **8.36e-5**, above the predeclared **1e-5** target.

The line source and its pointwise field are supported; this requested integral is not qualified. No special quadrature, softened line, omitted contribution, or analytic answer substituted for the numerical result was added. The original benchmark is retained with this explicit correction, rather than replacing the difficult case to improve the score.

### The main authoring gap is requested observations

The scene schema describes sources, particles, time and bounds. It does not natively request a force at a named point, a potential difference, a crossing speed, a turning point, or an accuracy-qualified flux. `run_pilot.py` performs these observations separately using the public engine API and saved arrays. Its per-case reference dispatch is test code, not a new engine apparatus dispatch.

For the next bounded authoring task, prefer a small reusable observation request/result contract with units, domain errors and tolerances over more source types or visual polish. Keep singular-surface flux qualification a separate task.

## Executed validation

Environment: Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, PyVista 0.48.4, VTK 9.6.2. The previously supplied wheels were transfer-hash checked and installed offline into a container-local directory; no user-computer change or new dependency was made.

- Unchanged parent suite: **191 passed**, no skips.
- Authorability assessment: **11 PASS, 1 PARTIAL, 0 FAIL, 0 ERROR**; 12 native JSON validates/runs succeeded. Thresholds were recorded in `criteria.json` before evaluation and were not loosened.
- Final cumulative tests: **210 passed**, no skips, warnings treated as errors. The 19 added tests comprise 12 model/provenance checks, six deliberate wrong-authoring rejection tests, and one frozen-file check. Passing tests do not turn the known PARTIAL flux result into a solved problem.
- All 12 models passed field/potential-gradient checks at declared smooth probes and a translated/rotated field/potential covariance check. This is bounded sampling, not exhaustive domain certification.
- Four moving scenes conserved energy within the declared tolerance; the largest observed normalized drift was about **5.21e-13**. The ellipse also matched a separately evaluated Kepler solution and angular-momentum checks.
- Real unchanged PyVista captures: **12 scenes / 20 frames**. Beginning/middle/end events matched saved particle positions. The first capture call hit the tool's 45-second limit after 11 scenes; only MC-36 was captured in a second call. The incomplete report/log and the resumed result are retained.
- Compilation passed. All 34 reconstructed parent files matched their Git blob hashes before and after the experiment. Four non-runtime parent entries were inherited unchanged rather than reconstructed. This was a verified source copy, not a full Git clone.

The screenshots were inspected as an overview and selected full-size cavity/overlap/orbit frames. They are usable working previews, not polished teaching diagrams. The cavity is **not** rendered as a boolean-cut void; the Gaussian sphere and zero-potential circle are **not** drawn by the native viewer, and the force probe is not a native annotated object. Those limitations remain visible in the model notes. No independent review or Windows interaction claim is made.

## Reproduce

From a checkout of the candidate branch with the existing dependencies installed:

```text
python pilots/authorability_v1/run_pilot.py --output output/authorability_v1
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python pilots/authorability_v1/capture_pilot.py --output output/authorability_v1/renders
python -m emfeeld view pilots/authorability_v1/scenes/num-31.json
python -m emfeeld view pilots/authorability_v1/scenes/mc-36.json
```

For an uninstalled source copy, set `PYTHONPATH=src` first. In PowerShell: `$env:PYTHONPATH = (Join-Path (Get-Location) 'src')`.

The normal assessment command returns success when the experiment completes with only the documented PARTIAL case. Add `--strict` to return nonzero unless every requested observation is fully supported. The detailed `results.json` always records the actual statuses.

`RUN_SUMMARY.json` retains compact results and evidence hashes. Full numerical outputs, CLI logs, refinement rows, screenshots, the initial incomplete capture and source copies are in the accompanying chat evidence bundle. No external calls are needed to run the authored models after dependencies are available. The PDF is an electrostatics corpus; gravitational corpus coverage is not established by these twelve cases.
