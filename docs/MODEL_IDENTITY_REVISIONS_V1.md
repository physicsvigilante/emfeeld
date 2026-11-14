# Model Identity and Revision Contract V1

**Status: proposed design contract, not an implemented API.** Contract draft 1, 2026-11-14. No model registry, revision executor, new input schema, physics calculation or new qualification is introduced by this document. Implementation needs a separately approved bounded task.

## 1. Basis and boundaries

The governing direction is [LLM-directed physical exploration](LLM_DIRECTED_EXPLORATION.md). Inspected main: `f4aebf692a5755c5d993904368612f91f77554a0`. Teaching Study V1 candidate: `d24fc47293d27e26d347675866dc73960d54ffc5`, PR #2, still draft/unmerged at inspection.

Relevant pinned sources:

- [V1 study contract](https://github.com/physicsvigilante/emfeeld/blob/d24fc47293d27e26d347675866dc73960d54ffc5/docs/TEACHING_STUDIES.md): baseline packet, one strength change, recorded previews.
- [study.py](https://github.com/physicsvigilante/emfeeld/blob/d24fc47293d27e26d347675866dc73960d54ffc5/src/emfeeld/study.py): `validate_study`, `STRENGTHS`, `source_index`, checks and captured-run identity.
- [scene.py](https://github.com/physicsvigilante/emfeeld/blob/d24fc47293d27e26d347675866dc73960d54ffc5/src/emfeeld/scene.py): strict source and particle fields, scene-v1 assembly.
- [physics contract](https://github.com/physicsvigilante/emfeeld/blob/d24fc47293d27e26d347675866dc73960d54ffc5/docs/PHYSICS.md): prescribed sources, potential references, test-body coupling and domain restrictions.
- [adopted verification decision](https://github.com/physicsvigilante/emfeeld/blob/d24fc47293d27e26d347675866dc73960d54ffc5/docs/CHAT_WORKFLOW_DECISION.md): same-author verification is not independent review.

V1 is a useful bounded comparison, not a model lifecycle: `study_version` is a serialization-format version; a source index is a position, not a persistent physical identity. The present operation allows only source charge/mass/density replacement. This design preserves V1 and introduces a proposed deterministic identity/revision adapter over existing laws, not a second solver.

## 2. Separate records, not a large framework

| Record | Meaning | What changes it |
|---|---|---|
| Model identity | One modeled physical system and its lineage | Explicitly starting another model; not a different question |
| Model revision | Immutable physical configuration, initial conditions, conventions and interpretation provenance | An explicit physical or interpretation correction, including a teacher hypothesis |
| Investigation | Named quantities or behavior to explore against pinned revisions | Different probes, observations, comparisons or teaching questions |
| Analysis specification | Requested analysis mode, horizon, sampling and numerical verification policy | A new numerical resolution, duration or analysis request |
| Run | One execution attempt with exact inputs, implementation identity, outputs and checks | Every actual execution, including failed attempts |
| Presentation | Display of identified results with its own settings | Camera, colour range, playback speed or selected frames |

An investigation can use the same revision many times. A revision can serve many investigations. `schema_version`, model/revision identity, run identity and software commit identity are distinct. Initially, immutable files and explicit references are enough: no database service, universal graph compiler, arbitrary plugins or general expression engine is required.

## 3. Stable physical identities

Assign a model ID and stable source/particle IDs at creation or explicit import. IDs are nonempty safe strings, unique within the model; use the existing observation-ID character/length convention for the proposed adapter. Reject duplicate IDs across sources and particles. Store role and source type separately from the ID. An optional display label is not the identity.

Examples: `source_left`, `sun`, `test_charge`, `planet_inclined`. Changing charge, radius or launch velocity must not rename the entity. Reordering a presentation list must not redirect a change. Identical numerical properties do not make two components one component. A copied distinct entity needs a new ID. Removed IDs must never be reassigned to a different entity; deletion itself is outside the first slice.

The model artifact uses ID-keyed entities. Runtime array indices are adapter outputs, never public revision targets. The adapter stores its exact ID-to-index mapping with each generated packet and run. Named particle references in new investigations are resolved against the pinned revision; existing observation IDs are retained. Reject missing, ambiguous or role-incompatible references before computation.

Legacy import must bind an explicit ID assignment to the exact original packet/scene bytes and their digest. Preserve that original artifact and record any expanded defaults as adopted conventions, not source givens. Import is explicit, not a silent conversion during an old CLI command. If the original array changes, its old assignment cannot be reused by index. Reordering requires an explicit identity-aware conversion, not nearest-position or equal-value matching.

Preserve imported accumulation and particle order internally for compatible lowering; do not expose ordering as a physical property. Identity stability is not a promise of bit-identical floating-point sums after a deliberately different ordering or environment.

## 4. Immutable revision lineage and integrity

A root has no parent. Every derived revision pins exactly one parent by model ID, revision ID and exact-byte SHA256. A change proposal includes those references and its own identity. No implicit `latest` reference is allowed during execution; resolve a user-friendly latest selector once before proposing and pin it.

Store the complete effective physical snapshot and its provenance together with the exact operation. This is simpler to inspect than a long delta chain. Keep root and all ancestors unchanged. Sibling scenarios are allowed; V1 has no automatic branch merging. Never silently rebase an edit onto a new parent.

Use an opaque unique revision ID plus an external exact-byte digest. The revision document contains its ID and parent reference, but not its own digest; this avoids a self-hash cycle. Preserve serialized bytes after publication. The same ID with different bytes is a conflict. Reject stale parent hashes and failed expected-value preconditions before creating an effective revision. No-op edits are reported without inventing another physical scenario. Reverting a value creates a descendant, not deletion of the intervening history.

A well-formed proposal that fails validation remains a retained rejected proposal, not an executable accepted revision. Constructing an accepted revision does not qualify every investigation or assert numerical success. Qualification records are attached to exact revision, analysis and implementation identities and never mutate the physical snapshot. A filesystem cache or saved output directory is not the identity system.

## 5. Typed changes and first-slice admission

Each proposal replaces one complete property with an explicit expected old value, new value, target ID, operation category, reason and provenance. A three-component vector is one property, not three independent edits. Values use the engine's unit-bearing keys and finite SI JSON numbers; reject strings, booleans, arbitrary expressions and unknown properties. Input preconditions use exact parsed-value equality, not solver tolerances. Negative zero and zero have the same physical value; byte-level differences remain visible in artifact hashes.

The first implementation should qualify the following bounded surface, not every imaginable revision:

| Category | Proposed allowed properties, subject to source/type checks | Physical meaning |
|---|---|---|
| Component property | Existing source strength keys; source `radius_m`, `center_m`, `direction`, `normal` where present; particle `mass_kg`, and electric particle `charge_C` | Another fixed prescribed configuration |
| Physical initial condition | Particle `position_m`, `velocity_m_s`, replaced as full vectors | Another launch at the model's explicit time origin |
| Prescribed external input | Existing uniform `field_N_C` or `field_m_s2` vector | Another constant field, not a waveform or an in-run change |

Only properties meaningful for the identified role/type/domain are admitted. Reject gravitational-particle charge changes as ineffective for this analysis, rather than advertising mixed coupling. Keep the model kind, component roles, source types and fixed-source/test-particle relationship invariant. Inherited finite-value, positive-radius, positive-test-mass and nonnegative-gravitational-source rules remain authoritative.

Boundary-condition changes, conductor grounding, potential-reference changes, coordinate-frame changes, source-type replacement, insertion/deletion, feedback connections and other structural edits are future categories, not aliases for scalar updates. Return `unsupported_change` with the required extension; do not choose a different physical model silently. The general principle includes these categories only where declared and qualified.

A radius edit keeps explicit total charge/mass fixed unless another qualified contract says otherwise; density consequently changes. A request to preserve density while changing radius is a coupled revision and is outside the initial one-property slice. Do not secretly recalculate total charge. Likewise, changing a source mass while retaining launch velocity must not silently enforce a circular orbit.

Changing a launch vector is not a numerical initial guess. Numerical initial guesses are not physical-model fields. Time horizon, sampling, event thresholds, error tolerances and display bounds belong to analysis/presentation; they are not accepted physical property edits. They remain explicit when lowered to the legacy scene/packet.

## 6. Provenance and incomplete information

Retain separate fields for scenario intent and value origin. Scenario intent is one of source interpretation/correction, teacher hypothesis or illustrative exploration. Value origin distinguishes supplied fact, source convention, adopted assumption, unit conversion, computed result, illustrative choice and unknown. Do not replace these distinctions with a single boolean `given`.

For every changed property, retain target ID/property, old/new values, scenario intent, origin, reason and evidence reference where claimed. The original root fact remains intact when a hypothetical descendant overrides it. A correction to source interpretation needs an explicit correction record, not a rewritten root. Display labels and natural-language explanations may aid review but do not authenticate evidence.

A computed input needs a traceable computation/check artifact with input and output identities, method and units. An unsupported LLM-derived number is not promoted to a verified engine result. If an edited property invalidates a recorded dependency, mark the dependent input stale. The first slice rejects execution requiring that stale input; it does not propagate arbitrary authored equations or silently freeze a claimed physical constraint. No unknown is filled with zero, standard gravity or a convenient classroom number without an explicitly hypothetical/illustrative scenario.

Keep unknown facts in draft records. Missing required numerical input blocks the affected lowering/analysis; irrelevant unknown descriptive geometry must not manufacture a requirement for an apparatus picture. A request to explore an explicitly limited subset needs its own declared scope, never silent removal of a component. The existing strict numerical engine is not thereby granted symbolic or underdetermined-system support.

## 7. Change planning and revalidation

Before any numerical work, the adapter must:

1. Resolve the exact model, parent and target identity; check hashes, duplicate/missing references, expected values and operation type.
2. Check physical requirements, provenance/dependency status, dimensions, finite shapes and source/particle validity; derive a candidate without mutating its parent.
3. Produce an explicit difference and assert that every unrequested physical field is unchanged. Rebuild the effective scene from the complete candidate and run the existing authoritative parser/admission checks.
4. Check the investigation against the modified model and classify the requested analysis. Static-only support does not imply trajectory support. Initial states on singularities or event surfaces, rest-launch policies and full-horizon availability must be reconsidered.
5. Execute only the admitted requested analyses; preserve per-request failures and compute the existing numerical checks without retrying with altered physics or silently relaxed tolerances.

Record both semantic change class and actual execution plan. A parameter edit may be mathematically simple, but the first implementation always rebuilds the small immutable source assembly and computes fresh requested results. It does not claim incremental solver-state reuse. A structural edit requires reassembly qualification; an unsupported analysis requires an explicit refusal, not a fallback solver. No compiled-model cache or smart backend-switching framework is required.

A previously qualified run cannot be reused merely because IDs match or the baseline passed. Reuse can be considered later only with a complete key covering effective physics, requests, constants, implementation, time grid and check policy. For this slice, no cross-revision numerical reuse is promised.

Keep construction validity, analysis admissibility, numerical execution, verification, request fulfillment and presentation availability separate. A valid static model can have an unsupported trajectory request. A convergence failure is not proof of physical impossibility. `no_event` is no detection at recorded resolutions, not absence proof. Preserve valid baseline and unrelated valid outputs when a descendant or individual request fails.

## 8. Investigations and unchanged backend interfaces

The proposed author-facing layer exposes named physical entities, not private array positions. It lowers to existing scene-v1 and observation-v1 packets; no `id` keys are injected into the strict legacy source objects. Retain exact generated bytes and the mapping receipt.

Physical entity data and physical initial conditions reside in the revision. Named observations, sample/time selectors and event conditions reside in the investigation. Numerical horizon/check policy reside in the analysis specification. Bounds, camera and colour scales reside in presentation. Their current co-location in a legacy packet is an adapter detail, not a reason to reauthor the model.

A new query does not create another physical revision. A revised physical model can use the same investigation, after revalidation. World-coordinate probes remain fixed when sources move; source-attached probes or moving observation surfaces must not be inferred from names. Such relationships require an explicit future qualified contract. Source-type changes and changing entities' roles are not supported by this first adapter.

Backward compatibility is mandatory: old scenes, packets and study-v1 documents still mean exactly what they meant. New model/revision envelopes must not be auto-detected as legacy studies. An explicit conversion tool may create new artifacts while retaining old bytes and results. The adapter may reuse V1 capture/check/presentation functions after separate approval, but must not loosen `validate_study` to make arbitrary changes appear to be old strength-only studies.

## 9. Runs, comparisons and educational meaning

Every run pins model/revision, investigation, analysis specification, adapter mapping, exact generated input, implementation and constant identities, and records its own outputs and verification. Failed and interrupted attempts remain distinct; no overwrite of prior evidence. A stricter tolerance is a new run/analysis, not a model revision.

A preview identifies the run whose arrays it shows and does not integrate secretly. A result from one revision cannot be attached to another merely because shape and initial states agree. Any recalculated field slice must be tied to the recorded effective model and compatible constants/field implementation. Hash checks detect corruption; they do not establish physical fidelity or adversarial authenticity.

Compare only compatible quantities, units, frames, times and potential conventions. Show event states at their own event times, not as simultaneous samples. A trajectory crossing one event surface is not a material collision. Changed source geometry can require a newly declared common display region; never change physical coordinates to improve framing. Direction-only arrows are not strength comparisons.

A pair of stationary scenarios is not time evolution. Connecting independent scenario snapshots with animation is presentation interpolation unless separately modeled dynamics exist. Energy differences between two hypothetical external fields are not automatically the work of a modeled charging/accretion process. There is no quasi-static-equilibrium solver added here.

Sweeps are a later qualified collection of individually validated revisions, normally siblings of a pinned parent unless a different sequence is declared. Sensitivities require a specified observable, units, perturbation regime, convergence checks and handling of event/discontinuity failures. A finite difference is not automatically a derivative proof. No sweep or sensitivity engine is implemented or authorized by this contract.

## 10. Acceptance gate and next implementation boundary

The prospective acceptance cases and self-review are in [the review plan](MODEL_IDENTITY_REVISIONS_V1_REVIEW.md). They are requirements, not executed tests.

The first implementation should add only explicit import, stable ID resolution, immutable single-parent revisions, one-property typed edits, and translation to existing analyses with retained provenance. Qualification should demonstrate one source-property revision and one true launch-condition revision reused across multiple investigations. Use electric and gravitational examples without question-specific production branches.

Do not start implementation, broaden source laws, modify numerical/event algorithms, invent boundary support, run sweeps, merge PR #2 or rewrite historical evidence as part of this documentation milestone. A successful contract review is not runtime qualification. Preserve the adopted same-author/user-acceptance gate unless a separate reviewer is actually engaged.
