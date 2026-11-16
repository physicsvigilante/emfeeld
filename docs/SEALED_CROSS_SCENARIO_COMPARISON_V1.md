# Sealed Cross-Scenario Measurement Comparison V1 — frozen design contract

**Design freeze:** 2026-11-16 (Asia/Kolkata). **Design-only candidate:** based on qualified main commit **1b7d5c652bb635723746b3c6ce77baee536b997e**, canonical Git tree **339224f69e5c671dea83678cdb00845887ce27b4** (merged Atomic Scenario Revision V1, PR #17). **Tracking:** [Issue #18](https://github.com/physicsvigilante/emfeeld/issues/18).

**Authorization boundary:** the owner approved this design-freeze step only. No comparison command is implemented by this document. Implementation, source merge, local Conda changes, new physics and teaching evaluation need separate decisions. **Risk R2**, because a cross-run arithmetic result changes the meaning, provenance, and fulfilment status of measured evidence despite leaving physical laws untouched. Apply [central protocol](https://github.com/physicsvigilante/review_sandbox/blob/main/PROTOCOL.md) and [risk policy](https://github.com/physicsvigilante/review_sandbox/blob/main/REVIEW-RISK-POLICY.md).

## 1. Purpose and implementation boundary

A teacher or LLM can explicitly match a small set of compatible observations from **two different, complete, sealed native model runs of separate immutable physical revisions of the same root model**, and receive signed **right minus left** differences. This supports investigations after V3 atomic insertion/removal, when original and final authored observation lists may differ. A run may contain additional observations irrelevant to the requested comparisons. No result is silently paired by list position, entity label, geometric proximity or matching numeric values.

This is **read-only, post-run arithmetic**, not a fresh solver invocation, source interpretation, physical revision, transfer of a numerical pass, interpolation of trajectories, automated observation authoring, inverse solver, gradient/sensitivity engine, multiscenario animation or new viewer. Existing model-format-1 snapshots, v1/v2/v3 proposals, strict source parser, source fields, integration, units, energy policy, named observation formats, sweeps, same-run derived observations and existing model_runs.compare_runs interfaces retain their meanings.

Preferred independent entry point, to be implemented only with later authorization:

~~~text
python -m emfeeld.scenario_comparisons SPEC.json --left SEALED_NATIVE_RUN --right SEALED_NATIVE_RUN --output NEW_DIRECTORY
python -m emfeeld.scenario_comparisons inspect NEW_DIRECTORY --left SEALED_NATIVE_RUN --right SEALED_NATIVE_RUN
~~~

A separate artifact is essential: **do not broaden model_runs.compare_runs**, whose historical strict same-investigation behavior is used by sweeps. No new dependencies, second model store or physical law.

## 2. Exact request envelope

One UTF-8 JSON document, parsed through existing duplicate-key/nonfinite rejection, with **exactly** these keys:

| Key | Meaning |
|---|---|
| comparison_version | JSON integer 1, not boolean or float 1.0 |
| id | existing safe identifier grammar |
| left_run_sha256 | exact 64-char lowercase hexadecimal SHA256 of LEFT/run.json raw bytes |
| right_run_sha256 | exact 64-char lowercase hexadecimal SHA256 of RIGHT/run.json raw bytes |
| pairs | ordered list of 1–16 explicitly named comparison requests |

Every pair has **id**, **type**, **left_observation_id** and **right_observation_id**. Each pair ID must be unique; both observation IDs must use the existing safe name grammar. Types are exactly:

- **field_vector**: two existing field observations, vector output in N/C for electric or m/s^2 for gravity.
- **field_magnitude**: two existing field observations at the same world point; output signed difference of the two **nonnegative magnitudes**, with the field's own units.
- **potential_difference**: two existing potential_difference observations at the same ordered (from_m, to_m) world-coordinate endpoints; scalar V for electric, J/kg for gravity.
- **particle_position**: two existing trajectory_sample observations of position for the **same stable particle_id**; vector metres.
- **particle_velocity**: two existing trajectory_sample observations of velocity for the **same stable particle_id**; vector metres/second.

For **particle_position** or **particle_velocity**, add one required **particle_id** to the pair; other types forbid particle_id. No other pair keys are allowed. The one physical ID is asserted for *both* sides; it cannot name a distinct paired body. Pair IDs may differ from native observation IDs. It is legal to reference the same native field observation in two distinct pairs, one vector and one magnitude, because pair IDs and selected operations are explicit.

Illustrative (NOT executable until actual run digests have been supplied; all case values are teacher-authored, not given source facts):

~~~json
{
  "comparison_version": 1,
  "id": "E1-source-replacement-comparison",
  "left_run_sha256": "ACTUAL_LEFT_RUN_JSON_SHA256",
  "right_run_sha256": "ACTUAL_RIGHT_RUN_JSON_SHA256",
  "pairs": [
    {
      "id": "E-at-probe",
      "type": "field_vector",
      "left_observation_id": "E_baseline",
      "right_observation_id": "E_replacement"
    },
    {
      "id": "delta-potential-step",
      "type": "potential_difference",
      "left_observation_id": "dV_baseline",
      "right_observation_id": "dV_replacement"
    },
    {
      "id": "test-charge-position",
      "type": "particle_position",
      "particle_id": "test_charge",
      "left_observation_id": "body_position_baseline",
      "right_observation_id": "body_position_replacement"
    }
  ]
}
~~~

The placeholders deliberately fail preflight until replaced with authentic pinned run.json digests. A spec does **not** invent missing observations, issue a fresh numerical investigation, or coerce a position sample into a field measurement.

## 3. Run preflight: fail before creating an output

Before any output publication, use **existing model_runs.inspect_run** for both source runs, and perform the additional bounded consistency checks below; do not introduce a shadow physics solver. Both sources must be complete, integrity-inventoried, saved native model runs, not merely files shaped like run.json.

- Both spec digests must match the corresponding exact run.json raw-byte SHA256. Reject swapped sides, stale pins, invalid/missing/incomplete/rejected/partial native runs, absent native packet/results, incomplete run inventories, tampered or missing nested native inventories and corrupted input/identity/mapping bindings. No cross-run summary labelled complete when its native report is partial.
- Require **distinct physical revision references**, but **identical exact root_reference**, model_id, physical domain/kind, supported physical-time origin and declared coordinate frame (existing V1 runs use the same world-coordinate SI frame and time origin 0 s; no transformed frame operation). Siblings and ancestor/descendant revisions of the same lineage are both eligible. Foreign stores/models or mixed-domain comparisons fail. No implicit "latest" resolution.
- For V1, require identical **implementation_sha256** mapping and identical native reported **Python, NumPy, SciPy and physical-constant metadata** across the two runs. This is deliberately conservative: comparing across different checkouts or software stacks, including Windows/Linux raw line-ending hashes, is **not** a qualified cross-version comparison. Both operands' actual numerical check policy and time horizon are separately retained; do not claim equal accuracy simply because the installed code matches.
- Verify nonempty, unique native observation IDs and one-to-one request/result correspondence; native report must have status "ok", each requested result must have status "ok" and no authored check passed=False. Verify stored summary's complete/execution_complete, numerical_checks_passed and unfulfilled_requests meaning against native outcomes, not only the existence of hashes. Mismatched supposedly sealed success evidence is a **hard invalid_native_run** preflight failure, not a merely unavailable pair.
- Require the source run's recorded physical revision, named investigation and actual native packet/mapping to remain coherently bound under existing inspect_run, with additional comparison-specific checks of the observed type, parameters, units, selector and physical particle index. Keep the original bytes unchanged.
- Reject already existing output, symlink aliases, output inside either protected run, or output under any store or source input path when it would overwrite/alter original evidence. Input run paths are read-only throughout. No automatic repair/rebinding or regenerated input run.

The qualification shall make an explicit decision about direct nested native-inventory checks in otherwise legitimate static-only runs: a static run on a model **with particles** may contain native/packet.json and native/result.json without a trajectory archive. Only require nested trajectory capture files in modes that actually captured trajectories; don't force static probes to integrate.

## 4. Per-pair compatibility and refusal (NO implicit matching)

Once the two complete source runs pass global preflight, process pair requests in their authored order. **Missing observation ID or a physically incompatible requested pairing is item-level unavailable**, not a false global success. Bad top-level grammar, duplicate pair IDs, invalid source-run integrity, incompatible root/implementation/domain, or saved metadata inconsistent with the native packet are hard preflight errors.

**All eligible operands** must come from the exact indexed native report and corresponding authored native packet request. For every pair independently require:

1. Actual results' status "ok"; expectation/check passed is not false (and the complete-run global invariant holds); type and kind appropriate; exact expected SI unit; numeric values are finite float64-compatible JSON numbers, not boolean, string, NaN/Infinity or overflowing integers; shape exactly vector length 3 or scalar as declared.
2. **Field vector/magnitude**: both native packet requests are type field, both **authored position_m** values are exactly the same SI world-coordinate triple (component numeric equivalence permits JSON int versus equivalent float, but no spatial tolerance, rounding, re-centering or source-following). Verify report coordinates, types and units agree with those captured requests. For magnitude, recompute robust norm from the saved three-vector, reject negative/nonfinite or inconsistent saved magnitude using the existing derived-observations 1e-12 relative **zero absolute floor** comparison; do not elevate either magnitude to a separately certified field measurement.
3. **Potential difference**: both packet requests are type potential_difference; their from_m and to_m triples respectively match *in the original order*, not as an unordered pair; confirm the report's convention is "potential(to_m) - potential(from_m)". Different endpoint ordering is **unavailable/endpoints_mismatch**, not a silent sign flip. Compare potential **differences**, never absolute potentials or source reference offsets.
4. **Shared particle position/velocity**: both original named investigation requests identify exactly **the same stable particle_id specified in the pair**. Verify each saved mapping's particle_id-to-particle_index agrees with the corresponding lowered native packet and the observation's particle_index. A source/particle role mix, missing ID on either revision, different particle ID or mismatched result-to-native index is never silently remapped. Compare only the same quantity in both reports.
5. A motion operand requires actual finite **time_s** and nonnegative integer **sample_index**, consistent with its own source's recorded trajectory and native sample-time arrays. The observed position/velocity components must agree with the corresponding actual archived full-horizon NPZ sample for that particle/quantity; a re-sealed but internally contradictory report must not count. **Actual saved time_s must match exactly** across sides. The indices may **differ** because the independently saved time grids may differ, provided both actual physical times are equal and each is a recorded sample. A nominally matching index but different saved time is **unavailable/different_saved_time**. Nearest-time selectors compare their *actual saved times*, not requested nominal times. No tolerance, interpolation or event-time equivalence is inferred.
6. No reported field, potential, kinematic or energy result can be used as evidence of an unrequested body or an unsimulated temporal transition. An added body absent from an earlier revision cannot be matched to an old array index, even if another body occupied it then.

**Per-pair unavailable codes** (freeze exact spelling for V1): unknown_operand, operand_unavailable, incompatible_observation_type, incompatible_units, different_world_point, endpoints_mismatch, particle_identity_mismatch, different_saved_time, invalid_saved_sample, numeric_range. Retain a human-readable reason and explicit null result. A request pointing to a genuinely absent particle-side observation returns unknown_operand or particle_identity_mismatch as appropriate, not a fabricated zero. Do not use a pair-level unavailable outcome to conceal globally corrupted run integrity or a falsely complete source report.

Successful signed difference = **right minus left**, componentwise for vectors and scalar for magnitudes/potential differences; record original operands. If any arithmetic overflows float64 or produces nonfinite output, return item-level **unavailable/numeric_range**. Do not clip, replace infinities with zeros or silently enlarge tolerances. Arithmetic value equals zero only when representable signed difference really rounds to zero under the declared float64 policy; retain the original operands so reviewers can distinguish rounding from an asserted exact physical equality. For complete output, **all pairs must be status ok**. Mixed success/unavailability yields **partial**.

## 5. Sealed output and deterministic read-only inspection

Create **one fresh output directory** after passing all source and schema preflight checks. No partial file is called complete. Retain exact request.json authored bytes, started.json with pending status, result.json with exact comparisons and all original operand provenance, and integrity.json covering all other files except itself. Retain source-run pins, exact source revision and root identities, run IDs, native packet SHA256s, implementation/constant identities, request/selected-observation IDs, source sample time and indices where relevant, explicit units, value shapes, method and **error_bound:null**. Do not claim certified uncertainty bounds or native solver equivalence.

Proposed comparison result schema has exactly:
**comparison_version, id, status, request_sha256, left, right, comparisons, meaning, qualification**.
The left/right metadata records source_run_sha256, run_id, reference, root_reference, native_packet_sha256, and recorded runtime/physical-constant identity. Each comparison result contains id/type, status, code (null on success), value (null if unavailable), unit (null if unavailable), the two original source observation IDs, original operands and contextual coordinates/particle IDs/saved actual times, error_bound:null, and the signed right_minus_left method/meaning. The inspector shall use the same pure derivation logic (without integrating or evaluating source fields) and **recompute every pair's expected status, code, value and aggregate status from the two exact source runs**; a re-sealed output with inconsistent result values or forged "complete" must fail inspection. A hashing inventory alone is not enough.

Before result sealing, correctly classify a controlled process interruption: retain a started/pending directory and any written evidence, never fabricate success or overwrite on retry. Separate exit statuses for complete/partial/malformed or bad run are proposed: **0/1/2** (unexpected runtime exceptions preserve incomplete output; no automatic fallback solver). The exact CLI and error formatting may be implemented under the later frozen source PR without changing this physical meaning.

Existing native stores, earlier proposal decisions, model roots, source imports, sealed runs, samples and previews stay byte-identical.

## 6. Frozen project-informed transfers (not hidden tests)

The cases below are knowingly chosen by this author before implementation; they **are not blind**. They should be instantiated through actual existing imports and V3 native model revisions, creating two distinct **complete** sealed runs with new observation packet IDs and explicit compatible measurement requests.

**E1 — electric dynamic source replacement.** Use examples/marker_regression/E1.json: negative line at origin plus uniform +0.15 N/C z field, existing charged test_charge; V3 atomically remove the negative line and add shifted_positive_line (charge density +1e-11 C/m, center [0.4,-0.3,0], direction z, reference_radius_m=1). Compare world-coordinate **field vector and magnitude** at the same non-singular probe, the same ordered two-point electric potential difference, and test_charge saved **position and velocity** at exactly matching physical times. Independently write ideal line/uniform E, V and axial acceleration (z(t) = z0 + vz0*t + 0.5*(q/m)*Ez*t^2) and fixed-step RK4; the final transverse trajectory changes. The comparison is not motion of the prescribed line source during a run.

**G1 — gravitational dynamic mass change plus third body.** Use examples/marker_regression/G1.json; V3 changes source_A sphere mass from 2e9 to 2.5e9 kg and adds body_3 with explicit independent initial state and gravity-neutral charge convention. Compare common world-coordinate acceleration/field and the same named body_1/body_2 saved position and velocity at identical physical times. Include one deliberately requested body_3 baseline pair and report **unavailable** without matching old body_2 by reindexed array position. Independently apply sphere interior/exterior plus point-source expressions and separate numerical trajectory reference. The surviving bodies' *initial conditions* are preserved, but their trajectories need not be identical after changing source mass.

**T1 — static electric shell and point.** Use examples/structural_revisions/T1.json; atomically change shell charge +2e-9 to +3e-9 C and central point charge -5e-10 to -8e-10 C, retaining static source geometry. Compare field vectors/magnitudes at identical interior/exterior non-singular coordinates and an identical ordered pair of potential-difference endpoints (the potential reference cancels). Independently calculate shell zero internal field/constant internal potential plus central point contribution; no shell/plane particle dynamics.

## 7. Required adversarial and compatibility evidence

The later implementation must add cumulative warning-as-error focused tests and retain all failures, including:

- Top-level duplicate JSON keys, wrong version/extra keys, invalid run digests, duplicate pair IDs, unknown type, 0/17 pairs, malformed particle keys, bad units/numeric shapes, booleans and nonfinite/overflow values, arithmetic overflow, missing observation IDs.
- Both sides using the **same observation ID** with genuinely different authored geometry/semantic meaning must be refused; different IDs with explicitly identical physical meaning must be admitted. Swapped left/right must reverse the signed numeric difference and require corresponding swapped run pins; no implicit source-to-source pairing.
- Matching world field points versus shifted/rounded coordinates; reversed potential-difference endpoints versus matched order; do not compare absolute potential or invoke arbitrary potential-offset cancellation without matching ordered endpoints.
- Saved time mismatch with same index; equal actual time with **different indices** on independently sampled grids; nearest-time selection; malformed/nonfinite time, negative/boolean index, wrong quantity or particle index, a reindexed retained particle ID, added/removed ID, and a forged re-sealed saved sample that disagrees with NPZ.
- Partial/rejected or unsealed native run; tampered source run.json, revision, mapping, native packet/results, original/nested inventory, implementation/version/constants, and a duplicate/missing native observation in a report; forged source "complete" and output "complete"; re-sealed altered comparison result; missing/altered inventory; output path or symlink alias into protected source run.
- Include runs from **different revisions of the same root** and reject unrelated roots, different physics kinds and mismatched implementation/constant records. No independent energy diagnostics reinterpretation or arbitrary certified error bound.
- **No mutation** of original input JSON, model stores, proposal decisions, source runs, earlier error reports and old native previews. Existing model_runs.compare_runs, investigation sweeps, same-run derived_observations, V3 structural edits, physics/event thresholds and historical fingerprints must remain unchanged.
- Preselected electric/gravitational/static geometry references must use separate analytic/numeric expressions and real saved native outputs, not fixture values fitted to solver traces. Chat B should independently challenge a different unfamiliar pair of scenarios and failure conditions.

## 8. Release and review gates

1. **Separate owner approval to implement** after this design-only PR. Work from the then-approved pinned main in a new feature branch; do not merge this draft design PR merely to activate source behavior.
2. Implement a small module reusing native sealed run inspection and the existing literal data/ID checks. Preserve historical source files, physical laws, tests and numerical thresholds; do not create a second model store, dynamic solver or UI framework.
3. Run exact-head full Linux/Windows clean-install headless/historical/real-PyVista workflows plus separate real-PyVista qualification and native E1/G1/T1 read-only comparison outputs. Hash and audit archived artifacts and negative attempts, with source SHA/tree pinned.
4. Publish central review packet under review_sandbox/projects/emfeeld/pr-<source PR number>/ after candidate author qualification; Chat B independently writes its own R2 report. Preserve first attempts, attribute findings and rerun CI plus proportionate re-review after source changes.
5. **Separate explicit owner merge approval** before production merge, followed by fresh main-branch CI, original ZIP/hash/run audit and a new append-only central MERGE-REPORT. Do not mistake successful postprocessing for classroom learning evidence.

**Limits remain:** no mixed-domain physics, source backreaction, particle interactions, conductor responses, shell/plane trajectory crossings, symbolic initial-condition solving, desktop Windows manual interaction or externally authenticated source inputs. This design does not install or update the user's Conda environment and does not resume teaching evaluation.
