# Question-first evidence checkpoint V1 (candidate)

**Purpose:** prepare a verifiable *source-first* workflow for a future **prospective, externally supplied question**. This is a local developer tool, **not** a natural-language physics interpreter, a blind teacher experiment or a new field solver. The bundled gravity example is deliberately **developer-authored** and cannot be counted as an independent teacher task.

## What is new, and what is not

The existing question-to-packet workflow begins with correctly interpreting supplied facts. A source-aware author can later rewrite that question to match a simulation unless the original wording is retained first. This V1 tool allows someone to **freeze the original question bytes and its declared requested measurements before preparing a scene or solver packet**. The later assessment checks exact source and authored packet bytes, strict native observation coverage and actual native unit/status outcomes. All results preserve source and packet SHA-256 receipts.

A *local* hash checkpoint is **not an authenticated timestamp or independent source identity**: a person who can rewrite and re-seal both files can fabricate its history. To call a task genuinely prospective, a separate teacher or question provider must supply an unseen source; the question receipt must be externally timestamped/committed *before the author sees reference answers*, and a separate reviewer must independently assess the author's interpretation, physics model and numerical reference. The fixture's `source.origin` value is a **declaration** (only `developer_authored` or `external_unverified`), never evidence that a teacher actually supplied it.

## Exact data contract

A UTF-8 question JSON has exactly these keys:

- `trial_version` (integer 1), `id` (safe unique trial identifier), `source` (`origin`, `label`, `question` strings);
- five arrays: `givens`, `assumptions`, `illustrative_choices`, `unresolved_information`, `requirements`;
- `requested_measurements`, a bounded ordered array of `{id, quantity, unit, native_type, [native_quantity], context}` declarations; `native_quantity` is required for `trajectory_sample` and forbidden for static requests. The native type/quantity is checked against both the authored packet and actual returned measurement, preventing a same-unit substitution such as total versus potential energy. `context` freezes exact static world points, ordered potential-difference endpoints, or native trajectory particle/sample index **and expected actual saved physical time**.

Every `id` is the *exact* desired native observation ID. Declared `native_type` is one of `field`, `potential`, `force`, `potential_difference`, or `trajectory_sample`; saved sample `native_quantity` is one of the existing observation quantities. A human-written `quantity` label remains a statement, not a semantic judge. For a static field/potential/force probe, `context={"position_m":[x,y,z]}`. For potential differences, `context` declares `from_m`, `to_m`, and the exact `convention="potential(to_m) - potential(from_m)"`. For a trajectory sample, `context` declares `particle_index`, `sample_index` and `time_s`. V1 accepts only static probes and saved-index trajectory samples (not event searches or nearest-time selection); these are refused rather than treated as fulfilled native observations. Context is compared to the authored packet before execution and against **actual** saved native result metadata afterward. Saved time admits, at most, a one-ULP representational rounding difference for nonzero instants **and** less than a quarter of the declared native sample spacing; time zero must match exactly. It never uses a fixed absolute time window that could accept a physically different instant at short timescales. This guards against obtaining the correct measurement ID/unit at the wrong point or time. `quantity` is human text, **not machine-semantic proof**. Every `unit` is checked against the native result, but choosing the wrong expected physical quantity or a dishonestly interpreted requirement is still possible. All arrays and strings are bounded; malformed UTF-8/JSON, duplicate keys, unknown keys/IDs, nonfinite JSON tokens and claimed verified/teacher origin codes are rejected.

**Freeze admits original questions even when they declare unsupported physics or unresolved givens.** Assessment then stops **before any integration or output** if unresolved information remains or if a requirement is outside the qualified `fixed_prescribed_sources` and `independent_nonrelativistic_test_particles` subset. This prevents silently replacing `conductor_polarization`, magnetic Lorentz dynamics or other unimplemented laws with a conveniently executable different model. This is conditional on the author **honestly recording** requirements; unrecognized implications in arbitrary prose are *not* automatically detected.

## Freeze first; author second; assess last

From a clean repository checkout with existing dependencies installed:

```sh
python verification/question_first_trial_v1.py freeze \
  examples/question_first_v1/developer_question.json \
  --output output/question-first-lock-001

# Only after the question is locked, author a data-only observation packet.
python -m emfeeld.observations examples/question_first_v1/developer_packet.json --validate-only

python verification/question_first_trial_v1.py assess \
  output/question-first-lock-001 \
  --packet examples/question_first_v1/developer_packet.json \
  --output output/question-first-attempt-001
```

Both destinations **must be new**. `freeze` saves the original raw `question.json` bytes and a `receipt.json` containing their SHA-256 and exact requested IDs. `assess` verifies the receipt against those frozen raw bytes, validates the authored packet through the **existing** `packet_from_dict`, requires exactly the question's declared observation IDs and locked point/time/endpoint context, and rejects answer-bearing `expectation` values inside the packet. It then saves the exact original `question.json`, `receipt.json`, authored `packet.json`, full native `native-result.json`, and `assessment.json` with separate statuses. A `state.json` starts as `execution_complete=false` and switches to `true` only after all results are saved. If unexpected execution fails, original captured inputs and the incomplete marker remain available; no failure is reclassified as success.

Return status: **0** = valid source freeze, or completed *native requested-measurement coverage* during assessment; **1** = an honestly incomplete native result, including a missing event/undefined field/wrong unit; **2** = invalid source, unresolved/unsupported requirement, rejected packet or input/output admission failure. A status 0 from `assess` **never** asserts physical correctness, faithful prose interpretation, independent reference validation, teacher usefulness, or textbook completeness. These remain explicitly `not_verified`/`not_evaluated`. Do not treat a solver/CLI exit 0 or `no_event` as a fulfilled measurement.

## Bounded illustrative example, not a prospective independent result

The checked-in example asks about **a single nonrelativistic test mass** in a fixed, prescribed uniform gravitational field `g=(0,-2,0) m/s²`. Its initial state is `r0=(1,2,0) m`, `v0=(0.4,1.2,0.1) m/s`, mass `2.5 kg`, duration `2 s`, 21 saved samples, and gravitational potential zero at the origin. Its data-only observation packet asks for the launch field, final position/velocity and initial/final total energy, using the **existing** uniform gravity field law and trajectory sample API.

For a **separately expressed same-author physics reference**, `r(t)=r0+v0t+gt²/2`, `v(t)=v0+gt`, `Phi(r)=-g·(r-origin)`. At 2 s the exact predictions are `r=(1.8,0.4,0.2) m`, `v=(0.4,-2.8,0.1) m/s`; `K+m Phi=12.0125 J` at both saved endpoints. Tests compare these directly without putting answers into the native packet. No feedback, ground collision, drag or relativistic motion is modeled; this is *not* an externally posed student problem.

The headless Linux/Windows release CI executes this exact example and retains its original question, question receipt, packet, native JSON and assessment inside the archived `question-first-v1` directory for later byte/CRC audit. The existing 18 historical behavioral and 33 real-PyVista tests remain separate from the added headless cases; rendering is not evidence of educational usefulness.

## Next scientific gate

A truly prospective evaluation requires an **independently sourced, previously unseen physical question** (preferably supplied by a teacher). First record its raw wording and original factual context in a frozen intake with independently verifiable ordering; then let an author who has **not seen the judge's answer** supply the scene and complete observation requests, capture the first attempt and all refusals unchanged, and have a distinct judge check source interpretation, physical/numerical correctness, requested measurement coverage, teaching usefulness and any requested textbook answer separately. Review failures honestly rather than rewriting the question to fit the engine. This V1 supplies the checkpoint/coverage mechanics only; no such held-out study or classroom outcome is claimed.

**Scientific boundaries:** no magnetic field law, radiation, Maxwell/conductor polarization, particle-particle coupling, collision handling, independent teacher certification, authentication of maliciously fully re-sealed unkeyed receipts, adversarial distributed filesystem atomicity or numerical global-error guarantee.
