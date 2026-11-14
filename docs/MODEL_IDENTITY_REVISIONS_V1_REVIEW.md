# Model identity/revision V1: design review and prospective acceptance

Date: 2026-11-14. Status: **same-author design review; implementation and runtime qualification NOT RUN**. This is not an independent review. Companion [contract](MODEL_IDENTITY_REVISIONS_V1.md) and [user principle](LLM_DIRECTED_EXPLORATION.md).

## Evidence inspected

Main was `f4aebf692a5755c5d993904368612f91f77554a0`. PR #2 was draft/unmerged at `d24fc47293d27e26d347675866dc73960d54ffc5`. Its current study contract and `study.py` were reread, together with `scene.py`, the physics contract, main's AGENTS guidance and the adopted verification decision. The contract's pinned links locate those exact sources. No local user working-tree state is accessible or inferred.

Observed facts: study-v1 is strength-only, addresses sources by index, derives a deep-copy variant, preserves captured results, and is not a general revision system. The strict scene parser accepts only existing physical source keys and particle fields; persistent IDs cannot simply be added to those dictionaries. Shell/plane trajectory restrictions and the separation between physical kinds remain. These findings motivate an adapter, not a replacement solver.

The user's new foundational text is recorded unchanged under 'User's principle' in the companion document. Its application notes and all lifecycle/acceptance details are proposed design decisions by the assistant, not claims from the source code.

## Design decisions checked for internal consistency

- Prefer explicit immutable files over a registry service or universal graph compiler. Full effective snapshots keep inspection simple.
- Separate model identity, revision, investigation, analysis, execution and presentation. Format version is not physical revision history.
- Keep physical IDs stable; runtime source/particle indices are generated and recorded, not author-facing revision targets.
- Pin parent revision and exact-byte digest. An old-value check alone is insufficient when a different parent has the same scalar.
- Do not include a document's own digest in its hashed body. Store it in the external reference/manifest.
- Always validate and freshly compute modified scenarios in the first implementation. A semantic parameter update does not promise backend-state reuse.
- Preserve the existing packet contracts. Do not widen study-v1 silently; qualification of a future adapter is separate.
- Initially reject stale computed dependencies instead of inventing automatic formulas. Treat density-preserving radius changes as coupled edits, not an implicit total-charge adjustment.
- Keep structural/boundary changes, gauge changes, sweeps and sensitivities explicit future scope. Do not equate their absence with failure of supported forward teaching simulations.
- Treat the original root and teacher hypotheses separately, including when an illustrative numerical instance is chosen for an underspecified statement.

No claim is made that this checklist proves the design correct. Its falsifiable obligations are below.

## Prospective qualification cases — none executed in this milestone

| ID | Case | Required outcome |
|---|---|---|
| ID-01 | Give two numerically identical sources distinct physical IDs | Both remain present; no deduplication |
| ID-02 | Reorder display entries, then change `source_left` | Same physical source changes; runtime map is explicit |
| ID-03 | Duplicate, absent or wrong-role target ID | Reject before lowering/calculation |
| ID-04 | Apply legacy ID assignment to differently ordered original bytes | Reject stale import; no index-based reassignment |
| REV-01 | Create two hypotheses from the same parent | Distinct siblings; parent/root bytes unchanged |
| REV-02 | Parent digest changed but expected scalar still matches | Reject stale parent, no automatic rebase |
| REV-03 | Reuse revision ID with different content or overwrite old output | Reject without destroying existing artifact |
| REV-04 | Revert a property to its root value | New descendant preserves intervening history |
| EDIT-01 | Change one existing source strength/property | Only target property and associated provenance differ |
| EDIT-02 | Change a whole physical launch-velocity vector | New initial-value scenario; no solver guess or hidden launch correction |
| EDIT-03 | Change a constant uniform field vector | New prescribed scenario; no implied time-varying field |
| EDIT-04 | Change radius while requesting unchanged density | Refuse unsupported coupled constraint; no hidden charge computation |
| EDIT-05 | Negative gravity mass, zero test mass, malformed vector or nonfinite value | Retain rejected proposal; valid parent unaffected |
| EDIT-06 | Structural replacement, grounding, waveform or gauge/frame change | Explicit unsupported category; no scalar-substitution fallback |
| QUERY-01 | Same revision, different probes or saved-state requests | New investigation, unchanged physical model |
| QUERY-02 | Same revision, smaller numerical tolerance or different horizon | New analysis/run, not a physical revision |
| QUERY-03 | Move source with an unchanged world-coordinate probe | Probe stays fixed; no invented source attachment |
| QUAL-01 | Valid baseline, singular revised launch | Revised analysis fails explicitly; baseline still accessible |
| QUAL-02 | Rest launch with an initially ineligible turning-event request | Retain eligible other outputs; no tiny velocity insertion |
| QUAL-03 | Shell/plane static probes plus a trajectory request | Static support does not hide unsupported motion |
| QUAL-04 | A changed property invalidates a computed input dependency | Block affected execution as stale; do not call it a new given |
| QUAL-05 | Unknown required numerical fact versus irrelevant unspecified appearance | No invented numerical input; optional appearance does not become physics |
| QUAL-06 | Well-formed conductor substitute mislabeled as insulating | Validator cannot certify fidelity; independent interpretation record/review required |
| RUN-01 | Show saved arrays after another revision was executed | Exact model/run identity remains bound; never silently use newest output |
| RUN-02 | Matching array shapes but wrong revision/results | Refuse misattachment; shape checks alone are insufficient |
| RUN-03 | Change camera or replay speed | Presentation changes only; no reintegration or new physical revision |
| CMP-01 | Events occur at different times or one is not detected | Label separate events/failure, no false equal-time comparison |
| CMP-02 | Future sweep has one invalid member | Retain failure and valid siblings; no aggregate success masking |

A passing implementation must preserve old contract meaning, tests, source formulas, restrictions and frozen evidence. Verify exact published bytes separately from semantic model comparisons. Test counts and prior CI successes must not be carried forward as new execution evidence.

## Review independence and teaching acceptance

Before a future implementation is merged, assess identity/revision logic and physical interpretation separately from numerical reference agreement. Independent review may be performed by another reviewer with the pinned inputs, but is not asserted here. If work continues under the existing chat-only decision, label it same-author verification and obtain explicit user acceptance; never rename a second self-check an independent review.

Teacher-task acceptance is separate: a teacher should reuse one root model for a source-change question and a launch-condition question, identify what changed, and compare the corresponding verified results without copying the entire physical definition. A teacher must be able to see that a hypothesis is not a source fact. Successful unit tests or attractive images alone do not establish this outcome.

The composability claim is disproved if a second supported arrangement needs new apparatus-specific production code, if model edits rely on unverified LLM intermediate answers, if array reordering redirects edits, if each new investigation requires reauthoring the system, or if the display cannot identify its revision/run.

## Scope and publication

Only three new Markdown documents are proposed. No production, schema, test, example, CI, dependency, historical-report or source-PDF file is changed. No tests, builds, simulations, renderings or replays were run for this design. The documents should be published on a separate documentation branch from inspected main, leaving PR #2's qualified candidate unchanged and unmerged. Contract approval and runtime implementation approval remain separate decisions.
