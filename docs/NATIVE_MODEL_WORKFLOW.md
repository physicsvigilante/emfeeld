# Native revision -> calculation -> recorded view

This is a convenience interface over the named-model engine and recorded-run viewer.
It adds no physical laws, new revision format, implicit parent selection or second
store. This ChatGPT conversation remains the LLM; the desktop window is not a chatbot.

## Apply one small revision

After a native model has been imported and one investigation has run:

```powershell
python -m emfeeld model apply revision.json --store my-model --using runs/root-motion --output runs/change-001 --view
```

`revision.json` is an existing native `proposal_version: 1` document. It already
pins the exact parent model/revision/hash, target identity, expected old value,
new value, category, scenario intent and provenance. This command does not infer
or alter those facts. `--using` selects a sealed native run of the same root model:
only its investigation, analysis and presentation settings are reused. It need
not be the proposal's parent, but both must belong to the identical model lineage.
There is no `latest` lookup, inherited numerical pass, hidden new measurement or
reused numerical solution. New results are computed with the existing backend.

The original model, its previous run and the downloaded proposal stay unchanged.
Use a **new output directory outside the model store and the sealed previous run**.
`--run-id` is optional; omission creates a fresh run identity, not a physical input.

The command validates the source run and captures the exact proposal/settings,
applies the native revision, runs and checks the requested investigation, and
then opens the recorded result. A failed request or trajectory check blocks the
automatic preview; successful unrelated outputs remain available. A static query
on a model containing particles does not silently acquire an unrequested motion
simulation merely because `--view` was supplied.

The accepted revision may remain in the store even when its numerical run fails.
Acceptance means construction validity, not a simulation pass. Do not delete it
or apply it again with the same IDs. Its `reference.json` can be used with the
existing `model run` command for a separately declared analysis and new output.
Unexpected computation errors leave a started attempt without an outcome marker.

## Headless calculation, snapshot and reopening

Omit `--view` for numerical execution without importing PyVista. Use `--render`
instead for an offscreen snapshot; graphics support is still required:

```powershell
python -m emfeeld model apply revision.json --store my-model --using runs/root-motion --output runs/change-001 --render --sample-index 30
python -m emfeeld model view runs/change-001/run
```

`--view` and `--render` are alternatives. A nonzero `--sample-index` is accepted
only for `--render` and must be an existing saved sample. Interactive viewing
starts at the initial sample; use the existing slider/playback controls afterward.
The viewer consumes captured arrays, without reintegrating or inventing intermediate
physical states. Separate previews do not imply a shared quantitative colour scale.

The output contains `inputs/`, `started.json`, the native revision `decision.json`,
`reference.json` when accepted, a sealed `run/`, `calculation.json`, final
`outcome.json`, and a readable `REPORT.md`. Snapshots live in `presentation/`,
not inside the sealed run. A viewer failure does not erase numerical results.
The calculation and presentation outcomes are reported separately. These hashes
are integrity checks, not proof of source interpretation or cryptographic authenticity.

Exit 0: all requested calculations/checks and requested presentation completed.
Exit 1: explicit rejection/no-op, unfulfilled request, failed check, or unavailable/
failed requested preview. Exit 2: malformed input or I/O failure. Unexpected backend
exceptions propagate; an incomplete attempt is never called successful.

## Initial setup and subsequent hypotheses

Existing commands are available under the same prefix with unchanged arguments:

```text
python -m emfeeld model import SOURCE.json --assignment IDS.json --store my-model
python -m emfeeld model reference root --store my-model
python -m emfeeld model run REFERENCE.json --store my-model --investigation QUESTION.json --analysis ANALYSIS.json --presentation VIEW.json --run-id root-motion --output runs/root-motion
```

`python -m emfeeld.model_runs ...` remains supported. Legacy scene commands,
observation packets and study-v1 commands also retain their original behavior.
The `apply` command is not a substitute for creating an initial physical model
or choosing the first investigation and its explicit numerical check policy.

For a chained hypothesis, the next small proposal pins the actual reference in
`runs/change-001/reference.json`. Reuse `--using runs/change-001/run` and choose
another output directory. Sibling hypotheses can instead pin the original root.
Never fabricate a parent hash; return the actual reference to the authoring chat.

## Compatibility with the portable Conda handoff

The previously delivered `emfeeld_chat_handoff.py` kit uses a different, deliberately
restricted store and revision envelope. Keep that working folder intact. This
command **does not automatically upgrade or overwrite `classroom-model`**. Use an
explicit native import with an ID assignment pinned to the original scene bytes,
then prepare a native proposal against the returned native reference. Do not copy
a portable root hash into a native proposal. The meaning of the original physical
model may be preserved, but the artifact identities and formats are not identical.

This command is available only in this implementation candidate until merged and
installed. Do not assume a prior `main` installation already includes it.

## Qualification examples

```text
python tools/qualify_native_model_workflow.py --output output/native-model-001 --render
python verification/check_model_revision_runs.py output/native-model-001 --output output/native-model-checks-001.json
```

The driver imports the existing electric/gravitational fixtures, computes each
root once for motion, and uses the actual native command for two sibling hypotheses
per model. Exact copies of the resulting runs are organized for the **unchanged**
harmonic/Kepler checker; these copies are not additional simulations. Static checks
are run separately. Fixture parameters are illustrative, not new textbook givens.
Teacher usefulness, interpretation fidelity and independent correctness review are
not inferred from native execution or rendering. No new physical scope, automatic
LLM connection, live file watcher, sweep or inverse capability is introduced.
