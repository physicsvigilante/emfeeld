# Native revision-and-view command — qualification

## Candidate scope

Runtime parent: `11a20f9c9a1f64b535116ab08c3beafdc492ef93` (draft PR #4).
Work is on `feature/native-revision-view`, stacked on that candidate. No existing
PR or main branch is merged or modified. This is same-author verification, not
independent review, automatic physical interpretation or teacher acceptance.

`model_cli.py` composes the existing named revision, execution and recorded-view
operations. `cli.py` adds a small lazy dispatcher. The existing source laws,
model store/derivation, scene parser, observation/event code, integrator, viewer,
playback, native run implementation, dependency constraints and historical tests
remain unchanged. The exact-parent proposal format is not replaced by another
revision protocol. The portable helper store is not silently upgraded.

## Completed local qualification

| Completed gate | Result |
|---|---:|
| Current headless tests | 1065 passed |
| Historical pilot-v1 behavioral cases | 18 passed, 1 historical freeze assertion deselected |
| Real PyVista tests | 25 passed |
| **Current behavioral coverage** | **1108 passed** |
| New cases within that total | 31 headless + 3 real-render tests |
| Original v6 replay | 10 cases / 58 declared checks passed |
| Discovery replay | 2 cases / 36 declared checks passed |
| Native CLI example applications | 4 completed; 4 real snapshots |
| Existing separate harmonic/Kepler checker | 54/54 passed |
| Compilation | Passed |

Counted tests completed with warnings as errors. No skip, xfail or relaxed existing
tolerance was introduced. The 1074 previous behavioral cases are retained; repeated
executions and platforms are not added to coverage. The old frozen-source assertion
remains unchanged and belongs to its pinned historical snapshot.

New tests cover exact inherited settings, immutable roots and old runs, chained
launch revisions, stale parent/old value, wrong role, unsupported edits, no-op,
output conflicts and protected directories, wrong-model/corrupted run settings,
input capture, pending unexpected failures, unavailable graphics, retained native
results, no-event and reference mismatch, a singular revised launch, static queries
without invented motion, explicit portable-store rejection and actual module CLI
execution. Real renderer tests check nonblank recorded images, paths containing
spaces and reopening without reintegration. Desktop-opening routing is tested;
no human Windows desktop interaction for this new command is claimed.

## Numerical and visual evidence

The driver imports the unchanged electric discovery and ideal-Sun fixtures once
per domain. Both existing source and launch hypothesis files are applied by actual
`python -m emfeeld model apply` subprocesses. Parent references are filled from the
native store; no physical answer is supplied by the driver. Root observations and
static descendant investigations use the existing execution interface. Exact copies
of the generated motion runs are arranged for the unchanged separate-expression
checker; the copies are not extra executions or replacement numerical answers.

All four native applications completed, all requested observations/checks succeeded,
and the original model bytes remained unchanged. The existing checker passed 54
harmonic/Kepler/field/potential/energy comparisons. It does not import emfeeld but is
same-author verification of illustrative exposed fixtures, not a blind benchmark.
The four snapshots show identified recorded runs, not a time transition between
hypotheses. Individual colour scales are not a quantitative side-by-side comparison.

## Source and execution provenance

Direct GitHub clone failed DNS in the chat container. A read-only GitHub Actions
source-snapshot job supplied a Git archive of the exact branch state before runtime
editing. All 281 archived file Git blob identities matched its `git ls-tree` record;
the ZIP and TAR transfer hashes were checked. This is a content-verified source
recovery, not a native local clone. Source-snapshot success is not physics testing.

Local Python 3.13.5 uses the existing numerical stack. Six previously supplied
viewer wheels (PyVista 0.48.4 and supporting packages) matched their transfer
manifest and were installed offline into a container-local target. VTK 9.6.2 is
provided by the environment. No user computer, system graphics setting or project
dependency range was changed.

The initial bare-source baseline test invocation lacked PYTHONPATH for subprocesses:
1030 tests passed and four child-import checks failed with `ModuleNotFoundError`.
The source-path test harness was corrected; no production code or assertion was
changed to address those harness failures. An initial new-test command timed out
after partial progress and is not counted. The completed rerun passed all 31 new
headless tests. Original logs are retained in the evidence bundle.

Current-commit Linux/Windows CI results must be checked separately after publication.
Parent runs and a source-snapshot job are not a pass for new runtime code. CI now
admits PRs based on the native-revision parent and executes the new driver/checker
in addition to all retained gates. Stop for explicit acceptance before any merge.
