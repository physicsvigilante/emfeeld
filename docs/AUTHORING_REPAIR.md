# Authoring safety and published-byte replay repair — 2026-11-14

## Scope and identity

Reviewed parent: `51b286842e837da4135989a3a6e5c7f81be6981f`, tree
`f00650e1415343ee9ef2e49027e0cc8ded4c9277`. The user requested correction of
project errors and continued development. This pass fixes reproducible input/I/O
bugs and adds a repository-resident authoring verification workflow. It does not
add physical laws, another source-aware benchmark, or permission to merge.
PR #1 remains draft and unmerged. These are author-run checks, not independent
review or Windows qualification.

## Reproduced defects and fixes

1. **Input destruction.** `emfeeld run scene.json --output scene.json` returned
   success and replaced the input JSON with a ZIP/NPZ header. The view screenshot
   path had the same missing protection. Both paths now reject equal, relative,
   symbolic-link and hard-link aliases before solving or rendering.
2. **Partial output replacement.** A simulated NPZ serialization failure left an
   existing result truncated. Numerical export now serializes to a temporary file
   in the destination directory and replaces the output only after success;
   ordinary failed writes clean up the temporary file and retain the prior result.
3. **Numeric coercion at the scene boundary.** The old scene loader accepted
   numeric strings, boolean coordinates/velocities and boolean/string bounds.
   It now requires finite JSON numbers before constructing sources and particles.
   The observation-packet interface already enforced this policy; both entry
   points now agree. Low-level Python field constructors are unchanged.
4. **Malformed source tags.** Array/dictionary source tags raised an unhandled
   `TypeError` in the public scene parser. They now produce a schema `ValueError`.
5. **Publication/verification gap.** Prior v3–v6 descriptions acknowledged that
   published packets were reserialized and not rerun from their GitHub bytes.
   All ten v6 packet copies in this pass match their live published Git blob IDs
   exactly. A generic runner, byte-hash manifest and separate reference-generation
   script are now in the repository, rather than only in a chat archive.

The first regression run reproduced **24 failures and 28 passes** across the 52
new safety cases. All 52 pass after the corrections. Another 34 tests cover
published packets and verifier mutation/rejection behavior. Missing event state,
wrong units, changed input hashes, mismatched shapes and unexpected `no_event`
are not successful reference checks. No old assertion or tolerance was relaxed.

## Executed validation

| Completed group | Result |
|---|---:|
| Existing static, scene, observation, geometry and playback tests | 288 passed |
| Existing saved-state, plane and radial observation tests | 288 passed |
| Existing turning and rest-launch tests | 188 passed |
| Existing live pilot-v2 compatibility plus pilot-v1 behavioral cases | 28 passed |
| Existing real PyVista viewer regressions | 9 passed |
| New safety and published-byte replay tests | 86 passed |
| **Current reproducible behavioral suite** | **887 passed, no skips** |

Warnings were errors. Every listed batch completed with exit code zero. One
historical all-file freeze assertion was explicitly deselected in the pilot-v1
behavioral run; see the accounting boundary below. An initial combined baseline
command timed out after progress reached 100% but without a final summary/exit
status. That interrupted command is retained and **not counted as a pass**.

The final replay command ran **10 exact published packets / 27 observations /
58 separate numerical, unit and refinement checks**, all passing. The runner
retains the copied input bytes, raw native result, per-check assessment and
current engine-module SHA256 hashes. The source packets were not edited. The
line-charge crossing is checked against an energy expression and a separate
regularized time integral. Other references use symmetry and analytic source
expressions. They were prepared by the same assistant, not an independent judge.
Compilation passed. No new screenshot qualification was needed or claimed.

## Test-accounting correction

The previous 837, 843, 865 and 820 totals combined the same engine baseline with
*different* chat-local pilot suites; they are not a monotonically accumulated
repository suite and must not be added together. This report names the actual
current groups. It does not claim that every historical chat-only test was rerun.

Pilot-v1 and pilot-v2 all-file freeze guards remain unmodified historical evidence.
They intentionally reject changed production files, including this corrected
scene/CLI code. Run those exact guards on their recorded snapshots. The live
suite replays their applicable behavioral cases instead; the original tests,
input hashes and outcomes were not rewritten to manufacture a new freeze pass.
V3–v5 published bytes are not newly qualified by this bounded v6 replay.

## Preservation and environment

The parent source, tests, examples, tools and viewer-test subtree hashes matched
the live repository before editing. The source was reconstructed from supplied
evidence, with content-addressed verification; this is not a full Git clone.
All ten v6 packet blob hashes were separately checked against live GitHub data.

Only two production modules change: `scene.py` and `cli.py`. The other fourteen
engine modules, analytic laws, original integrator, event algorithms, viewer,
playback, dependencies, old tests, old pilots, PDF and main branch are untouched.
README and AGENTS now point to the actual current authoring workflow. The new
runner has no question-specific equations or replacement simulation outputs.
The reference-preparation script is separate and does not call the engine.

Linux / Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / pytest 9.0.2;
PyVista 0.48.4 / VTK 9.6.2 for existing viewer tests. Six previously supplied
wheel transfer hashes were verified before offline, container-only installation.
No user-machine installations, new dependencies or license changes occurred.

New/modified publication blobs must match the tested local file hashes before
advancing the branch; inherited files remain at their parent tree identities.
Raw failing/passing logs, reconstructed source, packet outputs and publication
identity are supplied with the chat evidence archive. Historical reports remain
unchanged; this report supersedes no earlier recorded failure.

## Reproduction

```text
python -m pytest -q -W error tests
python -m pytest -q -W error pilots/authorability_v1/test_pilot.py -k "not test_all_available_parent_files_remain_frozen"
python -m pytest -q -W error viewer_tests
python tools/replay_packets.py verification/v6_published.json --output output/replay-001
python -m compileall -q src tests tools verification
```

The first command covers 860 current headless tests; the next two add 18 pilot-v1
behavioral and 9 viewer tests. Use a new replay output directory for each attempt.
The repository runner works without old chat archives. See AUTHORING_WORKFLOW.md
for the question-to-packet procedure, unsupported-model policy and result claims.
Native event completeness, global closest approach, inverse solving, conductor
response and simultaneous electric/gravitational coupling are not added here.
