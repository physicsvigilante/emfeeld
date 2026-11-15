# Particle Structural Revisions V1 — frozen bounded contract

Status: development candidate on `main` `7e6bd8c72cac7708ab3c2355cc1a98db09762133` (merged PR #13). Risk **R2** under `physicsvigilante/review_sandbox/REVIEW-RISK-POLICY.md`: physical initial-condition/identity semantics and recorded numerical evidence change. Keep the development PR draft/unmerged until full author qualification, separate-chat independent review and **distinct owner merge approval**. This document does not claim a new interaction law or teacher evaluation.

## Single reusable structural operation

Extend the existing **native model-format-1 revision store** with two explicit `proposal_version: 2` operations: `add_particle` and `remove_particle`. Do not add a separate model store or a solver, change source-only structural proposals or V1 property edits, introduce an apparatus-specific dispatch, or reuse a numeric trajectory as evidence for a different revision.

Both operations require `proposal_id`, `revision_id`, an exact `parent` model/revision/SHA256 reference, `category: structural_change`, `target_id`, `expected_role: particle`, explicit `scenario_intent`, and value `provenance` (origin, reason, evidence). A named physical entity is stable across descendants; array indices are execution implementation details, not physical identity.

### Add one particle

Illustrative data-only proposal envelope (replace placeholder reference with a real stored reference):

```json
{
  "proposal_version": 2,
  "proposal_id": "add-learner-body",
  "revision_id": "with-learner-body",
  "parent": {"model_id": "my-model", "revision_id": "root", "sha256": "EXACT_PARENT_SHA256"},
  "category": "structural_change",
  "operation": "add_particle",
  "target_id": "learner_body_2",
  "expected_role": "particle",
  "scenario_intent": "teacher_hypothesis",
  "provenance": {
    "origin": "illustrative_choice",
    "reason": "Investigate an additional independent test particle",
    "evidence": "Explicit teaching hypothesis, not a source-given body"
  },
  "particle": {
    "mass_kg": 0.000002,
    "charge_C": 3e-7,
    "position_m": [1.65, -0.45, 0],
    "velocity_m_s": [0, 0.15, 0.1]
  }
}
```

`particle` is a **complete explicit physical initial state**: required `mass_kg > 0`, complete three-vectors `position_m`, `velocity_m_s`, plus **explicit electric** `charge_C` (zero is allowed). All properties use SI units, strict existing numeric/vector/finite rules and the current single-domain scene parser. For gravity, `charge_C` may be omitted and is canonically expanded to **zero with a `source_convention` provenance record**; if explicitly present it must be physically zero, not an implied electric-gravity coupling. New particle attributes cannot be unknown or a synthetic unchecked `computed_result` in this slice. No auto-calculated orbit, velocity, charge or initial position is supplied.

Append only to `particle_order`; retain every source, other particle, physical value and provenance unchanged. The new particle ID must never have been used by *any accepted ancestor or sibling* (including previously removed particles and source IDs). Reject malformed, stale, wrong-role, duplicate, crashed/incomplete-store, concurrent-lock and unsupported inputs through the existing append-only proposal decision semantics. New particle insertion doesn't imply physical interaction with prior test particles, feedback on sources or time evolution of the insertion event.

### Remove one particle

Use `operation: remove_particle` and the complete **canonical `expected_particle` object** in place of `particle`; it must exactly match the named particle in the pinned parent (including the expanded gravitational default). Remove only that named particle from `entities` and `particle_order`; all other ordered entities remain unchanged. Removing the last test particle is allowed (static sources remain). Reject when a *surviving* computed property receipt depends on the deleted particle; never delete, retarget or claim renewed evidence for that receipt. Stale flags *on the removed particle* disappear; stale flags on all surviving entities remain unaltered.

Because prescribed sources and independent test particles have **no backreaction and no interparticle coupling**, changing test-particle membership does not automatically make a surviving source's or particle's previously recorded computed property stale. It is incorrect to reuse a previous numerical *run*, however; requested calculations are always re-executed and checked. The existing source structural edit's more conservative stale-dependency rule remains unchanged.

## Investigation and display semantics

Use the unchanged `ModelStore.revise`, `model_runs.execute` and `model_cli.apply_revision` interfaces. Existing observations named by stable `particle_id` lower to the new positional mapping for the specified revision. Compatible world-coordinate field/potential probes remain fixed and reusable. A previously authored observation referencing a removed particle is **explicitly rejected** (`wrong_role`/missing entity), never silently deleted, redirected or replaced. A fixed `entity_order` presentation including removed IDs or omitting added IDs is **explicitly rejected** until the author provides a new presentation document; no implicit repair.

A construction-valid particle addition at a singular launch or in an unsupported shell/plane trajectory regime is not a numerical/trajectory pass. Such failures remain in separate run attempt evidence. An accepted removal may yield a particle-free static model; no fictitious motion or extra particle is inserted. Sources are fixed, each particle is independently integrated only where supported, and numerical checks/thresholds/event policies are never relaxed to obtain success.

## Preserved history, provenance and evidence

The root's original/source/import bytes, previously accepted revision snapshots, exact SHA references, original model runs and every failed proposal remain byte-identical. A new revision is a distinct immutable full snapshot and its `operation` records the exact source-authored structural edit. A crash may reserve an identity; do not overwrite or erase it. The existing nonblocking structural-writer lock serializes identity checking across **source and particle** structural operations in this local store, not a distributed or adversarial guarantee. SHA256 inventories guard exact-byte integrity, not authentication of hostile writers.

## Frozen transfer plan and independent references

1. **E1 (electric, dynamic):** Existing negative infinite z-line charge + constant axial electric field + one charged test body. Add a differently charged/massed launched test body using a V2 proposal. Preserve original body's trajectory to numerical precision, match each body's z(t) to `z0 + vz*t + 0.5*(q/m)*Ez*t^2`, check both transverse motions with a separately implemented RK4 using independent line-field formulas. No new code for this arrangement.
2. **G1 (gravity, dynamic):** Two fixed asymmetric sources (one uniform solid sphere, one point) with two independent bodies. Remove **Body 1**, so surviving **Body 2 changes execution index from 1 to 0**, while its named identity and saved full-horizon physics remain unchanged. Validate field/potential independently and compare surviving trajectory with the baseline and separate gravitational RK4. Old investigation referencing removed Body 1 must explicitly fail; a new compatible Body 2 investigation succeeds, without changing source facts or numerical tolerance.
3. **T1 (preselected different geometry, static):** Fixed electric shell and point sources with **no initial particles**. Add an explicitly hypothetical charged particle; qualified **static** field/potential probes must remain numerically unchanged. Remove it again and show the sources, static evidence and original byte identities persist. Do not invent shell/plane motion support. T1 was chosen by the same author before implementation; its final replay is **not an independent hidden case**.

Adversarial cases: cross-role/new-ID collisions across siblings/removed ancestors; duplicate attempts and revision IDs; stale parent hashes; malformed/missing electric charge; gravity nonzero charge; negative/zero/booleans and nonfinite mass/charge/vector components; wrong expected canonical payload; removing a source by particle operation; dependent computation receipts; stale dependencies after removal; presentation order mismatch; missing named investigation IDs; singular launch not equated with construction rejection; source-only operations and v1 revisions unaffected; failed publication and interrupted lock behavior.

## Release and independent-review gates

Freeze the contract, implement once in source repo, run focused + existing tests with warnings as errors and E1/G1/T1 native runs against separately authored analytic/RK4 references. Publish source draft PR exact head SHA and tree only after self-checks; run fresh **Linux/Windows full clean install and real PyVista** CI with retained logs and artifacts. Inspect resulting output arrays, all source/particle mappings, exact model/run identities, numerical checks, and preserved baseline files. Retain failures without rewriting or weakening historical tests, tolerances or evidence.

Only **after** developer CI passes, publish a central packet under `review_sandbox/projects/emfeeld/pr-<source PR>/` with `REQUEST.md`, `STATUS.md` and `REVIEWER-PROMPT-01.md`, referencing exact SHA/CI/artifact digests. Supply the user a short copy-paste Chat B prompt. Chat B independently reads the pinned source and writes a **new** uniquely named review report directly into the central hub; it is a separate conversation, not necessarily a different model or human expert. Do not author Chat B's verdict. On user `Review complete`, fetch and triage, correct reproduced defects, add regressions, request only scope-appropriate follow-up, and retain originals. **Merge requires the owner's separate explicit approval**, then new main-branch CI and an append-only central merge report. No local Conda changes or resumed classroom evaluation.
