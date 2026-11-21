# emfeeld

A local, data-authorable explorer for **analytic electrostatic or Newtonian gravitational fields, potentials and independent test-particle motion in 3D**. Its purpose is teaching and investigation: author a physical model, ask explicit questions, retain the calculated evidence, then explore named hypothetical revisions without silently changing the original model.

The merged baseline through PR #71 includes named revisions, sweeps, sealed comparisons and ensembles, static magnetic probes and composable electric and magnetic force observations. The [November 17 audit](docs/PROJECT_AUDIT_2026_11_17.md) records the state evaluated on that date.

The original PR #1 chat-only acceptance exception and dated validation reports are **historical records**, not current feature status or permission to bypass review. Keep author tests, independent review, hosted CI, manual visual inspection and educational evaluation distinct. This is **not a general electromagnetic, conductor or natural-language physics solver**.

## Install and start

The package declares Python >=3.11; the released CI baseline used Python 3.13.5 on Ubuntu and Windows. Declared dependency ranges are compatibility intentions, not evidence that every combination was tested. Use an isolated environment; no external LLM service is required by the engine.

```sh
python -m venv .venv
# Activate .venv using your shell's normal command, then:
python -m pip install -e ".[dev]"
python -m pytest -q -W error
python -m emfeeld capabilities --output output/capabilities.json
python -m emfeeld validate examples/electric_composition.json
python -m emfeeld.observations examples/observations/gravity_composition.json --output output/gravity-probes.json
```

For the optional desktop viewer, install `python -m pip install -e ".[view]"` in that same environment, then run `python -m emfeeld view examples/ideal_sun.json`. PyVista/VTK needs a working graphics backend even for screenshots. Calculations and headless tests do not require it. On Windows, an explicit executable is `.venv\Scripts\python.exe`; on Linux/macOS it is `.venv/bin/python`.

## Capability map and scientific boundaries

| Area | Implemented capability | Important boundary |
|---|---|---|
| Analytic sources | Point source, uniformly filled sphere, thin spherical shell, infinite line, infinite plane, uniform field; translated/oriented same-kind compositions | Electric and gravity are separate domains. A prescribed sphere is not a polarizable conductor or collision surface. |
| Static measurements | Field vector/magnitude, potential, force with explicit test charge/mass, ordered potential difference | Explicit SI units and potential references; undefined source/surface values remain errors, not softened values. |
| Static magnetic probes | Superpose prescribed infinite straight DC wires and uniform magnetic fields at world-coordinate probes. Each source and total reports a vector in tesla. | A probe on an active wire has an unavailable total. See the [magnetic model contract and two-wire example](docs/STATIC_MAGNETIC_FIELD_V1.md). |
| Crossed-field forces | Compose electric and magnetic forces at a shared probe with signed charges and supplied velocities. | Instantaneous force in newtons. See the [V3 velocity-selector example](docs/CROSSED_FIELD_FORCES_V3.md). |
| Magnetic force observations | Evaluate the instantaneous force on signed test charges with supplied velocities at named magnetic probes. | Static field sampling only. See the [V2 contract and example](docs/MAGNETIC_FORCE_OBSERVATIONS_V2.md). |
| Wire force per unit length | Evaluate instantaneous local magnetic force per unit length in N/m on a named prescribed infinite straight wire, excluding only its own field by source ID. | Fixed prescribed wire; no self-force, motion or backreaction. See the [V4 parallel-wires contract and example](docs/WIRE_FORCE_PER_LENGTH_V4.md). |
| Motion | DOP853 integration, multiple independent nonrelativistic test particles, saved positions/velocities/speeds/energies | Fixed prescribed sources; no particle-particle forces, recoil, magnetic force, collisions or relativistic dynamics. Shell/plane-source motion is refused. |
| Events | Bounded plane/radial crossings and local radial turning observations, including the explicit rest-launch policy | Numerical first-detected events, not a proof that every crossing exists/was found or that a local extremum is global. |
| Numerical checks | Recorded energy exchange diagnostics; baseline/refined comparisons in teaching studies | Checks are not certified global error bounds or independent physical interpretation. |
| Reusable systems | Immutable named model revisions; source/particle insertion/removal; atomic 2-4-change V3 proposals | Exact parent and stable IDs; new observations/settings need not create a new physical model. `model apply` is currently bounded to V1/V2 proposals; V3 is available through native revision/ensemble interfaces. |
| Investigations | Bounded authored sweeps; derived ratios/separations; signed cross-scenario comparisons; sibling ensembles with a fresh baseline | Hypotheses are not physical time transitions. Unavailable operands remain typed `null`, and partial status is not upgraded by filtering. |
| Evidence | Captured input bytes, source hashes, sealed runs, read-only measurement projection and escaped Markdown tables | Hash receipts detect drift; unkeyed hashes do not authenticate a maliciously rewritten history or external teacher identity. |
| Visualization | Source geometry, potential slice, field-direction arrows, recorded trajectories, play/pause/seek/sample step, screenshots | Equal-length arrows show direction, markers are schematic. The cavity lesson traces field lines and the Gauss lesson shows face and closed-surface flux with prediction and reveal. General 3D equipotential surfaces remain unsupported. Manual Windows interaction is not established by offscreen CI. |
| Question trials | Freeze declared question/context before the packet; require native IDs, quantities, units and actual saved times | Structural native coverage is not correct prose interpretation, verified model assumptions or educational usefulness. |

The Python library also supplies midpoint line-integral contributions and spherical flux quadrature; these are **not general observation-packet request types**. Native JSON supports strict data, not arbitrary expressions or executable code. Python superpositions can be nested; JSON scenes compose a list of supported source records.

Read the exact [physics](docs/PHYSICS.md), [observations](docs/OBSERVATIONS.md), [saved samples](docs/TRAJECTORY_OBSERVATIONS.md), [events](docs/PLANE_EVENTS.md), [radial events](docs/RADIAL_EVENTS.md), [turning](docs/TURNING_EVENTS.md) and [energy](docs/ENERGY_BALANCE_V2.md) contracts before expanding a claim.

## Author a question and retain its evidence

Use [the authoring workflow](docs/AUTHORING_WORKFLOW.md). Separate source givens, assumptions, illustrative choices, derived inputs and unresolved facts. Declare unsupported requirements rather than replacing them with convenient supported physics. The capability catalogue is descriptive; the packet validator remains authoritative.

```sh
python -m emfeeld.observations examples/nasa_ion_public_v0/packet.json --validate-only
python verification/question_first_trial_v1.py freeze examples/question_first_v1/developer_question.json --output output/question-lock-001
python verification/question_first_trial_v1.py assess output/question-lock-001 --packet examples/question_first_v1/developer_packet.json --output output/question-attempt-001
python tools/replay_packets.py verification/v6_published.json --output output/published-replay-001
```

Use **new output directories** for retained studies/runs/replays. In the audit candidate, public writers also refuse destinations inside recognizable saved evidence or model stores, including ordinary symlink-parent aliases. Ordinary file replacement outside protected evidence retains each command's documented policy. This is preflight path protection, not distributed locking or a hostile concurrent-filesystem guarantee.

The [question-first contract](docs/QUESTION_FIRST_TRIAL_V1.md) qualifies explicitly requested native measurements only. Keep **interpretation fidelity, physical/numerical correctness, simulation coverage, educational usefulness and textbook-answer completeness** separate. The checked-in gravity example is developer-authored; the [NASA ion exercise](docs/NASA_ION_PUBLIC_REHEARSAL_V0.md) is a public **non-blind** rehearsal with an available answer key, not a previously unseen teacher task.

## Reuse models rather than copying apparatus code

[Named model revisions](docs/MODEL_REVISIONS_IMPLEMENTATION.md) keep physical state, investigation, numerical settings and presentation distinct. Read [source revisions](docs/STRUCTURAL_SOURCE_REVISIONS_V1.md), [particle revisions](docs/PARTICLE_STRUCTURAL_REVISIONS_V1.md), [atomic scenarios](docs/ATOMIC_SCENARIO_REVISIONS_V1.md) and [LLM-directed exploration](docs/LLM_DIRECTED_EXPLORATION.md).

```sh
python -m emfeeld model --help
python -m emfeeld model apply revision.json --store my-model --using runs/root-motion --output runs/change-001 --view
python -m emfeeld.scenario_ensembles --help
```

The `apply` example requires an existing native store, an explicit pinned-parent V1/V2 proposal and an integrity-checked same-root prior run; it is not a no-input quick start. It reuses settings, **never** the previous numerical pass. For other interfaces see [sweeps](docs/INVESTIGATION_SWEEPS_V1.md), [derived observations](docs/DERIVED_OBSERVATIONS_V1.md), [comparisons](docs/SEALED_CROSS_SCENARIO_COMPARISON_V1.md) and [ensembles](docs/BOUNDED_SCENARIO_ENSEMBLE_V1.md).

Completed ensembles can be inspected without another solve:

```sh
python -m emfeeld.scenario_ensembles measurements ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN
python -m emfeeld.scenario_ensembles table ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN
python -m emfeeld.scenario_ensembles view ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --baseline
```

A member named `baseline` is selected separately with `--member baseline`; it is not the fresh baseline. Signed results are member/right minus baseline/left. Filtering never changes the global partial/complete status. Numerical inputs and recorded trajectories are preserved; screenshots cannot rewrite them.

## Teaching studies and playback

```sh
python -m emfeeld.study run examples/studies/electric.json --output output/electric-study-001 --render
python -m emfeeld.study view output/electric-study-001 --configuration variant
```

Study V1 compares a baseline with **one changed source-strength scalar**, holding other physical and numerical conditions fixed. Broader structural/atomic scenarios use the named-model interfaces; do not silently broaden V1. See [teaching studies](docs/TEACHING_STUDIES.md).

Moving views start paused: **Space** toggles play, **Home** restarts paused, **Left/Right** steps saved samples, and dragging the slider pauses playback. Display speed changes no forces, timesteps or captured arrays. Shared colors/camera aid comparison but do not establish teacher acceptance.

## Testing, evidence and next work

```sh
python -m pytest -q -W error tests
# Requires the real viewer dependencies and a working graphics backend:
python -m pytest -q -W error viewer_tests
python tools/qualify_viewer.py --output output/viewer-qualification-001
```

Historical all-file freeze tests belong to their original pinned snapshots. Replay their behavioral cases separately without rewriting those old records. Hosted Linux/Windows workflows, screenshots and technical review are different checks from human desktop interaction or an independent classroom trial.

The next priorities are: qualify the audit fixes on both OSs with independent review; exercise a genuinely independently sourced question and separately held reference; complete human viewer acceptance; streamline the existing question-to-model workflow; then add only physical capabilities justified by concrete questions. A general mesh solver, symbolic inverse solver or broad application framework is not needed to compose currently supported sources.

No repository license has yet been selected by the owner. See [the project-wide audit](docs/PROJECT_AUDIT_2026_11_17.md) for scope, reproducible findings, test evidence and remaining decisions.
