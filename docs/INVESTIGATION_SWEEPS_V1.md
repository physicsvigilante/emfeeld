# Investigation Composability V1 — bounded one-property sweeps

Design freeze: 2026-11-15; implementation target parent `25cfd7f4c42c9cb472b137b80ce67c68cfb9b88a` (PR #10 merged). This is a new, qualified orchestration layer over *existing* physical models, immutable proposal-version-1 property revisions, recorded native runs and named observations. It is not a new physics solver, symbolic engine, uncertainty certifier, visualization framework or classroom evaluation.

## Research question and implementation-cost hypothesis

Can an LLM vary one supported physical property across several separately justified scenarios, observe the same quantities at matched physical times, and keep all failures/evidence without copying the apparatus or writing new production code for each sweep? The first qualifying E1 run may require a shared sweep orchestrator; G1 and the preselected structurally different static T1 case must require authored data and checks, not another apparatus-specific code path.

## Public contract

Use `python -m emfeeld.sweeps run SPEC.json --store EXISTING_MODEL_STORE --using SEALED_NATIVE_RUN --output NEW_DIRECTORY`.

Example (the parent reference and old value are illustrative; use the actual sealed model reference):

```json
{
  "sweep_version": 1,
  "id": "strength-study",
  "parent": {"model_id": "model", "revision_id": "root", "sha256": "ACTUAL_64_HEX_HASH"},
  "target_id": "negative_line",
  "expected_role": "source",
  "category": "component_property",
  "property": "charge_per_m_C_m",
  "expected_value": -2e-11,
  "values": [-3e-11, -1e-11],
  "scenario_intent": "teacher_hypothesis",
  "provenance": {
    "origin": "illustrative_choice",
    "reason": "Study the effect of a prescribed source strength",
    "evidence": "Explicit hypothetical teaching choices, not source givens"
  }
}
```

All keys above are required; unknown keys are rejected. The hash placeholder is not executable. The parent is an exact immutable model reference, not implicit `latest`. The target is an existing stable physical ID; its role/property/category and expected old value must match the pinned parent. Values are **explicit literal JSON values**, not strings, a generated `linspace`, a formula, or an answer. One complete existing editable property is varied; up to **eight** distinct non-baseline members are permitted, with **at least one** changed member. No member may equal the parent property value, and there is no simultaneous variation of multiple properties. Scalar and full-vector changes use the existing proposal-version-1 operation, and all existing physical validity rules apply.

The `--using` source must be a *complete, sealed native run of the exact parent revision*, in the same model lineage. Its bytes supply the same investigation, analysis and presentation settings for every member, never an inherited numerical pass or a solver cache. The baseline is recomputed as a fresh run. All variants are immutable siblings of that exact parent, never a chain. They use distinct deterministic IDs based on the sweep ID; attempts never overwrite a previous proposal, revision, run or sweep. No automatic numerical-tolerance, source, launch, observer, camera or time-horizon adjustment is permitted. The output directory must be new and outside the store and source run.

Each member uses existing ModelStore.revise and model_runs.execute, and compatible successful results use existing compare_runs with matched observation IDs and explicit physical sample times. No interpolation or comparison of separately located events as simultaneous states. A point for which the revision is rejected or the calculation is partial is recorded as a **failed or unavailable member**, never silently omitted, zero-filled or plotted as a measured result. All requested observations must be fulfilled for a `complete` member. The complete result includes canonical inputs, exact references, per-member decisions, run artifacts, comparisons, hashes and a readable report. An interrupted attempt remains without a final completion marker.

Exit codes: `0` if baseline and every declared member completed and compared, `1` if a member was rejected/partial, `2` for malformed/bad-boundary input. Unexpected solver exceptions propagate as incomplete, preserving existing run/attempt records.

The model and all prior runs remain byte-identical. Newly accepted variants are separate immutable source-authorized hypotheses in the *existing* model store, so the store gains append-only entries. No auto-deletion on failure. A repeated sweep ID cannot consume the same members again.

## Preselected transfer tests

- **A1 — E1 (dynamic, source strength):** negative line plus uniform axial field, vary the existing line density; compare axial positions and time-matched transverse states against analytic axial invariance, separate line-field/potential expressions and independently integrated dynamics.
- **A2 — G1 (dynamic, physical launch vector):** two fixed gravitational sources and two test bodies, vary only Body 1's complete velocity vector; Body 2's saved trajectory must remain unchanged, with independently checked conserved quantities and solver comparisons.
- **A3 — T1 (static further case, not author-blind):** shell-plus-point-source model; vary only the point charge; compare field and potential at qualified world-coordinate probes using separate ideal-source expressions. Selected before production implementation; same author knows the case, so it is not an untouched hidden benchmark.

Negative and boundary checks: wrong role/parent; unknown property; mismatched prior settings; duplicate/nonfinite/no-op/too-many values; invalid mass/radius/vector; static and dynamic modes; rejected members and partial-run evidence; failure to reuse IDs; output alias and overwrite attempts; old template byte modification; no baseline overwrite; runtime provenance and correct comparison meaning.

Stop after bounded implementation and this transfer set; report all outcomes separately. Qualify against existing numerical and historical suites, Linux/Windows clean-install and real PyVista before any merge. Existing source laws, integrator, energy balance, renderer, numeric tolerances and historical evidence are unchanged.

## Assessment of transfer evidence

The initial E1/G1 implementations were tested before T1. T1 first passed against the first production freeze. A subsequent numeric-input hardening (reject nonfinite values before creating revisions) changed the shared implementation **after** T1 had been exposed. Accordingly, T1 replays against the final candidate are **regression evidence**, not an untouched held-out test of the final code. The hardening was motivated by an independent preflight audit, not a T1-specific failure; nevertheless, do not call T1 blind or untouched for the final revision. A future independent transfer claim requires a separately preselected and concealed fourth arrangement.
