# Particle Structural Revisions V1 — developer verification ledger

This document records **same-author** development/qualification; it is not a Chat B review. The frozen prospective contract is [PARTICLE_STRUCTURAL_REVISIONS_V1.md](PARTICLE_STRUCTURAL_REVISIONS_V1.md). Source parent is `7e6bd8c72cac7708ab3c2355cc1a98db09762133` (merged PR #13). Source physics laws, integrators, trajectory event policy, native observations, viewer and numerical tolerances have not been modified. The only production changes are a bounded dispatch and one new structural particle adapter.

## First local test attempt — preserved, not retroactively graded green

The first `tests/test_particle_revisions.py` run recorded **35 passed / 2 failed**, in `/mnt/data/particle-v1_newtests_initial.log` (local developer log, not a GitHub CI artifact). Both test failures were mistakes in the authored test harness:

1. Test case supplying explicit `particle: null` accidentally used a helper function whose `None` argument substituted the fixture's default *valid* particle. The helper now uses a distinct sentinel, and null is correctly rejected by the production parser; no production behavioral change was necessary.
2. A malformed cross-operation proposal (`remove_source` with `expected_role: particle` and `expected_particle`) was correctly rejected, but the test demanded the `unsupported_change` code although the shared source-version-2 dispatcher detected a missing expected source payload and classified it `invalid_proposal`. The corrected test asserts the actual documented rejection category, preserving source-only API behavior and avoiding needless error-code rewrites.

The original failures are meaningful **author test design errors**, not demonstrated solver/physics defects. No historical test or numerical threshold was weakened. On the corrected test harness, the same suite plus existing structural/model revision regressions passed **159 tests** with warnings as errors.

## Transfer assessment and evidence boundaries

- E1: negative infinite electric line with constant axial field; add a second independently launched and differently charged/massed test body. Existing body's full-horizon trajectory is preserved. Two-body trajectories, axial acceleration and kinetic/potential energy are compared with separately authored expressions/fixed-step RK4.
- G1: remove Body 1 from the two-fixed-source gravity scenario. Body 2 reindexes from native `p1` to `p0` but retains its named identity and full-horizon trajectory. A prior investigation targeting removed Body 1 **explicitly rejects**. The new Body 2 named investigation and independent gravitational RK4 pass.
- T1: preselected **static electric shell + point** with no initial test particles. Add/remove an illustrative charged test body and reuse **static** field/potential probes; no shell/plane motion is claimed. Recorded field/probe results and sources stay identical throughout.

The shared adapter requires no arrangement-specific production branch. **7 complete native runs + 1 intentionally rejected analysis**, **4 accepted structural revisions** (E1 one, G1 one, T1 two), **6 full-horizon saved trajectories** across E1/G1 (606 states), and **34 separately checked static observations**. Baseline and all preexisting model-store bytes remain identical across revisions and runs; snapshots and source IDs are stable. Static T1 is evidence of structural data reuse, not a third newly qualified dynamic physical regime.

The reference checker `verification/check_particle_revision_runs.py` imports only NumPy, SciPy constants via a previously developed **separate** ideal-field/RK4 checker, not emfeeld field or solver code. Its reference equations were developed by the same author; they are neither an independent Chat B review nor a rigorous global error bound.

## Required release gate (pending separate qualification)

Run `python -m pytest -q -W error tests` and `python -m pytest -q -W error pilots/authorability_v1/test_pilot.py -k 'not test_all_available_parent_files_remain_frozen'` against the current source. Test current real PyVista on hosted Linux and Windows. Run:

```
python tools/qualify_particle_revisions.py --output output/particle-001
python verification/check_particle_revision_runs.py output/particle-001 --report output/particle-reference-001.json
```

The complete release workflow also captures E1/G1 saved particle frames and T1 explicitly static views. The expected generation errors, first negative controls and any CI failures must be retained without quietly rewriting them or claiming they passed. A high-risk **R2 separate Chat B review** must be requested through `physicsvigilante/review_sandbox` **after** developer CI success and after the source draft PR SHA and artifact digests are frozen. Neither author tests nor Chat B's verdict implies owner merge approval or classroom usefulness.

## Additional self-review and completed local qualification (same author)

After the first transfer checks, additional negative tests were added for unknown/unchecked provenance, cross-role identity reuse after a source was removed, stale-input lifetime, duplicate proposal IDs and nonfinite JSON. Their first attempt had **42 passed / 1 failed**: the test incorrectly expected a JSON exponent overflow (`1e999`) to fail *decoding before an attempt*. Existing `decode` rejects literal `NaN` and `Infinity` constants immediately; a numerical exponent parsed as float64 infinity is instead rejected by the authoritative scene parser and **retained as a rejected proposal**. Both correctly refuse the physical revision, and no existing revision was changed. The author changed only the test expectation to distinguish the two honest failure boundaries. The follow-up targeted combined run completed **165 passed**. The original first-failure log remains at `/mnt/data/particle-v1_newtests_final_preflight.log` in the local developer workspace.

The first attempt at a full regression suite was launched from a source checkout that was **not editably installed**: pytest found the local `src` package, but six subprocess tests could not import `emfeeld` in freshly invoked Python interpreters, producing **1,296 passed / 6 failed**. Those failures did not implicate particle calculations or the solver. The project was subsequently installed **locally in the isolated qualification container only** with `python -m pip install -e . --no-deps --no-build-isolation`; no user installation was affected and no production file or test expectation changed to suppress the failures.

**Final, current-source local qualification** with installed package:

| Gate | Result | Exact command |
|---|---|---|
| Full headless suite | **1,308 passed** | `python -m pytest -q -W error tests` |
| Historical behavioral checks | **18 passed, 1 historical whole-file-freeze guard deselected unchanged** | `python -m pytest -q -W error pilots/authorability_v1/test_pilot.py -k 'not test_all_available_parent_files_remain_frozen'` |
| Particle and existing structural/model revisions | **165 passed** | `python -m pytest -q -W error tests/test_particle_revisions.py tests/test_structural_revisions.py tests/test_model_revisions.py` |
| E1/G1/T1 fresh native transfer | **7 complete runs; 1 intentionally rejected analysis; 4 accepted revisions** | `python tools/qualify_particle_revisions.py --output NEW_OUTPUT` |
| Separate ideal-source/RK4 check | **34 static + 6 full-trajectory checks passed** | `python verification/check_particle_revision_runs.py OUTPUT --report NEW_REFERENCE_JSON` |
| Source compile | **passed** | `python -m compileall -q src tests tools verification` |

**This is still author qualification, not independent review or Linux/Windows fresh-checkout CI.** Local PyVista is unavailable; real rendering must be proven in hosted CI. An additional final snapshot of the source tree will be bound by exact Git SHA before central independent review. Do not sum duplicate cases across suites as distinct capabilities.
