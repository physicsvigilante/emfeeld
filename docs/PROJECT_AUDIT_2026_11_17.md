# Project-wide audit and forward plan — 17 November 2026

## Disposition and evidence boundary

This is a **new author-tested R2 correction candidate**, not an independently approved release. Its base is released main `066c94e4953c3ef29302c0bb6d0ee2f6cb8b8ca0`, Git tree `33b58fb55b387ec2b7c1bdd61bf1af7764db97cd`. The base was reconstructed from the original main-push viewer archive, not from a retyped source summary. The untouched 367-file source tree matched exactly and its headless suite passed **1,585 tests**.

The audit covered the physics/energy/integral and event interfaces, scene/packet admission, model revisions, run capture and presentation, sweeps/comparisons/ensembles, public output writers, replay/question-first tools, tests, live guides and CI configuration. Original worksheet text was inspected for scope, not scored as a solved corpus. This is broad practical review with executed adversarial tests, **not a proof that all possible errors are absent**. No educational or independent scientific certification is inferred from the test count.

## Reproduced defects and corrections

| Finding | Before correction | Correction and regression |
|---|---|---|
| Saved evidence could be polluted by a new output | A new native run inside a sealed run succeeded, then the original run failed its recursive integrity check. Other writers had no shared cross-evidence guard. | Add `output_safety.protect_saved_evidence` before public writes and store mutation. Reject destinations in recognizable sealed roots, model stores, question locks, studies, replays and completed workflow attempts; resolve ordinary symlink aliases. Preserve intentional children of unsealed in-progress workflows. |
| Oversized numeric settings crashed | Large JSON integers in analysis checks, bounds or replay speed reached NumPy/type conversion and raised unexpected errors rather than a retained rejection. | Use the existing finite float64 number validator before conversion. Validated rejected analyses remain inspectable. |
| Degenerate camera admitted | Camera view-up parallel or antiparallel to the line of sight passed validation. | Validate finite nonzero geometry and a nonzero cross product before rendering; no physical values are changed. |
| Unused sphere-potential branch overflowed | An exterior point with finite potential still evaluated the interior radius expression eagerly and overflowed. | Evaluate only the applicable original analytic branch; test electric, gravity, zero-strength and mixed inside/outside samples. |
| Zero-strength tiny spheres divided by underflowed zero | Solid and thin-shell sphere fields could compute zero divided by an underflowed radius cube. | Return the documented exact zero field before the unnecessary division when source strength is zero. |
| Captured motion bypassed an invalid-time-grid guard | Full-scene capture could send an already rejected unrepresentable saved grid to integration. | Cache the typed `unresolvable_time_grid` failure with `integration_attempted=false`, including capture; no fabricated trajectory. |
| Nonobject proposal inputs crashed | Lists, null, strings, booleans and numbers reached `.get` rather than normal admission. | Require a JSON object before reserving proposal files or mutating the store. |
| Malformed entity ordering crashed | Lists/dictionaries used as entity IDs reached set construction and raised an unhashable-type exception. | Validate every ordering member is a string before membership/uniqueness checks. |
| Live guidance had drifted from released source | README/AGENTS still described shipped features as unmerged candidates and could misapply the historical PR #1 chat-review exception. | Replace live status with the implemented capability map and current review gates; keep dated historical reports untouched. |

The output preflight is a local namespace safeguard, **not a concurrent-writer lock, authenticated seal, distributed transaction or defense against a malicious writer able to rewrite everything**. Existing caller-specific no-overwrite and input-alias checks remain in place. Files outside protected evidence retain their established atomic replacement policy.

No new physical law, field softening, solver algorithm or numerical tolerance has been introduced. However, **engine implementation bytes do change**, including `fields.py`; this is not a documentation-only patch. The new shared helper increases the engine module inventory from 29 to 30.

## Executed qualification and preserved first failures

Local environment: Linux, CPython **3.13.5**, NumPy **2.3.5**, SciPy **1.17.0**, pytest **9.0.2**. Warnings are treated as errors.

- Original untouched full headless suite: **1,585 passed**.
- Corrected cumulative suite: **1,629 passed**, comprising the prior 1,585 and **44 new audit regression executions**. The new tests are included in that total, not an additional independent benchmark.
- New audit tests alone: **44 passed** (37 safety/admission executions and seven numerical executions).
- Historical behavioral pilot: **18 passed; one obsolete all-file freeze guard deselected**. Historical all-file identity assertions belong on their original snapshots and were not rewritten to pass current code.
- Exact-input replay manifests: Physics Demonstration V1 **one case / 17 native observations / 64 reference checks**; published V6 **10 cases**; discovery examples **two cases**, all passed on the corrected source. Python compilation passed.
- Real local PyVista/viewer execution: **not performed**. The isolated dependency install attempt failed because package/DNS retrieval was unavailable. Existing VTK does not substitute for a tested PyVista installation. New Windows and real-viewer qualification must come from fresh exact-source hosted CI; the old baseline's successful workflows do not qualify these changes.

Original failure logs are retained: 15 initial safety/admission cases failed against the base; five initial numerical cases failed; the two zero-strength sphere failures were separately reproduced against the original field module; seven later malformed-input cases failed while one control already passed. An intermediate correction initially changed an expected `FileExistsError` into `ValueError`; the fresh-directory option restored the existing behavior, and the earlier failing correction log remains preserved. A publication-only argparse keyword ordering difference was detected by Git-blob comparison and retested on the exact published bytes. No failed first attempt is retroactively called a pass.

The completed local suites are **author checks**, not separate-context review. Independent R2, fresh Linux/Windows/full-viewer CI, original archive audits, guarded integration and actual-main post-merge qualification remain release gates until explicitly completed in the central review records.

## Compatibility with saved studies

Recorded studies can pin the exact field implementation. After these corrections, an old study may correctly refuse presentation with “field implementation differs from the captured run.” Keep the original evidence and its pinned source environment, or replay the original exact inputs into a **new** output under the corrected source. Do not rewrite historical implementation hashes or relax checks to force compatibility. The audit has not modified any user's local Conda installation, saved models or previous release artifacts.

## Capabilities now implemented

The core is a composable **electrostatic or Newtonian-gravity** teaching/exploration engine, not general electrodynamics or a natural-language solver.

**Physical sources and probes.** Point sources, uniform filled spheres, thin shells, infinite lines, infinite planes and constant uniform fields can be translated, oriented and superposed within one physical kind. Python superpositions can be nested; the strict JSON scene uses a flat list of source records. Static field vectors/magnitudes, potentials, explicit test-body forces and ordered potential differences are available with SI units, potential references and explicit singularity/domain errors. Python midpoint line-integral contributions and spherical flux quadrature exist; they are not general packet observation requests or interactive teaching tools yet.

**Motion and events.** The engine integrates independent nonrelativistic test particles in fixed prescribed fields with DOP853, records saved positions/velocities/speeds/kinetic/potential/total energy, and exposes energy-balance diagnostics. It supports explicit sample indices, exact stored times or explicitly bounded nearest-time selection. Bounded plane/radial crossings and local radial turning requests, including a separately defined rest-launch policy, retain actual event state, failures and base/refined agreement. A local turning point is not a global optimum; `no_event` is not proof of no physical crossing or a fulfilled event request.

**Reusable physical systems.** Immutable named revisions preserve exact parents, stable source/particle IDs, givens/assumptions/derived-input provenance and rejected attempts. V1 property changes, V2 source/particle insertion/removal and V3 atomic two-to-four disjoint edits are implemented. Investigations, numerical settings and presentation are separate from physical revisions. The convenience `model apply` command is currently V1/V2-only; native revision and ensemble interfaces support V3. This interface difference is now documented rather than hidden.

**Investigations and evidence.** Authored bounded sweeps, scalar ratios and same-time particle separations, signed right-minus-left scenario comparisons and sibling ensembles with a fresh baseline are implemented. Sealed original measurements can be projected into readouts and escaped Markdown without another solve. Missing operands retain typed unavailable/null outcomes; filtering does not convert global partial to complete. Hash inventories and exact input/source receipts support reproducibility and drift detection, not malicious-history authentication.

**Visualization and question trials.** The optional viewer presents source geometry, a potential slice, equal-length field-direction arrows and recorded trajectories with pause/play, restart, sample stepping, seeking and screenshots. Markers and finite depictions of infinite geometry are schematic; display grids do not drive forces. Source-first question freeze/assessment verifies declared native IDs, quantity, units, context and actual saved times. It does not certify the original question was faithfully interpreted. Developer-authored gravity and public non-blind NASA exercises remain distinct from a genuine independent teacher/withheld-judge trial.

For authoritative detail see [PHYSICS](PHYSICS.md), [OBSERVATIONS](OBSERVATIONS.md), [AUTHORING_WORKFLOW](AUTHORING_WORKFLOW.md), [TEACHING_STUDIES](TEACHING_STUDIES.md), [MODEL_REVISIONS_IMPLEMENTATION](MODEL_REVISIONS_IMPLEMENTATION.md), [ATOMIC_SCENARIO_REVISIONS_V1](ATOMIC_SCENARIO_REVISIONS_V1.md), [BOUNDED_SCENARIO_ENSEMBLE_V1](BOUNDED_SCENARIO_ENSEMBLE_V1.md) and [QUESTION_FIRST_TRIAL_V1](QUESTION_FIRST_TRIAL_V1.md), plus the runtime capability catalogue and validator.

## Not implemented or not yet established

There is no full Maxwell/time-dependent self-consistent solver, magnetic Lorentz motion, relativistic/radiation treatment, particle-particle forces, source recoil, conductor polarization, material collision response or simultaneous electric-plus-gravity dynamics. Finite rods, rings, disks and general nonuniform distributions are not native source types. Shell/plane-source motion is deliberately refused. There is no native general inverse/symbolic solver, guaranteed global closest approach/minimum launch speed, or guarantee of detecting every event root.

The viewer does not yet provide traced field lines, 3D equipotential surfaces or an integral-teaching interface. Automated offscreen qualification is not manual Windows desktop usability or classroom usefulness. A public answer-key rehearsal is not blind validation. The 149-page original worksheet corpus has **not** been comprehensively graded as solved; no worksheet coverage percentage is supported by this audit.

## Recommended plan forward

### Priority 0 — release the reliability fixes, then enforce the gates

Complete independent R2 and fresh exact-source Linux/Windows/viewer qualification; inspect original artifacts and preserve negative cases before guarded integration. Add compatibility checks for the intended dependency matrix rather than assuming every declared Python/dependency combination is qualified. The live main branch was unprotected at audit time; owner-approved required checks/review rules should enforce the safeguards currently maintained by process. No branch-administration change was made. The owner also needs to choose a repository license; none was selected by this audit.

### Priority 1 — test real scientific and teaching use, not another format

Use a genuinely new independently provided question and a separately held reference/judge rubric, preserving original wording and first attempts. Keep interpretation fidelity, physical/numerical correctness, simulation coverage, educational usefulness and textbook-answer completeness separate. Include supported, ambiguous and unsupported requests, and accept honest refusal as evidence rather than silently simplifying physics. Add a real Windows interaction/teacher walkthrough: opening a model, changing a hypothesis, reading units/signs, playback and comparing outcomes.

### Priority 2 — make existing capabilities easier to use

Consolidate the question-to-model-to-investigation-to-view workflow rather than building another solver/store or duplicate evidence layer. Improve guidance on source versus derived inputs, units, explicit missing information and available measurements. Measure the effort required to complete a real teaching task. Decide deliberately whether V3 convenience application, unit conversion presentation and integral observations solve demonstrated user problems before expanding APIs.

### Priority 3 — extend physics only when the task set justifies it

Build a source-derived capability-gap matrix from actual questions. Candidate isolated extensions include mixed qE+mg dynamics, finite source geometries, integral observations/visualization and better event/collision policies, each with independent analytic limits and negative tests. Magnetic dynamics or conductor boundary solving would be separate substantial physical modules, not relabeling a prescribed sphere as a conductor. A broad rewrite is not warranted simply because these features are absent.

**Overall assessment:** the project has a substantial reusable analytic core and unusually explicit evidence/provenance machinery. Its immediate bottlenecks are robust edge-case handling, clear current documentation, human usability and independently demonstrated interpretation—not a lack of additional report formats. The next growth should be driven by real questions and visible teaching value.
