# Source-aware, frozen-engine authorability pilot v2

## Result and meaning

**Eight scene-plus-observation JSON targets passed on their first native execution, with no engine edits and no executed-packet corrections. Two deliberately selected limitation requests remain unsupported.** Numerical measurements came from the existing `python -m emfeeld.observations` command, not problem-specific analysis scripts. The authoring inputs contain no expected answers.

Frozen engine: `81b8d1c8dced61e5583c8032f32c3d3043464c55`, tree `7d5678f5be2085faa9ee8f262623d3a6ff916a66`. All additions are confined to this directory; every earlier file is unchanged. PR #1 remains draft and unmerged. The user's approval authorized this pilot, not a merge.

This is **source-aware assisted feasibility in the same chat**, not a blind test, autonomous reliability estimate, independent review, or all-parameter symbolic proof. Earlier source solutions, examples and component hints were visible. The same assistant authored both packets and the separate reference expressions. Seven execution targets are based on the uploaded Electrostatics PDF; one is an explicitly illustrative gravitational composition, not new gravitational-corpus coverage. Three PDF targets (SC-18, SC-147, NUM-34) were not cases in pilot v1. Repeated cases test the new measurement workflow rather than add unseen-problem coverage.

## Cohort and native outcomes

PDF page numbers are one-based; printed numbering is separate. Question numbers restart across sections.

| ID | Source | Authored request | Result |
|---|---|---|---|
| P01 | Single Correct 18; PDF 22 / 1.162 | Potential at the stated 3D point, finite line reference and endpoint difference | PASS |
| P02 | Single Correct 147; PDF 38 / 1.178 | Field at the centre of seven occupied cube vertices; extra potential probe | PASS |
| P03 | Numerical 31; PDF 71 / 1.211 | Off-centre cavity potential using signed sphere superposition | PASS |
| P04 | Single Correct 99; PDF 32 / 1.172 | Saved-time state/energies and an added plane crossing in a uniform field | PASS |
| P05 | Single Correct 28; PDF 24 / 1.164 | Native midpoint-crossing state under two fixed charges | PASS |
| P06 | Solved 26; PDF 18–19 / 1.158–1.159 | Zero-potential spherical crossing plus static potential probes | PASS |
| P07 | Numerical 34; PDF 71 / 1.211 | Stopping distance and state for a repulsive point charge | PASS |
| P08 | Author-created, not a PDF question | Tilted motion in two overlapping massive spheres plus a uniform field; two independent test masses | PASS |
| L01 | Adapted observation on SC-28's unchanged rest launch | Later radial maximum from rest | UNSUPPORTED: initial_condition_error; separate potential probe remains valid |
| L02 | Numerical 12; PDF 69 / 1.209 | Ring-source capability probe for the stated oscillation problem | UNSUPPORTED: unknown ring source; no numerical report fabricated |

PASS refers to the declared numerical instantiation and requested native outputs. It does not claim a general symbolic solution, automatic multiple-choice grading or a complete teaching diagram. L01 is a new limitation request, not the original SC-28 midpoint question, which P05 handles. L02 probes the missing source vocabulary with a saved-state request; the original period question remains unsupported. Neither control counts as a solved problem.

SC-18/SC-147/SC-99 and the earlier SC-28/Solved-26 scenes use clearly labelled numerical choices where the book supplies symbols. NUM-31 and NUM-34 preserve the supplied numerical data with explicit SI conversions. Source geometry and parameter choices are recorded in `cases.json`; no figure ambiguity is silently resolved by changing physics. The gravitational example is entirely illustrative.

## Representative measured answers

- NUM-34: **0.09988885865580274 m = 99.88885865580274 mm**, at **0.00022220032075857208 s**. The charge's speed is approximately zero at this local minimum. The supplied mass is **2 micrograms = 2e-9 kg**, not 2e-6 kg. The stopping radius was not supplied to the event condition.
- NUM-31: **35.11136897797393 V**, rounding to the requested **35 V**. The negative source represents removed density, not an additional physical object.
- SC-28, retained illustrative scene: midpoint speed **0.1340712630370193 m/s** at **27.320139193856054 s**, returned by the native plane-event interface.
- Solved 26, retained illustrative scene: sphere-exit speed **0.06703563151850973 m/s** at **83.87132242424451 s**. No case-specific crossing interpolation is used.
- New gravitational composition: both 0.2 kg and 2 kg test masses reach their first local distance minimum at **0.7853981633974484 s**, at distance approximately **1 m** and speed approximately **2 m/s**. Their kinetic/potential energies scale with mass, while their trajectories agree.

The source descriptions determine the physics; the time horizon, display bounds, numerical measurement settings and any additional observations are explicitly authored settings, not extra textbook givens.

## What the experiment establishes

The original pilot needed a per-case analysis program to extract crossing speeds. Here the native observation command supplies static measurements, saved-state quantities, plane crossings, radial crossings and local turning points directly. `run_pilot.py` is a generic executor/judge: it invokes the same CLI for every packet and compares output paths with numeric reference data. It contains no source formulas, equation-of-motion solver, root search, or question-number-specific measurement calculation.

A separate preparation script evaluated reference expressions before native execution. That script is retained in the chat evidence bundle, not required to execute the packets. `references.json` is verifier input, never a replacement for native results. Expected values and tolerances were fixed before the first run. `FIRST_ATTEMPT_INPUTS.json` records the pre-run hashes; those 15 files remained unchanged through publication. A reference-path spelling was reconciled with the existing contract before that freeze, not by relaxing a failed numerical comparison.

## Reference basis

These are same-author mathematical checks, distinct from source statements and native engine measurements:

- Line: potential relative to the supplied zero-potential cylinder, with radii 13 m and 5 m; compare `2*k*lambda*log(13/5)`.
- Cube: subtract the missing vertex from the symmetry-cancelled eight-charge field; add seven equal potentials.
- Cavity: analytic interior potential of the full solid sphere minus exterior potential of the removed sphere.
- Uniform launch: constant-acceleration state and `K + qV`; initial kinetic energy is retained rather than confused with its gain.
- SC-28/Solved-26: energy gives crossing speed; a separate one-dimensional quadrature with the release-point square-root singularity removed checks travel time.
- NUM-34: with C=k*Q*q and total energy H=m*u^2/2+C/r0, the radial stop is C/H. A nonsingular change of variable checks the travel-time integral independently of the engine.
- Gravity: both particles remain inside both solid spheres throughout the authored interval. Chosen positive masses give `g_total=-(position-equilibrium)` in SI, enabling a separately evaluated rotated harmonic solution. Energy checks use each sphere's interior potential plus the uniform-field potential.

Shared physical constants are recorded explicitly. Agreement is not an independent review, a rigorous global error bound, or proof of event completeness.

## Executed verification

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2; existing viewer tests use PyVista 0.48.4 and VTK 9.6.2. Previously uploaded wheel hashes matched their transfer manifest; installation was offline into a container-local directory. No user-machine changes or dependency additions occurred.

| Check | Result |
|---|---|
| Frozen baseline | 706 tests passed: 678 ordinary tests + 28 viewer/historical-pilot tests |
| New pilot tests | 38 passed |
| Final cumulative validation, warnings as errors | **744 passed, no skips**, in bounded batches: 697 existing core/pilot + 9 existing viewer + 38 new pilot |
| First native authoring attempt | 8 PASS, 2 UNSUPPORTED controls, 0 unexpected failures |
| Packet-only correction rounds after execution | 0 |
| Schema checks | 9 accepted packets; 1 deliberately unsupported source rejected |
| Requests in accepted schemas | 28 returned: 27 ok, 1 initial_condition_error |
| Accepted event states | 6, each with base/refined native records |
| Saved-state / static measurements | 11 / 10, respectively |
| Predeclared numeric/unit/shape comparisons | 49 passed: 48 execution-target checks + 1 valid control probe |
| New judge mutation tests | Reject no_event as a solved crossing, wrong values/units/shapes, missing state and missing refinement |
| Historical pilot, strict mode | 11 PASS, 1 PARTIAL, 0 FAIL, 0 ERROR; expected exit 1 |
| Original pilot freeze guards and compilation | PASS |
| Production code edits | **Zero** |

An initial combined baseline command hit the tool execution limit after the headless portion; its incomplete log is retained. Complete runs were then split into bounded batches. No code or tolerance was changed because of that timeout. The added test fixture reruns the native CLI packets in a temporary directory, separately from the preserved first-attempt outputs. No skipped tests or xfails were introduced.

All 134 locally reconstructed parent files and four inherited Git entries reproduce the pinned live parent tree. Freeze checks pass before/after execution and publication. This is a verified source copy, not a full local Git clone. New files stay under this pilot directory. Previous source formulas, adapters, schemas, examples, tests, dependencies, reports, PDF and main branch are not modified.

## Reproduce

From the candidate checkout with the existing dependencies:

```text
python -m emfeeld.observations pilots/authorability_v2/packets/P07-numerical-stop.json --output output/numerical-stop.json
python pilots/authorability_v2/run_pilot.py --output output/authorability_v2
python -m pytest -q -W error tests pilots/authorability_v1/test_pilot.py
python -m pytest -q -W error viewer_tests
python -m pytest -q -W error pilots/authorability_v2/test_pilot.py
```

Source-only copies need `PYTHONPATH=src`. The runner requires an empty output directory to preserve earlier attempts. Default exit 0 means the assessment completed with every declared expected outcome verified, **not that the unsupported controls were solved**. `--strict` returns nonzero unless every selected case is PASS. The detailed assessment always retains the unsupported statuses. The ring packet itself exits 2; the rest-turning packet exits 1 while retaining its valid static result.

## Remaining boundary and recommendation

This demonstrates improved numerical authorability, not a complete natural-language application. The LLM still chooses source assumptions, representative values, horizons and numerical settings; source-aware success is not autonomous reliability. Two-run event agreement does not prove the first physical root or absence of events. Local minima are not global closest approach. The initial-rest turning policy remains a real limitation; it must not be evaded by silently changing a textbook launch. Ring sources remain absent; no discretization, new laws or minimum-launch-speed inverse solver were added. SC-158 remains PARTIAL.

No new scene screenshots, teaching annotations, mesh subtraction or Windows interactions were qualified; existing viewer regression tests alone were rerun. For the next bounded capability change, consider **a separately qualified policy for observing later turning points from a genuine rest launch**, preserving its initial state. Do not interpret that recommendation as part of this frozen-engine experiment or an authorization to merge.
