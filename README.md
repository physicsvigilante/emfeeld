# emfeeld

A local, LLM-authorable explorer for **analytic electrostatic and Newtonian gravitational fields, potentials, and test-particle motion in 3D**.

**Status: merged analytic-field foundation with qualified Linux/Windows offscreen previews.** Eight scenes have passed offscreen rendering and programmatic time-slider checks; screenshots were inspected in chat. Windows desktop/mouse interaction remains untested. This is author verification, not independent review. The [approved chat workflow](docs/CHAT_WORKFLOW_DECISION.md) requires explicit user acceptance before merge. See [viewer qualification](docs/VIEWER_QUALIFICATION.md). This is not a general electromagnetic or conductor solver.

## Teaching accompaniment and two-configuration studies

The primary goal is faithful physical interpretation and verified simulation of
supported systems. Textbook final answers, exam formats and solution sequences
are optional. Interpretation fidelity, physical correctness, simulation coverage,
educational usefulness and textbook-answer completeness are separate outcomes.
An explicitly requested quantity still requires a genuine computed result.

```text
python -m emfeeld.study run examples/studies/electric.json --output output/electric-study-001 --render
python -m emfeeld.study run examples/studies/gravity.json --output output/gravity-study-001 --render
python -m emfeeld.study view output/electric-study-001 --configuration variant
```

Each study records assumptions, keeps a baseline packet, changes exactly one
source strength, and retains measurements and checked full-horizon trajectories.
The report and snapshots compare configurations at matching physical times, with
shared potential colour scales. Playback uses saved arrays without reintegration.
Use a new output directory each time. Rendering and numerical checks do not
establish classroom usefulness or correct source interpretation by themselves.
See [the bounded study contract](docs/TEACHING_STUDIES.md).

## Machine-readable capability discovery

```text
python -m emfeeld capabilities --output output/capabilities.json
```

The generated catalogue lists actual source fields, units, observations, saved-
state selectors, event conditions and unsupported physics. It requires no viewer
or external LLM service. It is descriptive discovery data, not a second validator:
validate each authored packet with `python -m emfeeld.observations PACKET.json --validate-only`.
See [the catalogue guide](docs/CAPABILITIES.md) and
[export-integrity qualification](docs/CAPABILITIES_VALIDATION.md).
Two illustrative composed electric/gravitational models and a separate reference
manifest are in `examples/authoring/` and `verification/discovery_examples.json`.

## Current authoring workflow

Use [the question-to-packet workflow](docs/AUTHORING_WORKFLOW.md) to author
sources **and measurements** as data. Static probes, saved trajectory states,
plane/radial crossings and local radial turning points are available through
`python -m emfeeld.observations`. Event detection is numerical, not a guarantee
that every crossing was found; local extrema are not global closest approach.

```text
python -m emfeeld.observations pilots/authorability_v6/first_attempt/MAIN19-Q5-LINE-OUTWARD.json --validate-only
python -m emfeeld.observations pilots/authorability_v6/first_attempt/MAIN19-Q5-LINE-OUTWARD.json --output output/line-motion.json
python tools/replay_packets.py verification/v6_published.json --output output/published-replay-001
```

The replay command requires a **new** output directory. It checks exact input
hashes, freezes those bytes, executes the existing engine, and checks declared
statuses, shapes, units and separate references. A successful CLI exit alone is
not a solved-event claim. The published-v6 replay is a regression, **not a new
blind authorability benchmark**. See [repair and verification evidence](docs/AUTHORING_REPAIR.md).

The scene CLI rejects outputs that alias its input (including links). Numerical
exports replace an existing output only after successful serialization. Scene
JSON rejects booleans and numeric strings instead of changing their meaning.

## Install and run

Use Python 3.11 or newer in a dedicated virtual environment. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,view]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m emfeeld run examples/ideal_sun.json --output output/ideal_sun.npz
.\.venv\Scripts\python.exe -m emfeeld view examples/ideal_sun.json
```

On Linux/macOS, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. Headless calculations need only `pip install -e .`; PyVista is optional. Dependency ranges are compatibility intentions, not proof that every combination has been tested. See the [original numerical validation](docs/VALIDATION.md) and [current viewer qualification](docs/VIEWER_QUALIFICATION.md) for executed environments.

```text
python -m emfeeld validate examples/electric_composition.json
python -m emfeeld run examples/electric_composition.json --output output/composition.npz
python -m emfeeld view examples/shell_fields.json
python -m emfeeld view examples/ideal_sun.json --screenshot output/sun.png
```

`validate` checks the schema and reports whether trajectories are supported; it does not integrate or certify the physics. `run` computes trajectories and prints energy diagnostics. NPZ files contain SI arrays, input JSON, version/constant metadata, and no pickled objects. `view` requires a working PyVista/VTK graphics environment; screenshot mode also needs graphics support.

## What works in the numerical core

- Point sources, uniform solid spheres, thin spherical shells, infinite lines, infinite planes, and uniform fields, in both physical domains.
- Vectorized field/potential evaluation and arbitrary same-domain superpositions. No named apparatus profiles or source-count-dependent physics.
- DOP853 motion for nonrelativistic test particles in supported static, continuous fields; several independent particles can share a scene.
- Midpoint line-integral contributions and spherical flux quadrature with individual contributions retained for later visualization.
- Strict, data-only JSON authoring and explicit invalid-domain errors. No `eval`, softened singularities, or hidden conductor approximations.

The preview combines source geometry, equal-length field-direction arrows, a potential slice, trajectory curves, a sample-time slider, and **play/pause/restart/sample-stepping controls**. Its recorded Linux rendering and native timer checks are verified; this is **not Windows mouse-interaction qualification**. Field lines, equipotential surfaces and animated integral explanations remain future work.

### Motion controls

Moving scenes start paused. **Space** plays/pauses, **Home** restarts paused, and **Left/Right** steps one saved sample. Dragging the time slider pauses playback. Replay stops at the final sample; Space then starts it again. The full simulated interval is replayed in about 12 wall-clock seconds by default, with physical sample time shown separately. This display speed never changes solver timesteps or particle forces. See [playback contract and evidence](docs/PLAYBACK.md).

## Examples

| File | Purpose |
|---|---|
| `electric_sphere.json` | Test charge entering a prescribed uniform insulating sphere; not a conducting sphere or hard collision surface |
| `electric_composition.json` | Two translated spheres plus a uniform field, authored entirely as data |
| `shell_fields.json` | Zero interior field with nonzero constant interior potential |
| `line_plane_fields.json` | Prescribed infinite line and plane with explicit potential references |
| `ideal_sun.json` | Fixed point-Sun and two independent test planets, including an inclined trajectory |

The Sun example uses illustrative SI parameters, not an ephemeris. Planet masses are 1 kg test masses; there is no planet-planet interaction or solar recoil. Rendering markers do not represent planetary radii. A solid sphere is a penetrable prescribed density, not an automatic material collision boundary.

## Authoring and extending

```python
from emfeeld import SolidSphere, UniformField, Superposition, Particle, integrate
import numpy as np

field = Superposition((
    SolidSphere("electric", -1e-9, center=(0, 0, 0), radius=1),
    UniformField("electric", (0, 0, 0.2)),
))
particle = Particle(mass_kg=1e-3, charge_C=1e-6,
                    position_m=(2, 0, 0), velocity_m_s=(0, 0.02, 0))
result = integrate(field, particle, np.linspace(0, 20, 401))
```

Python sources implement `kind`, `trajectory_safe`, `field(points)`, and `potential(points)`. Evaluation accepts shape `(..., 3)`; potentials have shape `(...)`. New physics needs a reusable source implementation and tests. New combinations of existing sources need only a new model. The JSON source registry and viewer geometry adapters are separate from field composition and integration.

JSON uses explicit unit-bearing keys: `charge_C`/`mass_kg`, `radius_m`, `center_m`, line densities `charge_per_m_C_m`/`mass_per_m_kg_m`, and plane densities `charge_per_m2_C_m2`/`mass_per_m2_kg_m2`. Lines require `reference_radius_m`. Uniform fields use `field_N_C` or `field_m_s2`. See the examples and [physics contract](docs/PHYSICS.md).

## Viewer regression checks

With the existing `[dev,view]` extras installed and a working graphics backend:

```text
python -m pytest -q -W error tests viewer_tests
python tools/qualify_viewer.py --output output/viewer-qualification
```

The ordinary `python -m pytest -q` remains the headless suite. `viewer_tests` explicitly requires real PyVista; it is not silently skipped when dependencies are missing. The capture tool produces images and a runtime report. Inspect the images separately; successful rendering is not automatically a visual-acceptance decision.

## Deliberate boundaries and next work

Shell/plane fields and potentials work, but motion involving them is rejected until surface-crossing behavior has been qualified. Point/line singular encounters are not collision handling. No source reaction, radiation, induced conductor charge, relativistic motion, simultaneous electric-plus-gravity coupling, or self-consistent many-body dynamics is implemented.

Playback is available for existing moving scenes; foundation PR #1 is merged. New features require separate acceptance. Windows desktop interaction remains a separate optional qualification before claiming Windows support. Plane/radial observation events and local turning points are documented in the authoring workflow; they do not add material collision handling. Integral teaching views remain separate work. Do not add a general mesh solver or a large application framework merely to run another supported arrangement.

No license has yet been selected by the repository owner.

## Reusable named physical models (candidate)

`python -m emfeeld.model_runs --help` exposes an explicit import/revision/run
adapter over the existing physics. A source property or physical launch change
creates an immutable descendant addressed by physical ID. New probes or numerical
settings reuse the same model revision. Original source bytes and rejected edits
are retained. No structural, boundary, inverse or sweep service is added.

See [the model-revision guide](docs/MODEL_REVISIONS_IMPLEMENTATION.md). Execute the
two illustrative models and named hypotheses without copying their physical
systems or modifying production code:

```text
python tools/qualify_model_revisions.py --output output/model-revisions-001 --render
python verification/check_model_revision_runs.py output/model-revisions-001 --output output/model-revisions-checks-001.json
```

This is a separately reviewed candidate stacked on Teaching Study V1. Neither
candidate is merged by publication. Teacher usefulness and textbook-answer
completeness remain separate from numerical execution and reference agreement.

## Native revision-and-view command (candidate)

```powershell
python -m emfeeld model apply revision.json --store my-model --using runs/root-motion --output runs/change-001 --view
```

Reuse the explicitly identified previous run's investigation/settings, apply a native
pinned-parent proposal and compute fresh checked results before opening its recorded
preview. No physics or source facts are silently changed. See
[the native workflow guide](docs/NATIVE_MODEL_WORKFLOW.md), including the explicit
import requirement for older portable handoff stores. Existing commands remain supported.

## Verified bounded ensemble native viewing (R1 candidate)

After creating a sealed Bounded Scenario Ensemble V1 with separately authored
V3 siblings and complete/partial evidence, the new *candidate* CLI can route a
selected saved run to the existing native PyVista viewer without guessing the
internal member-directory index:

```text
python -m emfeeld.scenario_ensembles view ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --baseline
python -m emfeeld.scenario_ensembles view ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --member hypothesis-A --sample-index 0
python -m emfeeld.scenario_ensembles view ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --member hypothesis-B --output NEW_SCREENSHOT_DIRECTORY
```

Exactly one of `--baseline` and `--member EXACT_DECLARED_ID` is required;
these are deliberately separate because a member may literally be named
`baseline`. The command first verifies the complete saved ensemble, original
model-store proposals and sealed parent template, then selects the **actual
complete native run** and delegates to `model_runs.present_run`. A legitimate
partial *comparison* may coexist with a fully viewable native member run; a
rejected or incomplete selected run never opens. Static runs have only
sample index zero; motion playback and screenshots use recorded native states,
not interpolation or a new solver. Screenshot output must be fresh and outside
the ensemble, model store and sealed parent run. Neither scene presentation
nor saved comparisons model physical transitions, certify teacher outcomes or
qualify manual Windows mouse interaction.

This capability is a source candidate pending its focused R1 review and
exact-head Linux/Windows/real-PyVista qualification, not a merged-release claim.


### R1 corrective safeguards for verified ensemble presentation

The returned view receipt differentiates `selection_kind: fresh_baseline` from
`selection_kind: member` and includes `member_id`, the verified `run_path`,
the native `run_id`, exact model revision `reference`, and
`run_integrity_sha256`. For example, `--baseline` reports `selection: baseline`
whereas `--member baseline` reports `selection: member:baseline` and a different
saved-run path. Newly generated member-run IDs use a distinct `-m-` namespace,
within the existing maximum identifier length; older sealed runs are never
rewritten or retroactively renamed. Older same-named IDs remain distinguishable
by selection kind, path, reference, and exact saved-run integrity hash.

A screenshot output must be fresh and outside **any recognizable saved evidence
root**, including unrelated native runs, sealed ensembles/comparisons, pending
ensemble attempts, and existing model stores, even through a symlinked parent.
A normal fresh external destination remains supported. As with other local
preflight path checks, this cannot provide distributed locking or a hostile
concurrent-writer / filesystem TOCTOU guarantee; do not treat it as one.


## Verified ensemble measurement readout (R1 candidate)

The ensemble's existing inspector establishes complete/partial status; this new
read-only convenience exposes already verified per-member **signed right-minus-left
measurement values, units, typed unavailable reasons and exact saved-source hashes**
without opening or guessing nested comparison paths:

```text
python -m emfeeld.scenario_ensembles measurements ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN
python -m emfeeld.scenario_ensembles measurements ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --member hypothesis-B
```

The command verifies **all** original ensemble and model-store evidence with the
existing native inspectors *before* selecting a member, then projects only fields
from the sealed cross-scenario comparison results. It performs no new physical
calculation, numeric rounding, unit conversion or file write. Member filtering
never changes the **global** reported ensemble status; a complete selected
member does not turn a legitimately partial ensemble into a complete one.
Rejected or native-incomplete members remain explicit with no synthetic zero
measurements. A genuinely unavailable G1 baseline body keeps its original
`unknown_operand` code and `null` value. A member literally named `baseline`
is selected by `--member baseline`, not confused with the fresh left baseline.

As in the existing inspector, the CLI exits `0` for globally complete evidence,
`1` for honest globally partial evidence, and `2` for invalid inputs, unknown
members or detected integrity failures. The JSON fields include source `run.json`
SHA256 pins and the exact sealed request/result/integrity SHA256 receipts. This
is an evidence *presentation*, not another comparator or a claim of physical
time evolution, independent physics certification or teacher acceptance.

This is a new unmerged source candidate requiring its own focused independent
R1 presentation-integrity review and Linux/Windows plus real-PyVista CI.
See [the bounded readout contract](docs/VERIFIED_ENSEMBLE_MEASUREMENT_READOUT_V1.md).
