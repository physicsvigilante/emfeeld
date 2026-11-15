# Structural source revisions V1

Implementation candidate on parent main `2ea54f93acd297936c12d98d263d646b1de4a297`.
This extends the native model lifecycle, not the physical laws or supported
interaction regimes. Keep the candidate unmerged pending qualification/acceptance.
Historical contracts/reports and original model/run bytes remain unchanged.

## What this adds

Add or remove one existing supported source type within the model's single
physical domain, using an exact parent and stable identities. The original root
and unrelated sources/particles are preserved. Each accepted descendant is an
immutable full snapshot in the same store. No case-specific engine dispatch,
new model format, solver, dependency or viewer changes are introduced.

New operations use `proposal_version: 2`; version 1 remains the existing
single-property revision contract. `model_format: 1`, source/scene-v1 and named
investigation formats are unchanged. Older applications do not understand v2
proposals; they must not silently substitute a different operation.

## Add a source

After importing a model, obtain the exact parent with `model reference`. Author:

```json
{
  "proposal_version": 2,
  "proposal_id": "add-background",
  "revision_id": "with-background",
  "parent": {"model_id": "my-model", "revision_id": "root", "sha256": "ACTUAL_PARENT_HASH"},
  "category": "structural_change",
  "operation": "add_source",
  "target_id": "new-background",
  "expected_role": "source",
  "source": {"type": "uniform", "field_N_C": [0, 0, 0.1], "origin_m": [0, 0, 0]},
  "scenario_intent": "teacher_hypothesis",
  "provenance": {
    "origin": "illustrative_choice",
    "reason": "Investigate an additional prescribed uniform field",
    "evidence": "Explicit teacher hypothetical scenario, not an original given"
  }
}
```

The placeholder hash is explanatory and is not executable input. All values use
the existing unit-bearing source keys. Added sources are appended to the source
execution order; no pre-existing identity, property, launch or ordering is changed.
Existing optional parser defaults are expanded and labelled source conventions.
One declared provenance applies to supplied source properties. This bounded V1
accepts explicit literal source data; it does not invent unknown inputs or supply
per-property computed-input receipts for a new source.

An ID already present in any accepted revision of the same store is unavailable
for new entities, including removed sources and sibling revisions. Identical source
geometry with a distinct genuinely new ID is allowed. IDs also share the existing
particle namespace. Source-type replacement and reusing a deleted ID are not
insertion. Return to the preserved parent to investigate the original entity.

## Remove a source

Use the same envelope with `operation: "remove_source"`. Replace `source` with
`expected_source`, containing the complete canonical properties of the targeted
source in the exact parent snapshot (including expanded defaults). The source ID
must exist and have source role. The final remaining source cannot be removed:
empty-source scenes are still outside the inherited scene contract.

If a surviving computation receipt names the removed source, removal is rejected
as `dependent_source`, with the dependents identified. No receipt is deleted or
retargeted. Any successful structural change conservatively marks all remaining
computed properties stale: old receipts cannot express source-set dependence.
Applicable analyses remain blocked until separately supported, justified correction.
No automatic recomputation or same-value receipt-renewal service is added here.
Ordinary supplied/assumed launches remain unchanged, never adjusted to preserve an
orbit or preferred result.

## Execute with the existing native workflow

```text
python -m emfeeld model revise proposal.json --store my-model
python -m emfeeld model run reference.json --store my-model --investigation questions.json --analysis analysis.json --presentation view.json --run-id revised-001 --output runs/revised-001
```

`revise` reports construction validity, not a numerical pass. Save the actual
returned reference; never fabricate hashes or resolve an implicit latest parent.
Alternatively reuse an explicitly identified, integrity-checked previous run:

```text
python -m emfeeld model apply proposal.json --store my-model --using runs/baseline --presentation revised-view.json --output runs/structural-001
```

`--presentation` is optional and explicitly replaces only presentation settings.
Original template hashes and the replacement bytes/hash are retained. This is
useful when an explicit `entity_order` no longer matches the changed source set.
Without an override, incompatible inherited presentation is rejected during
analysis; the accepted revision and original run remain intact. No IDs, camera,
bounds or observations are automatically repaired. Use `model run` with that
accepted reference to retry a separately corrected analysis, not `apply` again
with consumed proposal/revision IDs.

Named particle observations and world-coordinate probes are revalidated and can
be reused when compatible. Source removal never redirects an observation to a
replacement. Native calculations are fresh, not copied from the previous run.
Shell/plane motion prohibitions, singularity errors, units, potential references,
checks and failure semantics remain authoritative. A static admissible assembly
need not support trajectories. Scenarios are not source-switching time evolution;
energy differences between scenarios are not switching work.

## History and failure boundaries

Accepted/rejected attempts use the existing append-only store machinery. Before
structural admission, all accepted snapshots and ancestry are checked; incomplete
or corrupt history fails closed. A nonblocking exclusive local structural-write
lock serializes identity checking/publication. A crash may leave a lock or an
incomplete revision; preserve and inspect it rather than automatically deleting
it or retrying under the same ID. This is not a distributed or adversarial store.

No particle insertion/deletion, source replacement, empty-source scene, mixed
electric/gravity coupling, inverse computation, arbitrary equations, sweep service
or new presentation feature is included.

## Reproducible bounded transfer

```text
python tools/qualify_structural_revisions.py --output output/structural-001
python verification/check_structural_runs.py output/structural-001 --output output/structural-checks-001.json
python tools/qualify_structural_revisions.py --cases examples/structural_revisions/reserved_cases.json --output output/structural-reserved-001
python verification/check_structural_runs.py output/structural-reserved-001 --output output/structural-reserved-checks-001.json
```

E1 adds a translated positive line to the original negative-line/axial-field model.
G1 removes Source B, preserving Source A and both test bodies. Separate ideal-source
formulas and independently implemented fixed-step RK4 (20/40 substeps per recorded
interval) check the results; E1 axial motion and the G1 remaining central-field
angular momentum supply additional physical checks. RK4 agreement is not a rigorous
error bound; the checks share constants and author, not implementation code.

The further preselected T1 case adds an oblique plane to a static shell/point model
and then removes the point. It first ran only after production hashes were frozen;
no production changes were needed. It was known to the same author, not concealed
or independently authored. Its committed replay is a regression, not another
held-out trial. New arrangements required data and verification, not an equivalent
arrangement-specific production extension. This establishes bounded transfer only.

The teaching evaluation is paused; these results do not grade classroom usefulness.
All prior tests and failure records remain intact. Fresh Linux/Windows CI must be
reported separately from local results before merging this candidate.
