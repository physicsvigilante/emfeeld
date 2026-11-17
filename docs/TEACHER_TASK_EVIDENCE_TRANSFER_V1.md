# Teacher-task evidence transfer V1 — frozen author-selected pilot

**Status:** a development-authored, retrospective, **not-blind** pilot; it does not establish teacher acceptance or independent physics certification. Tracking [Issue #30](https://github.com/physicsvigilante/emfeeld/issues/30). This is a bounded evidence-transfer demonstration rather than a new field solver, natural-language parser, or another Markdown renderer.

## Verified original source and authored questions

- Fully post-merge release-qualified `main` source: **`3f1ec44a54b24b9f8275a98abf81126a9386bf61`**, Git tree **`3d9fa4c8b594e46837e6825590e4e5d72db9a030`**. [PR #29 release report](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/emfeeld/pr-29/MERGE-REPORT.md).
- Frozen development-author-authored [three-question fixture](../pilots/teacher_transfer_v1/questions.json), SHA256 **`536ada6775aa3effb7abafaef742f7cb0030ce4428bcecf1d4664e1025436008`**. Question choices were made **after** source scenarios were available. The physical alternatives in original V3 proposals were marked `illustrative_choice`, **not provided textbook givens**. Do not advertise a blind held-out authoring benchmark.
- Exact original main release ZIPs: Linux [14300302937](https://github.com/physicsvigilante/emfeeld/actions/runs/44019720004/artifacts/14300302937), SHA256 **`0654fa7d39249c4026945295ce15a18eae46a8598325e66d321cd515aa1e7f55`**; Windows [14301401780](https://github.com/physicsvigilante/emfeeld/actions/runs/44019720004/artifacts/14301401780), SHA256 **`be72aef030afef113758a671aa93363b7e01af51ad9e79d942b91ea508c9a27e`**. The archives remain untouched, and no cross-OS byte identity is assumed.

## Pilot interface and safeguards

The opt-in, read-only [pilot runner](../verification/teacher_transfer_pilot_v1.py) receives one **explicit frozen release ZIP** and its declared OS. It checks full original ZIP SHA256 against the frozen fixture, the exact merged `head-sha.txt`, unique case-insensitive archive entries, path safety, rejected symbolic links, bounded decompressed sizes and full ZIP CRC before touching original scenario content. It extracts **only** the archived `scenario-ensembles` files to a disposable directory and invokes the unchanged, fully source-bound **`read_ensemble_measurements`** on original E1, G1, T1 studies. No second physics engine/inspector, new integration, numeric rounding, unit conversion or model-store edit is introduced. Results go only to JSON stdout; no new application-managed file destination exists.

Run with existing dependencies installed from the repository root:

```bash
PYTHONPATH=src python verification/teacher_transfer_pilot_v1.py /path/to/original-main-linux.zip --platform linux > /tmp/teaching-pilot-linux.json
PYTHONPATH=src python verification/teacher_transfer_pilot_v1.py /path/to/original-main-windows.zip --platform windows > /tmp/teaching-pilot-windows.json
```

The redirected `/tmp` files above are caller-managed **disposable captures**, **never** paths inside a sealed native run. Both author-side executions returned status 0 and emitted exact-source-bound JSON to stdout. The result captures are reproducible using these two commands; the frozen source fixture and original archive hashes, rather than a second checked-in result, are the audit inputs. The original archive SHA256 and preserved native input hashes were independently audited in PR #29; extraction was confined to temporary paths, not the user's actual model store.

## Actual author-run illustrative questions and observed outcomes

| Frozen question | Original verified saved measurement | Interpretation limits |
|---|---|---|
| **E1, field magnitude at `(1.5, -0.4, 1.4) m`: which independently authored source replacement decreases/increases it?** | hypothesis-A **`-0.05458851160751549 N/C`**, hypothesis-B **`+0.18513207463551812 N/C`**, both signed **right member minus common fresh baseline**, original E1 global `complete` | A has a negative **change in magnitude** and B a positive change; neither reports a negative **absolute** magnitude. Both are independent line-source replacements (an illustrative prescribed-source choice), **not** sequential charging/translating source events. |
| **G1, body_4 added only in hypothesis-B: what is its position difference from baseline?** | Original measurement `body-4-absent` reports **`unavailable` / `unknown_operand` / `null`**; original G1 global comparison `partial`, hypothesis-B native execution complete | No baseline body_4 counterpart exists. The answer is **not a zero displacement** and may not silently retarget to another particle's array index. |
| **T1, ordered static potential difference from `(0.4, 0.6, 0.3) m` to `(2.8, 0.25, 0.4) m`: what is the saved source-alternative delta?** | hypothesis-A **`+1.1741058461436236 V`**, hypothesis-B **`+1.513997527981914 V`**, each signed right-minus-left, T1 global `complete` | Original potential endpoint order is explicit. Each hypothesis changes **both** the prescribed shell and point-source charges; the total result cannot be attributed to only one source, and neither is a responsive conducting sphere. |

These particular selected values were obtained from both original OS archives. The original result JSONs carry **the exact saved member reference and original native comparison request/result/integrity/left-right-run SHA256 receipts**. The development-author-selected questions are illustrative, not independently judged explanations or general physical-law claims. Some other original native values or receipts differ slightly by OS; that is not corrected by rounding this pilot.

## Five separate evaluation dimensions

| Dimension | Evidence and honest status |
|---|---|
| **Interpretation fidelity** | Questions name supported original observation IDs, context, unit and hypotheses; this is an **author-selected matching exercise**, not a blind independent interpretation of a teacher's own givens. |
| **Physical/numerical correctness** | Values and units correspond to original native-complete source-validated E1/G1/T1 saved runs and comparison receipts, already qualified by current-source CI and original archive checks. **No new independent human physics derivation or general-law certification.** |
| **Simulation/measurement coverage** | **Four original numerical measurements fulfilled; one explicitly unavailable** (`unknown_operand/null`). The unavailable one is never reclassified as solved or zero. |
| **Educational usefulness** | **NOT EVALUATED**. No teacher/student interaction, comprehension assessment or classroom acceptance. |
| **Textbook-answer completeness** | **NOT EVALUATED**. These are three bounded source-evidence requests, not a textbook-solution-format benchmark. |

## Qualification and scope boundaries

- Two original Linux/Windows merged-main ZIPs passed the pilot with **three questions**, four genuine numerical results, one honest unavailable and exact original provenance. Author-run stdout JSON SHA256 (reproducible outputs, not separately checked-in result files): Linux **`0e0d0db21e19b5075df9be3069937f88156dbe914cd1cd0e987a0ba7cba3aab7`**, Windows **`20615a519c9f674387ce6d9e29f307f8227c5e1f372441f077f2877a09e483bb`**. These are **author-side evidence**, not independently reviewed results.
- **13 initial author-written unit cases** passed with `pytest -q -W error tests/test_teacher_transfer_pilot_v1.py`: frozen question identity/version, exact archive hash refusal, invalid declared OS, ZIP traversal/case collisions/symlink refusal. No original ZIP or sealed study was modified. These tests alone are not the entire repository or independent reviewer qualification.
- The original `read_ensemble_measurements` preflight and PR #27 B1 nested integrity byte binding remain the sole native source-authority path. A future adversarial review must test selected/unselected source tamper, corrupted original ZIP and absence of writes. Do not claim unkeyed digest authentication against malicious full resealing, concurrent-writer/ACID safety, manual Windows mouse interaction, teacher usefulness or actual physical time evolution between alternatives.
- Since this new verification wrapper labels source evidence, classify as **R1 evidence interpretation/reporting**; require exact-source tests, both OS CI and a distinct Chat B focused independent review before merging any source PR. Escalate to R2 if numerical meaning, source identities or physical-law scope changes. Keep the source PR **DRAFT/UNMERGED** until those gates are met. A documentation/validation pilot does not change physics, add a solver or install anything in the user's Conda environment.
