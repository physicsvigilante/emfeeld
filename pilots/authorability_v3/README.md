# Authorability pilot v3 — new electrostatic/gravitational arrangements

Frozen-engine authoring cohort against engine commit `08571d366a0499d2110de0929d91db7d5caa6c7f`. Seven data-only JSON scene-plus-observation packets are provided in `packets/`, and two deliberately unsupported physical-model controls in `controls/`. No core physics code has changed.

| Packet | Source | What it exercises |
|---|---|---|
| sc-66.json | Single Correct Q66; PDF 28/book 1.168 | Three charged square vertices; 3D field |
| sc-86.json | Single Correct Q86; PDF 31/book 1.171 | Zero potential on an axis; nonzero field |
| sc-36.json | Single Correct Q36; PDF 25/book 1.165 | Concentric prescribed shell superposition |
| sc-102.json | Single Correct Q102; PDF 33/book 1.173 | Symmetric conductor **gap field only**; prescribed thin-shell equivalence |
| sc-157.json | Single Correct Q157; PDF 40/book 1.180 | Opposite charges on z axis; full vector field |
| num-7.json | Integer Q7; PDF 69/book 1.209 | Negative charge moving through two-charge field; first later turn |
| grav-triad.json | Illustrative (not from PDF) | 3 fixed masses; off-axis trajectory and plane crossing |
| controls/sc-69-conductor.json | Single Correct Q69; PDF 29/book 1.169 | Unsupported conductor polarization |
| controls/sc-80-nonuniform.json | Single Correct Q80; PDF 30/book 1.170 | Unsupported radial density 1/r |

Execute a packet with:

```sh
python -m emfeeld.observations pilots/authorability_v3/packets/num-7.json --output output/num7.json
```

The chat-local authorability evidence bundle contains the complete generic test runner, predeclared and corrected numerical references, source hashes, frozen-file guards, 3 attempt logs, tests and real PyVista screenshots. Those evidence files are **not** included in this repository commit. All nine JSON files here have the same model/observation numeric parameters as the tested packets but are reserialized; only the chat-local bundle is byte-identical to the tested candidate.

The local study recorded 7 supported cases passing and 2 controls rejected, after two JSON schema corrections and one **same-author reference sign correction**. Do **not** call that a first-attempt 7/7 result, a blind benchmark, independent review, an all-parameter proof, or a qualification of conductor response. The current-engine baseline 802 tests and 35 new local pilot tests passed. Original historical freeze checks remain pinned to their earlier commit. The event solver does not certify root completeness or global extrema.

PR #1 remains draft and unmerged. No screenshot/UI changes, Windows qualification, license change or new physics sources are claimed.
