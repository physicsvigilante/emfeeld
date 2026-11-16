# Bounded Scenario Ensemble V1 — design contract

**Design candidate:** 2026-11-16. **Tracking:** [Issue #21](https://github.com/physicsvigilante/emfeeld/issues/21). **Provisional base:** merged EM Fields main SHA f0fc993dae1831432ca43b651a12e64fa0b2fdd5, canonical Git tree a9cee83857195f0c2d4c36d4741559094fad64bd. The PR #20 post-merge Linux/Windows and viewer verification must complete before this new source feature can be integrated. Design is not runtime qualification.

**Risk R2:** evidence meaning, bounded orchestration, derived comparison completeness, revision identity and saved-run provenance. The owner's standing direction allows bounded development without routine approval prompts, but independent-context R2 review and blockers still halt integration; material physical-law scope changes require a separate decision.

## Purpose

An LLM/teacher can author **2–4 independent physical hypotheses** as separate V3 atomic child revisions of one exact parent, run explicitly authored native investigations for each, and compare every completed child to a **freshly recomputed common baseline** using the existing sealed cross-scenario comparator. No per-question production Python, new numerical solver, symbolic constraint engine or change to physical laws.

These hypotheses are **independent alternative prescribed-source scenarios**, not sequential physical times or a charging/accretion transition. Comparisons are signed right-minus-left observations, never automatically source-motion work or a derivative.

Keep the old one-property sweeps unchanged. It intentionally varies one complete supported property under the old strict same-investigation model_runs.compare_runs semantics. This new ensemble must instead reuse existing ModelStore.revise V3, model_runs.execute/inspect_run, and scenario_comparisons.compare/inspect with different authored named observations when components change.

## Proposed CLI and exact input grammar

    python -m emfeeld.scenario_ensembles run ENSEMBLE.json --store EXACT_STORE --using SEALED_PARENT_RUN --output FRESH_DIRECTORY
    python -m emfeeld.scenario_ensembles inspect OUTPUT --store EXACT_STORE --using SEALED_PARENT_RUN

One strict UTF-8 JSON document parsed with existing duplicate-key, unknown-key and nonfinite input rejection. Exact top-level fields:

- ensemble_version: JSON integer 1, never bool/float.
- id: one safe study identifier short enough to form deterministic native run IDs.
- parent: one exact {model_id, revision_id, sha256} reference; never implicit latest.
- source_run_sha256: raw SHA256 of the separately supplied sealed parent run.json.
- members: 2–4 ordered author-declared objects.

Each member has exactly {id, proposal, investigation, analysis, presentation, pairs}.

- id: safe unique ensemble member ID. It is an orchestration ID, not a physical entity ID or a source name.
- proposal: **complete existing proposal_version-3 atomic_change** (2–4 independently qualified V1/V2 edits), with exact proposal_id, revision_id and parent equal to ensemble.parent; author supplies all stable target IDs and literal provenance. Do not invent or silently regenerate physical IDs, masses, launch data, geometric constraints or absent observation requests. Source/particle identity reuse across accepted siblings is forbidden by existing history rules; reject explicitly.
- investigation, analysis, presentation: complete existing native named V1 objects for this variant, authored independently when membership changes. Do not silently carry a removed body's old observation or presentation entity_order into another revision.
- pairs: 1–16 complete existing cross-scenario V1 pair descriptors, explicitly naming LEFT baseline observation ID, RIGHT variant observation ID, kind and stable particle ID where needed. Coordinates, ordered potential-difference endpoints, units and actual saved times are checked by the existing strict comparator, never inferred from name or array position.

A sample request skeleton (deliberately not executable without actual parent SHA and full V1/V3 objects):

    {
      "ensemble_version": 1,
      "id": "two-electric-hypotheses",
      "parent": {"model_id": "electric-example", "revision_id": "root", "sha256": "ACTUAL_SHA"},
      "source_run_sha256": "ACTUAL_SEALED_PARENT_RUN_JSON_SHA",
      "members": [
        {"id": "hypothesis-A", "proposal": {"...": "COMPLETE_V3"},
         "investigation": {"...": "NATIVE_V1"}, "analysis": {"...": "NATIVE_V1"},
         "presentation": {"...": "NATIVE_V1"}, "pairs": [{"...": "EXPLICIT_V1_PAIR"}]},
        {"id": "hypothesis-B", "proposal": {"...": "COMPLETE_V3"},
         "investigation": {"...": "NATIVE_V1"}, "analysis": {"...": "NATIVE_V1"},
         "presentation": {"...": "NATIVE_V1"}, "pairs": [{"...": "EXPLICIT_V1_PAIR"}]}
      ]
    }

No untyped formula strings, external template fetching, hidden analysis selection, automatic LLM source facts, or arbitrary generated loops.

## Preflight, provenance and output safety

Before creating any output directory or attempting revisions:

1. Validate all nested grammar, unique member/proposal/revision IDs, counts, exact parent pins, valid physical ID syntax and stable role constraints. Reuse strict V3 validation; do not create a second permissive physics-admission path.
2. Load the exact immutable model parent from the existing ModelStore. Verify the separately supplied parent native run through existing model_runs.inspect_run, require status complete and execution_complete true, matching exact model root and revision, and the declared raw run.json SHA. Check its native observation IDs and map receipts. A failed, interrupted, stale, corrupted or partial template is a hard preflight failure with **zero** newly accepted revisions.
3. Refuse an existing output directory or symlink and any output inside a model store, original run, user input or other protected path. Resolve Windows/Posix path aliases safely; no overwrite or deletion of prior evidence.
4. Check all authored proposal/revision identifiers against already reserved store identities before creating a new run. Do not promise atomic pre-reservation against separate hostile/concurrent writers; the existing local structural-writer lock and exact history validation remain authoritative on publication.

Physical validity of a hypothetical final snapshot is decided by the existing V3 native revision validator when that particular member is attempted. This means a member may reject without invalidating other independent siblings, and the original parent always remains byte-identical.

## Execution state machine

1. Create a fresh output, preserve exact raw ENSEMBLE.json and source parent-run provenance, and write a pending/started marker. The marker is **not** a completion claim. A crash or unhandled exception must leave an inspectable incomplete attempt; never mark it complete or silently recover/overwrite.
2. **Recompute baseline** from the *captured parent run's original investigation/analysis/presentation*, not an inherited result or cached numeric pass. Save its new exact run reference, native packet/mapping, diagnostics and full sealed output. If baseline is rejected/partial, all 2–4 hypotheses are **not_attempted** with explicit reason, not fabricated zero values or unrecorded omission.
3. In declaration order, call ModelStore.revise **once** per member with its unchanged complete V3 proposal. Record native attempt decision and source bytes. A rejected/no-op/unsupported member remains a recorded **rejected** item, and other independent siblings continue when safe.
4. If a revision is accepted, execute its completely authored named native investigation through model_runs.execute, seal and inspect that run. A construction acceptance is **not** a numerical pass. Rejected/partial native analysis is recorded, not repaired by silently moving a probe or changing tolerance.
5. If both *fresh* baseline and member runs are complete, construct one existing comparison_version-1 request using exact SHA256 of both new run.json files and the member's authored pairs. Call scenario_comparisons.compare then its strict deterministic inspector. An absent legitimate observation leads to typed unavailable and a **partial** member; invalid source evidence leads to hard integrity failure and cannot be disguised as missing data.
6. Publish summary.json and final top-level integrity.json only after all declared members are accounted for. **Complete** means baseline complete **and each** member accepted, native run complete, and every declared pair comparison complete. Otherwise aggregate **partial**, retaining status, exact reason and evidence for all entries. For unexpected crash, no completion marker and no automatic retries.

Each member's source revision, run and comparison is a separate immutable outcome, not an intermediate step of a physical time transition. The scenario orchestration's own output files are fresh, and the model store grows only through intentional append-only proposal/revision writes.

## Output and deterministic read-only inspection

Save exact input bytes, parent/store/run pins, baseline, per-member proposal and native decision, member reference, member native run and cross-scenario comparison when attempted, summary, readable report, final integrity inventory. Bind every result to its original physical IDs, measured quantities/units, explicit common coordinates and saved times, as returned by the existing qualified subsystems. A missing member must not disappear from the summary.

Read-only inspection must verify top-level inventory and source spec SHA; inspect pinned original template, fresh baseline and all member runs; inspect every completed cross-scenario comparison using its own native two-source hashes and deterministic recomputation; compare stored decisions, references, exact member order and aggregate completion with actually retained facts. No new integrations, field evaluation or implicit latest resolution.

No claim of authenticity against an attacker who rewrites and re-seals all unkeyed file hashes, no distributed crash-safe ACID and no teaching-usefulness certification.

## Preselected native E1/G1/T1 transfer cases

These are author-selected qualification arrangements, not blind independent reviewer tests.

**E1 electric:** negative line + +z uniform field with test_charge. Two separate V3 sibling hypotheses involving supported line/source property revisions and a test-body insertion/removal. Each variant has its own valid observation list. Compare same world point E field vector and magnitude, same ordered potential-difference endpoints and surviving test_charge position/velocity at **identical actual saved time**. Independently check line + uniform expressions, axial analytic acceleration and separate RK4. A deleted/added body is explicitly unavailable or refused, never retargeted by index.

**G1 gravity:** fixed sphere + point with body_1 and body_2. Two distinct V3 siblings combine a sphere mass/property edit and independent test-body insertion/removal. Compare common named body positions/velocities and fields at exact saved physical time, independently verifying solid sphere inside/outside field and point-gravity formulas and trajectories. A newly added body absent from baseline cannot be mapped to another array index.

**T1 static electric:** shell + centered point without particles. Two V3 siblings with distinct charge edits on different existing sources. Compare field and ordered potential differences at non-singular probes inside/outside the shell; do not request unsupported shell motion or conductor effects.

## Minimum adversarial qualification

- Malformed/duplicate JSON keys and IDs, zero/one/five members, wrong parent SHA, stale source-run pin, duplicate or reused sibling physical ID including removed ancestors, wrong role/domain, unsupported source/particle type, partial vectors and nonfinite input values.
- Baseline partial/rejected/unsealed/corrupted: no subsequent proposal executed; member rejected after one valid V3 operation: zero accepted intermediate revision; second member failed while first member complete: preserve first success, record second failure and aggregate partial.
- Physically accepted but numerically partial trajectory; removed/reindexed particle, stale named presentation reference; unmatched point/ordered endpoints/time and legitimately unavailable baseline body; malformed authored check and inconsistent NPZ source evidence hard-refused.
- Output aliases and symlinks, previously consumed proposal/revision/run IDs, concurrent local writer, interrupted output without final status marker, tampered or re-signed top-level completion, path traversal, failure to verify nested run/comparison seals.
- Immutable original import, root revision, prior native run, existing sweep/derived/comparison semantic behavior, all historical regression fingerprints. No tolerance relaxation or silent filtering of negative runs.

## Review and release gates

- First qualify PR #20 merged-main Linux/Windows and viewer workflows and publish its final central release record. This design may be discussed or committed before release qualification, but a new source implementation must not be merged onto an unqualified base.
- Isolated source branch and additive orchestration module, focused tests, E1/G1/T1 native transfer and separate references, exact-head full Linux/Windows clean-install and separate real-PyVista runs. Preserve red first attempts.
- Publish exact-head review packet to central physicsvigilante/review_sandbox after author qualification. **Separate Chat B independently authors R2 findings**, potentially proposing new adversarial cases. Never invent verdicts or bypass blockers.
- Under standing owner autonomy, guarded merge only with unchanged reviewed source SHA/tree, qualified exact-head CI and no unresolved material blocker. New physical laws, consequential scientific claims or departure from this bounded scope interrupt for owner decision. After merge, fresh main Linux/Windows and PyVista CI and append-only final central report.

User's local Conda installation and saved studies remain untouched; classroom evaluation remains paused, and all sources/test particles retain the previously qualified nonrelativistic prescribed-source physics.