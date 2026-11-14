# Named physical model revisions V1 — implementation candidate

Design basis: [contract at 38079f1](https://github.com/physicsvigilante/emfeeld/blob/38079f1496637a94b64ee4b28f97871461665fe1/docs/MODEL_IDENTITY_REVISIONS_V1.md)
and its [28 prospective cases](https://github.com/physicsvigilante/emfeeld/blob/38079f1496637a94b64ee4b28f97871461665fe1/docs/MODEL_IDENTITY_REVISIONS_V1_REVIEW.md).
Runtime parent: Teaching Study V1 `d24fc47293d27e26d347675866dc73960d54ffc5` (PR #2).
This implementation is a separate stacked candidate; PR #2 and design PR #3 remain
unchanged and unmerged. The design's historical proposed status is not rewritten.

## Purpose and boundaries

One reusable physical model supports many investigations. The LLM identifies
entities, source facts, assumptions and teacher hypotheses. The existing engine
computes supported consequences. Source fidelity and educational usefulness still
need human assessment; reproducing textbook answers is optional.

The adapter implements explicit legacy import, stable physical identities,
immutable full snapshots, exact-parent single-property revisions, named observations,
separate analysis/run/presentation records, retained rejected proposals and fresh
execution. It rebuilds the small existing source assembly; it does not reuse solver
state or create a general graph/equation compiler. Source laws, integration,
event policies and the legacy scene/observation/study formats are unchanged.

Boundary/structural changes, source-type replacement, gauge/frame changes, waveforms,
insertion/deletion, sweeps, sensitivities and inverse solving remain unsupported.
There is no reinterpretation of static scenario comparisons as charging/accretion
or any time-dependent physical transition. No numerical initial-guess field is
exposed as a physical initial condition.

## Separate files and identities

- A model store has one immutable `model.json` root reference, retained `original.json`
  bytes and an exact `import.json` ID assignment. It has no mutable latest pointer.
- Each accepted revision has a complete ID-keyed entity snapshot, explicit source/
  particle execution order, property provenance, parent reference and the operation.
- References contain `model_id`, `revision_id` and exact-byte `sha256`. Schema versions,
  model IDs, revision IDs, investigation IDs, run IDs and software hashes differ.
- Proposal and revision filenames use SHA256 of the logical ID, so IDs are not OS
  filenames. Distinct case-sensitive IDs and names such as `CON` remain safe on Windows.
- Exclusive creation prevents API overwrites. A revision's external reference file
  is written last. A crash before that marker leaves an incomplete reserved ID,
  not an accepted revision. Store files are not signed or adversarially immutable.
- Runs use new output directories, pin exact source/revision/request/settings bytes,
  and retain generated packets, the ID-to-index map, native results and diagnostics.
  An unfinished run remains pending without a completed integrity inventory.

The root's original bytes do not change when descendants override physical values.
Reverts produce descendants, not deletion of intervening history. Sibling hypotheses
have the same pinned parent. No-op numerical edits do not create another scenario;
interpretation-only revision editing is not implemented in this first slice.

## Import and origin records

Import only explicit existing scene-v1 or observation-v1 JSON with an assignment
pinned to its SHA256. All source and particle IDs must be supplied, globally unique
within the model and correct in count. Different source bytes invalidate the old
assignment even when array values look similar. The importer never matches IDs by
nearest location or equal component values.

Every physical property receives a value-origin record. The assignment supplies an
explicit default origin/reason/evidence for original properties; omitted legacy
centre/direction/origin/charge defaults are expanded as source conventions, not givens.
An import of an incomplete legacy numerical scene is rejected without filling missing
numbers. Its original source file remains available as the draft. Recorded unresolved
facts can block only the named analysis category; unspecified appearance need not
block field calculations. This is not symbolic or underdetermined-system support.

Origins distinguish supplied facts, source conventions, assumptions, conversions,
computed results, illustrative choices and unknowns. Scenario intent separately
identifies source interpretation/correction, teacher hypothesis or illustration.
These labels are declarations, not automatic source extraction or truth certificates.

Computed properties require an embedded computation receipt with ID, method, SI unit,
input property identities and values, output identity/value and a recorded successful
check with method/evidence. Receipts are retained and hashed; their mathematics and
claimed external evidence are not automatically authenticated. The adapter checks
structure, output correspondence and units, not arbitrary authored equations.
Changing a dependency marks dependent inputs stale, transitively. A stale launch
blocks trajectories but not unrelated static field probes. No automatic formula
propagation or silent circular-orbit adjustment is performed.

## Typed changes

Each proposal pins an exact parent, names a stable `target_id`, asserts its role,
and supplies a category, property, expected old value, new value, provenance and
scenario intent. Full vectors are one property. Only an existing meaningful
property for that role/type/domain can be changed:

| Category | Admitted changes |
|---|---|
| `component_property` | Source strength, radius, centre, direction/normal; particle mass and electric charge |
| `initial_condition` | Entire particle `position_m` or `velocity_m_s` vector |
| `external_input` | Existing constant uniform electric/gravitational field vector |

Inherited finite-number, positive-radius/test-mass and nonnegative-gravitational-mass
rules remain authoritative. Gravitational test-charge edits are refused as ineffective.
A radius revision holds explicit total charge/mass fixed. Preserving density while
changing radius is a coupled constraint outside this slice, not a hidden recalculation.
A singular revised launch can be construction-valid but fail its requested trajectory;
static probes and the valid baseline remain separately available.

## Investigations, analyses and lowering

New investigations name `particle_id`, never runtime `particle_index`. World-coordinate
probes do not follow a moved source. The adapter records its source/particle index map
and lowers to ordinary scene/observation packets without adding ID keys to legacy data.
Analysis mode is explicitly `static` or `trajectory`; no fallback to another solver.
An admitted trajectory analysis retains existing per-request runtime restrictions.

Static analyses request no integration even if the physical snapshot includes test
bodies. Trajectory analyses specify horizon, sample count and check policy, and capture
full-scene motion for recorded presentation through Teaching Study V1. Each captured
base trajectory has its existing refined check; event searches remain separate.
Adding an observation or changing horizon/tolerances creates an investigation/analysis
and a new run, not a physical revision. Result failures and `no_event` remain visible.
Two-run agreement is not a certified global bound or proof of event completeness.

Recorded playback checks the exact revision, generated packet, ID map and results.
Copied arrays of the right shape do not establish a valid binding. The model/run
identity appears in the plot label. Changing camera, display bounds or playback speed
creates separate presentation metadata and does not integrate or mutate the model.
Particle-free static scenes can be rendered without invented time evolution. A static
query on a model containing particles does not imply a qualified motion preview.

Numerical comparisons require the same root lineage and compatible named observations.
Different sample times are not subtracted; events retain their own times or failures.
This adapter does not add a synchronized multi-revision viewer or a new shared-colour
comparison UI. Separate screenshot autoscaling must not be mistaken for a quantitative
cross-scenario potential comparison; use recorded numerical measurements or study-v1
within its qualified strength-only scope. Direction arrows still omit magnitude.

## Commands and example workflow

```text
python -m emfeeld.model_runs import examples/authoring/discovery_electric.json --assignment examples/model_revisions/electric_import.json --store output/electric-model
python -m emfeeld.model_runs reference root --store output/electric-model
python -m emfeeld.model_runs revise PROPOSAL.json --store output/electric-model
python -m emfeeld.model_runs run REFERENCE.json --store output/electric-model --investigation INVESTIGATION.json --analysis ANALYSIS.json --presentation PRESENTATION.json --run-id run-1 --output output/run-1
python -m emfeeld.model_runs view output/run-1 --sample-index 30 --output output/run-1-view
python -m emfeeld.model_runs compare output/run-root output/run-hypothesis
```

Each argument is a JSON document with an explicit version/ID. `reference` prints a
pinned JSON reference; copy it into the proposal/next command, never substitute latest.
`examples/model_revisions` supplies two existing-model import assignments, named
investigations, numerical/presentation settings and hypotheses without copied models.
The generic example driver fills exact parent references, not physics answers:

```text
python tools/qualify_model_revisions.py --output output/model-revisions-001 --render
python verification/check_model_revision_runs.py output/model-revisions-001 --output output/model-revisions-checks-001.json
```

The driver executes one electric and one gravitational root, each with source and
launch siblings, across two investigations: six revisions and twelve runs. All
parameters are illustrative. Harmonic/Kepler checks are separate expressions written
by the same author, not an independent judge or autonomous LLM reliability study.

`run` returns 0 for fulfilled requests/checks, 1 for recorded limitations/failures,
and 2 for malformed input or I/O failure. Unexpected backend exceptions propagate;
no incomplete run is silently marked successful. Teacher-task acceptance remains open.
