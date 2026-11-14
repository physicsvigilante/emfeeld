# Static observation authoring: qualification — 2026-11-13

## Identity and scope

Parent: `e725639f3220518e5262875d0fd48658b52e0db1`, tree `f87be720d1767355cec668d57cbd402e14df84c6`. This report covers the additive observation layer in the commit containing this file. The user approved field/potential/test-force probes and potential differences after the authorability pilot; this is not approval to merge or extend physics.

**Author verification only; no independent review. PR #1 remains draft and unmerged.** The chat-only acceptance policy is unchanged. No Windows interaction or new visualization qualification is asserted.

New production functionality is confined to `src/emfeeld/observations.py`. All previously published files are retained byte-for-byte. This includes source laws, solver, integrals, original scene schema/CLI, viewer/playback, dependencies, original examples, earlier tests, and all of authorability_v1. New tests, contracts and observation-packet examples are additive. The main-branch PDF is not edited.

## Executed environment and source identity

Linux / CPython 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / pytest 9.0.2. Existing optional real-viewer regressions used PyVista 0.48.4 and VTK 9.6.2. The six previously uploaded wheels matched their transfer manifest hashes and were installed with `--no-index --no-deps` into a container-local directory. No user-machine installation or new dependency was introduced; a transfer hash is not a fresh independent upstream provenance check.

The prior evidence archive supplied a 56-file source copy. Its src, tests, examples, tools, viewer_tests and pilots Git subtree hashes matched the live pinned parent. README/AGENTS and available documents were checked as part of preservation. Four other parent entries (workflow, gitignore and two historical documents) are inherited unchanged at publication. Required historical documents were read through the connector/context. This is a verified source copy, not a complete local clone.

## Results

| Check | Result |
|---|---|
| Unchanged parent: tests + viewer_tests + historical pilot tests | **210 passed**, no skips |
| First new contract test run | 89 passed, 1 test-fixture failure |
| Corrected initial observation checks | 90 passed |
| Expanded observation/example contract tests | **106 passed** |
| Final cumulative tests, warnings treated as errors | **316 passed**, no skips |
| Generic-runner observation packets | 11 packets / 39 requests checked |
| Successful requested measurements | **38**, all authored reference checks passed |
| Deliberate shell-surface field request | **1 domain_error**, null value; potential still returned |
| Actual CLI runs and output-file round trips | 11 matched JSON reports; 10 exit 0, intended partial packet exit 1 |
| Original frozen-engine pilot rerun | **11 PASS / 1 PARTIAL / 0 FAIL / 0 ERROR** |
| Original pilot strict mode | Exit 1, retaining SC-158 PARTIAL |
| Original reconstructed files | **56/56 byte-unchanged** |
| Compilation | PASS |

The 316 cumulative cases consist of the original 210 (including nine real-viewer tests and 19 pilot guards) plus 106 new headless observation checks. No old assertion, tolerance, example or historical acceptance record was changed. No skips or xfails were added. The first new-test failure supplied a NumPy scalar to an intentionally JSON-only interface; the fixture was corrected with `float(...)`, without weakening validation or changing source behavior. The original failure log is retained.

## Coverage and limitations

The new checks cover electric/gravitational units and signs, test-charge/test-mass coupling, potential-difference direction, reference shifts, zero source strength, singular endpoints, oblique line/plane roundoff boundaries, shell field versus potential, nested grouping/source multiplicity, translations and rotations, finite result validation, overflow, exact result shapes, duplicate ids/JSON keys, unsupported requests, wrong-domain coupling, bool/string/unit rejection, authored-reference failure, no expectation broadcasting, unchanged input, stable hashes, CLI exit codes, input overwrite protection and output round trips. Static observation is checked not to call trajectory integration or import PyVista.

Eight observation packets reuse exactly the scene objects from SC-55, SC-35, SC-96, SC-122, MC-33, NUM-31, ARCH-ADV-MC-05 and SOL-26. Their requests exercise existing fields/potentials rather than the full original question in every case. Two additional packets are labelled illustrative (line potential reference; gravitational composition), not new corpus coverage. The last packet deliberately requests an undefined shell-surface field alongside its valid potential.

NUM-31 again produces **35.11136897797393 V**. SC-55 again produces force magnitude **0.008987551786170797 N**. The gravitational composition packet returns acceleration in m/s^2, specific potential in J/kg and force in N for an explicit test mass. The reference algebra used to write expectations is separately expressed from the evaluator but authored by the same assistant. This is not an autonomous authoring reliability score or independent verification.

The original SC-158 singular-surface flux case remains PARTIAL in the unchanged pilot; the new interface rejects flux requests instead of hiding that limitation. No new flux algorithm, source, conductor response, mixed electric/gravity coupling, trajectory crossing, turning-point solver or probe annotation was added. No fresh image inspection was needed for an unchanged viewer; the existing nine real runtime tests were rerun. Windows keyboard/mouse operation and arbitrary dependency versions remain untested.

Expectation tolerances are comparison tolerances, not solver accuracy guarantees. Reports explicitly leave `error_bound` null. Floating-point cancellation of nearly equal potentials and extreme-scale underflow remain unqualified. Successful schema-only validation is never described as successful physical evaluation.

## Reproduce

From a checkout with the existing dependencies available (set `PYTHONPATH=src` for an uninstalled source tree):

```text
python -m pytest -q -W error tests viewer_tests pilots/authorability_v1/test_pilot.py
python -m compileall -q src tests viewer_tests tools pilots
python -m emfeeld.observations examples/observations/sc-55.json --output output/sc55-observations.json
python -m emfeeld.observations examples/observations/num-31.json --output output/cavity-observations.json
python -m emfeeld.observations examples/observations/gravity_composition.json --output output/gravity-observations.json
python -m emfeeld.observations examples/observations/domain_errors.json --output output/domain-errors.json
python pilots/authorability_v1/run_pilot.py --strict --output output/legacy-pilot
```

The final two commands intentionally exit 1 for distinct documented reasons: a requested domain error and the historical partial flux case. Do not turn these into skipped tests or rewrite the historical result. The accompanying chat bundle retains complete outputs, logs, source copies, baseline identities and publication hashes.

## Next bounded opportunity

After acceptance, extend the same request/result design to observations of saved trajectory samples (time, position, velocity, speed and energies), without changing the solver. Crossing/turning events and singular-surface flux need their own contracts and qualification, not hidden per-question Python in the engine.
