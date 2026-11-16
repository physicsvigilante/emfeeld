# Atomic Scenario Revision V1 — frozen design contract (design only)

**Design freeze:** 2026-11-16. **Design base:** merged PR #14, main commit
8fe6331aefa252585b3b90f54b8ee7cbbac5e605, canonical Git tree
c274d94dd2185dcecdfca735e2951edae3e3d835.
**Tracking:** [issue #15](https://github.com/physicsvigilante/emfeeld/issues/15).
**Status:** owner approved this **design-freeze step**, not source implementation,
merge, teaching evaluation or a local Windows/Conda update.
This document proposes a future feature; no V3 transaction is currently implemented.

**Risk:** R2 (physical model identity, initial conditions, derived evidence and
rejection semantics). Follow the central
[review risk policy](https://github.com/physicsvigilante/review_sandbox/blob/main/REVIEW-RISK-POLICY.md)
and [independent-context protocol](https://github.com/physicsvigilante/review_sandbox/blob/main/PROTOCOL.md).

## 1. Physical purpose and limits

Permit a teacher/LLM to author **one coherent alternative prescribed physical
configuration** comprising 2–4 independent, explicitly stated changes. Accept
exactly one immutable descendant of a pinned parent only if the entire final
snapshot is structurally and physically valid. A teacher need not accept
artificial intermediate scenarios just to replace a source while adding a body.
Recompute investigations after acceptance; do not reinterpret the transaction
as changes occurring over physical time.

Build on the existing model-format-1 store, proposal-v1 property edits,
proposal-v2 source/particle structural edits, native named observations,
strict scene parser, existing DOP853 solver and recorded-run integrity
mechanisms. **No** new laws, numerical thresholds, time-dependent event
physics, backend, material boundary conditions, branch merges, symbolic
constraints, source backreaction, particle interactions, runtime interpolation,
viewer subsystem, dependency packages, or second model store.

## 2. Proposal envelope and admitted member grammar

A single proposal-version-3 JSON document (strict unknown-key and duplicate-key
rejection) has **exactly** the top-level keys:

- proposal_version: integer 3 (not boolean or 3.0)
- proposal_id and revision_id: fresh, valid IDs under the existing ID grammar
- parent: exact model_id, revision_id, sha256 reference
- category: literal "atomic_change"
- scenario_intent: one existing INTENTS value for the entire hypothesis
- changes: ordered array of **2–4** members

Every member has exactly these common keys:
operation, category, target_id, expected_role, provenance.
The provenance object is the existing exact {origin, reason, evidence} record.
There is no member-level scenario_intent: the one transaction is the
user-declared scenario. Every supplied new value has a separately recorded,
truthfully attributed origin. Reused parent facts and provenance are untouched.
The complete authored V3 envelope is saved unchanged under the descendant's
operation, and exact input proposal bytes are retained in the proposal attempt.

Allowed member forms (additional keys depend on operation; no unknown keys):

| operation | category | expected_role | required additional keys |
|---|---|---|---|
| replace_property | component_property / initial_condition / external_input | source / particle | property, expected_value, value |
| add_source | structural_change | source | source |
| remove_source | structural_change | source | expected_source |
| add_particle | structural_change | particle | particle |
| remove_particle | structural_change | particle | expected_particle |

The property member uses **only the already-qualified V1 editable role,
property and domain combinations**. One complete vector is one value; no
partial-vector edits. Existing strict nonboolean finite SI number checks, unit
keys, geometry and provenance rules apply. Parent expected_value follows V1
physical numeric equality (integers versus numerically equal floats allowed,
but boolean is never numeric); removal expected_source/expected_particle
must match the **complete canonical parent properties**, using the
existing V2 exact encoded-object comparison, not nearest-match, tolerance or
array index.

**V1 narrow provenance rule:** V3 members may introduce only explicit literal
values with origins supplied_fact, source_convention, adopted_assumption,
unit_conversion or illustrative_choice. Reject origin unknown, computed_result
and a member-supplied computation receipt. Existing computed-result properties
and receipts *not edited* are preserved and invalidated where necessary. A
future composite-computed-input contract would need separate qualification.
Do not certify source facts from an LLM-authored origin label.

## 3. Illustrative E1 proposal shape

The following is **illustrative, not executable as written**: replace the
placeholder parent SHA with the actual imported model reference. For E1,
import examples/marker_regression/E1.json with source IDs negative_line and
axial_field and particle ID test_charge. All source values below are intentional
hypothetical choices, not textbook claims.

~~~json
{
  "proposal_version": 3,
  "proposal_id": "E1-atomic-replace",
  "revision_id": "E1-replaced-line",
  "parent": {
    "model_id": "E1-atomic-model",
    "revision_id": "root",
    "sha256": "ACTUAL_PARENT_SHA256_FROM_IMPORT"
  },
  "category": "atomic_change",
  "scenario_intent": "teacher_hypothesis",
  "changes": [
    {
      "operation": "remove_source",
      "category": "structural_change",
      "target_id": "negative_line",
      "expected_role": "source",
      "provenance": {
        "origin": "illustrative_choice",
        "reason": "Remove the former prescribed line for an alternative setup",
        "evidence": "E1 atomic design case, not a source given"
      },
      "expected_source": {
        "type": "line",
        "center_m": [0, 0, 0],
        "charge_per_m_C_m": -2e-11,
        "direction": [0, 0, 1],
        "reference_radius_m": 1
      }
    },
    {
      "operation": "add_source",
      "category": "structural_change",
      "target_id": "shifted_positive_line",
      "expected_role": "source",
      "provenance": {
        "origin": "illustrative_choice",
        "reason": "Test a spatially shifted prescribed positive line",
        "evidence": "E1 atomic design case, not a source given"
      },
      "source": {
        "type": "line",
        "center_m": [0.4, -0.3, 0],
        "charge_per_m_C_m": 1e-11,
        "direction": [0, 0, 1],
        "reference_radius_m": 1
      }
    }
  ]
}
~~~

The exact old-source payload must be checked against the canonical imported
snapshot (including any expanded defaults), **not copied blindly** from this
illustration. The final dynamic scene has the retained axial_field and
test_charge plus shifted_positive_line; the original source/run stay intact.
The initial particle is not at the new line singularity.

## 4. Identity, ordering and transaction semantics

1. Pin **one** valid parent by exact byte SHA256, not implicit "latest".
   All expected values and role/type/domain checks use that same parent,
   never an intermediate partially edited candidate. Parent must still read
   with its exact reference when the write lock is held.
2. No two members may target the same target_id, even if different properties
   of one entity or different operations are requested. A remove-and-add
   under the same ID, a source-type replacement under an existing ID, or a
   reference to a newly added entity within this same transaction is
   unsupported. Existing identities are never retargeted by execution index.
3. Each inserted ID must be absent from **all accepted ancestor/sibling
   snapshots**, removed historical IDs included, and from all other members.
   Reuse the existing complete-history identity scan and structural-writer
   lock, including failure-closed behavior for incomplete/disconnected history.
   This is a local-store identity guard, not a distributed hostile-writer lock.
4. The final source_order/particle_order preserve the relative order and
   properties of surviving parent entities, with newly added entities appended
   **in member order within their role**. This intentionally fixes an
   implementation ordering rule; it is not a statement that order changes
   physical identity or guarantees bitwise equal floating-point sums.
5. Stage changes in a private in-memory candidate. Validate individual
   explicit inputs/preconditions and the **entire final** model snapshot;
   do not repeatedly publish or validate sequential intermediate revisions.
   Removing the parent's only source is allowed *within* a replacement
   transaction only when the final snapshot still has at least one qualified
   source. Removing the final source without replacement is rejected.
   Removing the final particle remains allowed.
6. On final construction validity publish exactly **one** full immutable
   descendant using the store's exclusive revision directory and write
   its reference marker last. Record exactly one proposal decision and one
   parent link. A later run may fail; successful model construction is not
   a numerical or teaching pass.
7. On any prepublication error, preserve the identifiable proposal, its
   pending/rejected decision and attributable error; create **no accepted
   intermediate descendant**. Malformed input that cannot be parsed or
   identified may fail before a normal attempt record; do not misreport it
   as an accepted/rejected physical calculation.
8. An interrupted write may reserve a revision ID or leave a lock or
   incomplete directory; never overwrite or automatically clean it up.
   A reference marker, model byte hash and retained evidence are not
   crash-proof ACID transactions or cryptographic authentication.
   If a crash happens after a published reference marker but before a
   decision marker, report an inconsistent/incomplete attempt requiring
   inspection rather than guessing that the transaction was cleanly rolled back.

**Proposed implementation boundary:** V3 dispatch in ModelStore.revise
only; one small atomic-revision helper using existing pure validators,
snapshot format, history scan, structural lock and _publish. Factor shared
pure V1/V2 preconditions only as needed, while retaining v1/v2 accepted and
rejection behavior. Do not implement V3 by calling ModelStore.revise or
v2 publish sequentially for every member: that would publish unapproved
intermediate models and violate atomic construction.

## 5. Provenance, computed receipts and stale dependencies

A V3 proposal changes only the specified member values/membership,
canonical parser defaults for genuinely added entities, transaction operation,
revision identity/parent, scenario intent and necessary stale flags.
No source or launch field gets inferred from another change.

- If a removed entity is referenced by **any surviving computed property
  receipt**, reject the entire transaction with an explicit dependent-entity
  error. If both the dependent and its source are removed, no dangling
  surviving receipt remains; preserve earlier snapshots and their old receipts.
- For property edits, initialize invalidation from the **union** of all
  replaced (target_id, property) keys. Transitively mark surviving computed
  properties stale when they depend on changed/stale inputs; retain their
  values and original receipts. A directly overwritten property receives
  the new declared literal provenance, not its former computed receipt.
- For **any source insertion or removal**, conservatively mark **all**
  surviving computed-result properties stale (as source V2 does), including
  source-set effects not captured by scalar dependency lists. Deleted-entity
  stale flags disappear; inherited unrelated stale flags persist.
- Particle insertion/removal alone does not invalidate otherwise surviving
  sources or independent test-particle computations: there is no backreaction
  or interparticle coupling. Property edits combined with particle operations
  still trigger their ordinary transitive invalidations.
- Neither a stale flag nor a successful run is an automatically recomputed
  computed-input receipt. The existing analysis admission must still refuse
  a run requiring stale inputs, until an explicit separately supported
  hypothesis/revision supplies valid evidence.

The final snapshot must pass the existing model validator and legacy
scene_from_dict checks once fully assembled; request lowering must separately
recheck source and particle ID mappings, unsupported shell/plane motion,
singular launches, named observations, presentation entity_order, physical
time and numerical settings. Prior saved runs are **never** rebranded or
reused as proof of the final revision.

## 6. Frozen acceptance arrangements (project-informed, not hidden)

Use the already committed input scenes and independently expressed physical
reference calculations. Record original import bytes, exact generated
references, a complete baseline run, a new final run, negative attempts and
all hash inventories. The three scenarios are preselected by this author:
they are **not** unseen or reviewer-independent transfer cases.

**E1 — dynamic electric, source replacement.**
Input examples/marker_regression/E1.json: negative z-line
(lambda = -2e-11 C/m at origin), axial E_z = +0.15 N/C and
charged body (q = 1e-6 C, m = 1e-6 kg, x0 = [1,0,0] m,
v0 = [0,0.55,0.1] m/s), four seconds, 101 samples.
In one two-member transaction remove negative_line and add
shifted_positive_line with lambda = +1e-11 C/m, center
[0.4,-0.3,0] m, z direction and 1 m logarithmic reference radius.
Keep axial_field and named test_charge. Verify unchanged baseline
bytes, retained physical body attributes/provenance, final named
source mapping, final potential and field from independent line +
uniform expressions, axial position
z(t) = z0 + vz0*t + 0.5*(q/m)*E_z*t^2,
and transverse full-horizon trajectory against an independently
implemented fixed-step RK4/refinement reference. Do **not** assert
baseline trajectory equals replacement trajectory.

**G1 — dynamic gravity, mass change plus body insertion.**
Input examples/marker_regression/G1.json: fixed sphere source_A,
mass = 2e9 kg, center [-1.5,0,0] m, radius 0.75 m; point
source_B mass 1.3e9 kg, center [1.8,0.5,0] m; independent
body_1, body_2; five seconds, 101 samples. One transaction
replaces source_A.mass_kg with **2.5e9 kg** and adds named body_3
with explicit mass 0.7 kg, position [0.3,0.9,-0.4] m and
velocity [0.03,-0.07,0.02] m/s. Gravity charge is omitted and
must expand to a provenance-labelled zero, not mixed coupling.
Retain both original bodies' initial conditions but recompute
all **three** trajectories and verify each against independent
sphere interior/exterior and point-gravity expressions and
separate numerical integration. Their trajectories need not match
the baseline because the field changed.

**T1 — static electric, two distinct property edits.**
Input examples/structural_revisions/T1.json: 2 m shell
at origin with charge +2e-9 C and point at origin with charge
-5e-10 C; no particles. In one transaction change the shell
charge to +3e-9 C and the point charge to -8e-10 C.
Use source IDs shell and central_point. Preserve both source
identities, geometries, and all provenance other than the two
new declared property origins. Check field and potential with
separate ideal-source formulas at probes [0.4,0.6,0.3] m,
[2.8,0.25,0.4] m and [-1.1,0.9,0.75] m.
Do not request motion in a shell scene or treat a field-defined
point as a material collision object.

## 7. Required adversarial regression matrix

Acceptance requires explicit, retained tests for at least:

1. One valid member followed by a malformed or physically invalid later
   member: reject with **zero accepted descendant revisions** and byte-identical
   parent, older siblings, previous runs and source/import records.
2. 0, 1, 5 members; unknown keys/operations/categories; non-integer V3;
   boolean, nonfinite, wrong-shaped or unknown properties; zero/negative
   mass/radius; wrong physical domain; invalid source geometry.
3. Duplicate target_id within a transaction (including two properties
   of one entity), wrong role, mismatched parent expected scalar/canonical
   whole-object values, no-op property, old/reused ID across siblings or
   removed ancestors, stale reference and duplicate proposal/revision ID.
4. Remove-only last source fails, remove-last-source-plus-add-valid-source
   succeeds **without an intermediate accepted empty-source revision**,
   removal of last particle succeeds for static analysis.
5. Surviving receipt depends on removed entity: reject; a surviving
   computed receipt depends on changed property: stale transitively;
   source-set change invalidates all surviving computed receipts;
   particle-only addition does not invalidate unrelated receipts.
6. A removed-body observation or stale entity_order presentation refuses
   explicitly, while a newly authored compatible named investigation
   executes; source/particle reindex maps are checked against exact IDs.
7. A syntactically valid new particle launched at a singularity (or under
   shell/plane motion) is **not** called a trajectory pass. Numerical
   failure/rejection must not undo its separately accepted physical
   construction or overwrite a previous good run.
8. Interrupted publish, existing lock, incomplete ancestry, concurrent
   local writers, swapped/tampered hashes, output aliasing and no
   mutating a saved sealed run. The local lock is not called crash-
   recovery or distributed coordination.
9. Unmodified v1 single-property, v2 source and v2 particle operations:
   replay prior rejections and successful behavior; V3 does not broaden
   the native scene schema, solver, energy policy or viewer.

Use fixed existing tolerances and report independently evaluated
physical quantities and observed numerical discrepancies, with
source-level checksum provenance. Existing tests may be extended, but
never weakened or silently replaced. Linux/Windows duplication of
the same test definitions does not count as new independent cases.

## 8. Release and authorization gates

**This document alone is a design artifact, not a production feature.**

1. Obtain separate owner approval **to implement**, then create an
   isolated source feature branch from the approved pinned main/parent.
2. Implement V3 once, with targeted tests and the frozen E1/G1/T1 native
   transfers; preserve first failures and all negative outcomes.
3. Run full current Linux and Windows clean-install/historical/real-PyVista
   workflows and the separate real-PyVista workflow on the **exact candidate
   tree**, check raw run/artifact identities and separately expressed
   references. Record any pre-merge CI merge-preview SHA/tree distinction.
4. Only after author qualification, publish the exact-PR central review
   packet under review_sandbox/projects/emfeeld/pr-<number>/.
   Separate Chat B authors its own R2 report in reviews/; Chat A may
   respond but must never invent Chat B's verdict. Targeted corrections
   require fresh source SHA, CI and proportionate re-review.
5. Merge only after **distinct owner approval** and resolved blocking
   defects, then fresh main-branch CI plus append-only final central report.

Teaching evaluation remains paused. No change to the user's Conda
installation, classroom stores, saved investigations or license is
authorized by the design freeze.
