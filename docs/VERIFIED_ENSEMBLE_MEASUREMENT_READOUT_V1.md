# Verified Ensemble Measurement Readout V1 — bounded presentation contract

**Risk: R1 evidence presentation (escalate to R2 on any changed numeric or evidence meaning).** Base is the fully independently reviewed and post-merge-qualified Verified Ensemble View Selector V1, GitHub main `9e5924efa60dea56606e0b8eef591f94711b666d`, Git tree `ce20aa49d978c94150edbbf017d8fae1e2f6f896`. This readout is a new feature-branch candidate, **not** a merged capability or release approval. Independent-context focused review is mandatory because a misleading measurement label can impair scientific evidence interpretation.

## Need and non-goals

Existing Bounded Scenario Ensemble V1 has sealed native E1/G1/T1 runs and explicit signed cross-scenario comparisons. `scenario_ensembles inspect` verifies each native record and reports completeness, but a teacher/LLM seeking actual measured differences must traverse private `member-XX/comparison/result.json` paths. A stable, verified projection can provide exact typed measurements without new physics, changing V3 identities, or creating duplicate source-of-truth outputs.

**Not in scope:** new formula, solver, tolerance, unit conversion, rounding, derived value, same-time interpolation, side-by-side animation, material conductor, model-store writes, screenshot generation, mutable cache, textbook answer, automatic problem interpretation, source repair or teaching acceptance. Comparison is **right (member) minus left (fresh common baseline)**; the different hypothetical scenarios do not represent a physical time transition. A valid accepted V3 construction is not proof of a complete numerical outcome.

## CLI and input

```text
python -m emfeeld.scenario_ensembles measurements ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN
python -m emfeeld.scenario_ensembles measurements ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --member EXACT_DECLARED_MEMBER_ID
```

The optional filter is an **exact declared member ID**. `--member baseline` names an actual member; the baseline itself is the left operand, not a member comparison. There is no `--baseline`, `--sample-index` or `--output` for this read-only command. All existing `run`, `inspect` and `view` CLI flags and behavior remain unchanged.

Require full `inspect_ensemble` successfully on the entire original source, even when only one member is requested. This verifies the sealed outer inventory, original complete/partial member decisions, each original V3 proposal raw SHA256, stored immutable root and child references, original parent template, fresh baseline and every legitimate completed cross-scenario comparison. Then for a member with recorded comparison, call the **existing** `scenario_comparisons.inspect` again to obtain authoritative typed values. Fail on any changed result or request bytes versus saved comparison inventory before returning a readout. Do not rescue corrupted evidence by selecting a different member or silently using a stale result.

## Output — strict read-only projection

One JSON document printed to stdout, not saved in or adjacent to the sealed study. Required high-level fields: `readout_version=1`, `id`, global `status`, `parent`, `source_run_sha256`, `baseline` saved status/reference, `selection` (`all_members` or `member:EXACT_ID`), ordered `members`, `meaning`, `qualification`. **Global status always describes the original full ensemble, even when a selected member is complete.** The CLI returns exit `0` on an entirely complete ensemble, `1` on an honestly partial ensemble and `2` on invalid request or detected integrity failure (consistent with current `inspect` semantics).

Each member retains original declaration order/index, exact member ID, accepted/rejected decision, original exact model reference, source native run status, comparison status, member status/reason, `measurements` and `evidence`. For a rejected or numerically incomplete native member, `measurements=[]` and `evidence=null`, preserving the member's missing/partial reason: an empty list is **not** a list of numerical zeros and never a success claim.

For members with a sealed comparison, preserve each original measurement's original `id`, `type`, `status`, `unit`, `value`, `code`, `reason`, `error_bound`, `context`, `left_observation_id`, `right_observation_id`, `particle_id` **without changing the numbers, time selector, coordinate convention or units**. A legitimately unavailable operand retains `value=null`, `status=unavailable`, original `code=unknown_operand` and its original reason, never `0` and never a fabricated physical counterpart. The verbose source-native `operands` are not duplicated in this compact projection; evidence fields identify where to read them if needed.

Each successfully compared member includes exact SHA256 of the original immutable `request.json`, `result.json`, `integrity.json`, and exact original left and right run.json input SHA256 pins. These are unkeyed integrity bindings, **not adversarial cryptographic authenticity** or a new scientific reference calculation.

## Safeguards and review gates

- No run output, model store, sealed original native input, comparison output, screenshot or old studies may be modified by the readout or by a refusal. When filtering, an unrelated sibling's tampered original evidence still fails preflight.
- Unknown/empty/non-string member selection, prohibited CLI flags, a tampered/re-signed ensemble, changed original source proposal bytes, altered template/run input or result, and a comparison changed between inspection and projection all fail closed. Local reads cannot make guarantees against a malicious concurrent writer or distributed crash-safe ACID.
- Positive controls: two to four valid siblings, member literally named `baseline`, full E1/T1, G1 honest partial, rejected V3 member and accepted-but-native-partial member, signed field/potential/trajectory native values with exact original units and JSON precision, no new computed values.
- Run focused tests and complete current-source headless/historical Linux/Windows and separate real-PyVista CI; exercise native archived E1/G1 scenarios with this CLI in both OS jobs, preserve exact-head Git tree and original published ZIP hashes, then require focused Chat B review of exact immutable source. This is **R1** only if numeric and saved evidence semantics are strictly unchanged; escalate to R2 for any substantive semantic changes or new computation.
- After independent review and owner-directed authorized merge, run fresh `main` CI and original artifact evidence audit. Automated offscreen PyVista does not establish manual Windows pointer, human physicist review or teacher learning outcomes.
