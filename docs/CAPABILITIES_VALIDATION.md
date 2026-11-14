# Export integrity and capability discovery qualification — 2026-11-14

## Identity and scope

Parent: `69f0ccc46852c39f6bf52447fcb5352e6a3564f3`, tree
`465188fd79692b439dcb18d0d6cc67174bb284a4`. The user requested correction of
project errors and continued development. This adds machine-readable capability
discovery and fixes reproduced export/provenance defects. It is not a new physical
source library, autonomous authoring benchmark, general field solver or merge.
PR #1 remains draft and unmerged. Verification is by the same author in this chat.

## Reproduced defects

1. Numerical export reread the scene file after solving. Changing the file during
   the run caused the NPZ to contain the new scene JSON alongside results from the
   old scene. The CLI now parses and retains one captured document.
2. Screenshot export wrote directly to its destination. A render that wrote a
   partial file and then failed destroyed an existing image. The regression uses
   injected OSError/RuntimeError after a partial write; staged replacement now
   preserves the old image and closes the plotter.
3. PyVista appends `.png` to extensionless screenshots. The old alias guard checked
   only the unextended name, so an input named `scene.png` was not protected from
   `--screenshot scene`. The effective PNG destination is now checked before
   constructing a plotter. The installed PyVista implementation's suffix rule
   was inspected; real explicit/default-extension exports are also tested.

All seven new export-regression cases failed before the changes and passed after.
This is seven assertions covering three issues, not seven distinct physics bugs.
The source-file mutation and renderer failure cases deliberately inject those
conditions; they are not claims of unexplained corruption in a physical example.

## Authoring catalogue

`python -m emfeeld capabilities` produces versioned JSON. Source field keys are
shared with the scene parser. Observation enums, quantity units/shapes, event
options and exact-rest policy are read from runtime modules; remaining structural
metadata is checked against parser acceptance and rejection tests. All six source
families in both domains, four static observations, seven saved-state quantities,
three event conditions and the optional rest-launch policy are represented.

The catalogue reports restrictions rather than inventing support for conductors,
mixed electric/gravity coupling, feedback, collisions, inverse solving or packet
flux operations. It distinguishes static-only shells/planes from motion-safe
sources, and no numerical event from a solved observation. It is a descriptive
contract, not JSON Schema or a separate physics validator. Generating it does not
calculate fields, integrate particles, import PyVista or contact another service.

Two illustrative JSON packets combine two spheres and a uniform field in each
physical domain. A separate no-engine reference script uses harmonic motion and
interior potentials; the 36 predeclared checks passed on the first native replay.
No expected answers are embedded in the packets. No independent judge, unseen-
problem reliability rate, new corpus coverage or symbolic proof is claimed.

## Completed local checks

| Check | Result |
|---|---:|
| Current static/schema/authoring/playback group | 433 passed |
| Saved-state, plane and radial observations | 288 passed |
| Turning/rest-launch and live pilot-v2 compatibility | 198 passed |
| Historical pilot-v1 behavioral tests | 18 passed, 1 historical freeze assertion deselected |
| Real PyVista regressions, including two new export cases | 11 passed |
| **Current behavioral total** | **948 passed, no skips** |
| Exact prior v6 packet replay | 10 packets / 27 observations / 58 checks passed |
| New illustrative composition replay | 2 packets / 10 observations / 36 checks passed |
| Build and install wheel without network/dependency changes | PASS |
| Installed catalogue and both examples outside checkout | PASS |
| Compilation | PASS |

The previous 887 live tests are retained; 59 new headless and two real-export tests
add 61 cases. Historical all-file freeze guards are unchanged and belong on their
original commits, not current source. No old tolerance or assertion was relaxed,
and no skip/xfail was introduced. Warnings were errors in all completed test groups.
No new claim about every earlier chat-local pilot test is made.

## Preservation and evidence

The chat environment could not resolve github.com for a native clone. The source
was recovered from the exact GitHub CI archive of `19bc001`; its root hash matched
`fe5fc647882d9404e883eac7daabea21d2e0eada`. Its production, test, example, pilot,
verification and tool subtrees match the live parent. The later release workflow,
.gitattributes and release protocol are inherited unchanged by their Git identities.
This is a content-verified source copy, not a fresh local clone.

Only existing `scene.py` and `cli.py` production files change; `capabilities.py` is
added. Analytic fields, integrator, observation/event adapters, viewer/playback,
existing test files, dependencies, all historical evidence and authored examples
remain unchanged. README and AGENTS gain discovery guidance. Added example files
and references are explicit new illustrations, not replacements for old evidence.
Every published new/modified file must match its tested local Git blob hash before
the branch advances. No reserialization of tested packets is used for publication.

Local environment: Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2,
PyVista 0.48.4, VTK 9.6.2. The six previously uploaded wheels were transfer-hash
checked and installed offline into a container-local directory only. No user-PC
installation, new dependency, license change or native Windows interaction test.
New current-commit CI results, if executed, are separate from these local checks;
parent release-candidate passes do not by themselves qualify changed code.

## Reproduce

```text
python -m pytest -q -W error tests
python -m pytest -q -W error pilots/authorability_v1/test_pilot.py -k "not test_all_available_parent_files_remain_frozen"
python -m pytest -q -W error viewer_tests
python -m emfeeld capabilities --output output/capabilities.json
python tools/replay_packets.py verification/v6_published.json --output output/v6-replay-001
python tools/replay_packets.py verification/discovery_examples.json --output output/discovery-001
python -m compileall -q src tests viewer_tests tools verification
```

Use new replay directories. The first command has 919 tests; the next two add 18
and 11 respectively. The catalogue is available without the optional viewer extras.
Release acceptance and merging remain separate user decisions.
