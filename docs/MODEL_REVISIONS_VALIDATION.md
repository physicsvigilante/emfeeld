# Named model revisions V1 — implementation qualification

## Identity and scope

Parent: `d24fc47293d27e26d347675866dc73960d54ffc5` (Teaching Study V1 / PR #2).
Design: `38079f1496637a94b64ee4b28f97871461665fe1` (documentation / PR #3).
This candidate is stacked above PR #2; neither existing PR nor main is changed or
merged. No acceptance of desktop interaction, independent review or textbook
answer generation is implied. The user approved the bounded implementation.

New production code is confined to `model_revisions.py` and `model_runs.py`.
Existing fields, dynamics, scene parser, observations/capture, event algorithms,
study-v1, viewer/playback and catalogue are byte-unchanged. The adapter uses the
existing capture/check/presentation machinery rather than adding another solver.
Existing tests, fixture inputs, reference manifests, dependencies, PDFs and historical
reports remain unchanged. CI adds the explicit stacked-PR base plus new example checks.

## Completed local checks

All counted commands completed with warnings as errors and no skipped/xfail tests.

| Group | Passed |
|---|---:|
| Original static/CLI/safety/replay/playback/presentation regressions | 275 |
| Observations, samples, catalogue, teaching study and new revisions | 370 |
| Plane/radial crossing regressions | 191 |
| Turning/rest-launch/live historical compatibility regressions | 198 |
| Historical pilot-v1 behavioral cases | 18 |
| Real PyVista regressions, including recorded revision/run presentation | 22 |
| **Current behavioral total** | **1074** |

This retains 1002 previous behavioral cases and adds 66 headless and six real-render
cases. One historical all-file freeze assertion is explicitly deselected against
changed code; it remains unchanged for its original snapshot. No old tolerance was
relaxed. Totals from repeated executions are not added together.

The original hash-locked v6 replay (10 packets/58 checks) and discovery replay
(2 packets/36 checks) passed. Compilation passed. Twelve new example runs completed:
three revisions per domain (root, source-property sibling, launch-condition sibling),
each used by a static and a motion investigation. The source systems were imported
once from unchanged existing examples, not reauthored per investigation.

A no-engine-import reference script passed **54 separate checks**. Electric motion
uses analytic harmonic solutions with a conservative bound ensuring the whole path
stays within both uniform spheres, plus field/potential and energy expressions.
Gravity uses Kepler equations for five samples of each independent test planet in
all three configurations, plus field, potential and energy expressions. These are
same-author checks of explicitly illustrative configurations, not new textbook
coverage, an independent review, or autonomous LLM reliability evidence.

## Contract coverage

| Design cases | Executed evidence |
|---|---|
| ID-01 through ID-04 | Distinct identical sources; display reordering; missing/duplicate/wrong-role IDs; stale original-byte mapping |
| REV-01 through REV-04 | Siblings; exact parent digest; duplicate revision/output protection; descendant revert |
| EDIT-01 through EDIT-06 | Named scalar/vector changes, radius/centre/orientation, mass/charge, physical launch, uniform input; invalid/coupled/structural/boundary/gauge/waveform edits rejected |
| QUERY-01 through QUERY-03 | One revision reused for static/motion/new horizon; probes stay world-fixed after source movement |
| QUAL-01 through QUAL-06 | Singular revised launch, rest-policy failure, shell motion limitation, stale computed dependency, relevant/irrelevant unknowns, no automatic source-fidelity certification |
| RUN-01 through RUN-03 | Old recorded run after later revision, wrong-revision/capture binding refusal, real camera/replay presentation without reintegration |
| CMP-01 | Different saved times not subtracted; two distinct event times labelled separately; no-event comparisons remain unavailable |
| CMP-02 | Sweep category rejected; actual memberwise sweep execution remains **deferred**, not a passed sweep capability |

Additional cases cover safe Windows filenames for logical IDs, unit checking on
computed receipts, pending attempts after unexpected backend exceptions, reference
mismatches remaining unfulfilled, and static particle-free rendering without invented
dynamics. Missing numerical properties are not silently default-filled. The legacy
parser's intentional defaults are explicitly recorded as conventions during import.

Computed-receipt checks validate identity, dimensions and recorded evidence, not
arbitrary mathematics or forged claims. An author can still mislabel a conductor;
the adapter cannot infer truthful physical interpretation from valid JSON. The
five evaluation dimensions remain separate, with teacher usefulness awaiting feedback.

## Runtime and evidence limits

Local runtime: CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, PyVista 0.48.4,
VTK 9.6.2; Linux software EGL rendering. Six previously supplied viewer wheels were
transfer-hash-checked and installed offline into a container-local target only.
No user-computer installation or dependency-range change occurred.

Native Git clone failed DNS. Source was recovered from the previous teaching-study
archive; source/test/viewer/example/tool/verification/pilot/CI subtree hashes matched
pinned PR #2. The archive omitted an inherited release-protocol document; it is
retained by the remote parent tree and is not modified or claimed reconstructed.

An initial unbatched baseline command timed out after partial progress and is not
counted. A combined run-and-render command also hit the local execution timeout near
its sixth frame; its partial outputs are retained. The completed numerical example
run and completed per-frame captures are distinct evidence, not a relabelled full
combined-command pass. No numerical tolerance or physics input was adjusted in
response. The reference checker passed both initial and final numerical runs.

Visual inspection after the first publication found that a single-line title
clipped model/revision/run IDs. The adapter now constructs a three-line display-only
title before the unchanged viewer creates its axes and caps the native title font.
An intermediate actor-removal approach changed axis bounds and was rejected; those
captures remain retained. The final real test preserves exact authored bounds,
complete identities and the immutable original title. A combined 22-test viewer
command reached 100% but timed out before an exit summary; it is not counted.
Separate completed batches passed 16 inherited and six new viewer cases. The
initial 1073-test publication remains historical; the corrected total is 1074.

Fresh-checkout CI results must be recorded against the published candidate/merge-
preview tree after completion. Prior Linux/Windows successes are not new-candidate
passes. The repository record reports those outcomes separately in the PR.

## Reproduction

```text
python -m pytest -q -W error tests
python -m pytest -q -W error pilots/authorability_v1/test_pilot.py -k "not test_all_available_parent_files_remain_frozen"
python -m pytest -q -W error viewer_tests
python tools/qualify_model_revisions.py --output output/model-revisions-001 --render
python verification/check_model_revision_runs.py output/model-revisions-001 --output output/model-revisions-checks-001.json
python tools/replay_packets.py verification/v6_published.json --output output/v6-new
python tools/replay_packets.py verification/discovery_examples.json --output output/discovery-new
```

Use new output directories/files. The implementation is a bounded model lifecycle,
not a general framework for structural changes, boundary solving, numerical initial
guesses, sensitivity derivatives, sweeps or source feedback. Model construction,
analysis admission, execution, verification, request fulfillment and presentation
availability remain distinct. Stop for explicit acceptance before any merge.
