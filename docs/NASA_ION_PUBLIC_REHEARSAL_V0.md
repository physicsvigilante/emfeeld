# NASA ion-grid public question rehearsal V0 — NON-BLIND

This is a **source-derived public educational rehearsal**, not the genuinely prospective, independently supplied teacher question and withheld-judge study tracked by Issue #36. It uses a previously published external exercise with the existing qualified native observation API. No solver, field law, numerical tolerance, model store, viewer or general question interpreter is changed.

## Source and provenance boundary

NASA Space Math, Sten Odenwald, *The Mathematics of Ion Rocket Engines*, p. 64, [official NASA PDF](https://spacemath.gsfc.nasa.gov/weekly/5Page64.pdf), Problem 1 and one auxiliary grid-spacing fact from Problem 2. The frozen question quotes only the final 21-word sentence of Problem 1; the other numerical facts are paraphrased separately. The original PDF is not copied or independently byte-authenticated in this repository. The PDF itself includes an answer key, which was visible to the author: **this is not blind**, not an original teacher-to-author submission, and not a verified withheld reference.

The source gives a xenon ion mass of **2.2e-25 kg**, positive charge **1.6e-19 C**, and energy gain across a **1300-V potential difference**, asking for speed in **km/hour**. Problem 2 separately gives **0.7 mm** grid separation. Combining the two problems to supply trajectory geometry is explicitly disclosed as an author modeling choice; Problem 1's speed does not depend on that gap.

## Verifiable question-first Git chronology

The branch descends from fully released PR #35 main commit **510014fc078c73d37146b9804763e29d04ac0018**. Source was frozen locally before the simulation packet was created, then retained in distinct ordered Git commits:

1. **b1faed6a75fa61b90614a494c837937626296826** — frozen question alone. Exact UTF-8 SHA256: **cd797751a84d86caa57c2024620215895c1414169c6682b96933e4b4cf25cc23**.
2. **a5a11dd36a16bc5b7560d8e3e43f882320b7bbba** — original generated receipt matching these bytes, with source authenticity **not_authenticated** and interpretation **not_verified**.
3. **e0a008119fca8289607ec2c337722da0bd3861dd** — only after the question lock, the data-only authored observation packet. Exact SHA256: **f86211065ec99e3e82181de256d321a6ebb054f9b397440996529a3ec6ccfeda**.

This shows local ordering, **not** externally authenticated source chronology, original PDF receipt, or proof an author had never encountered the answer key. Source origin is declared **external_unverified**.

## Explicit forward physics and limitations

To instantiate supported native physics, the author assumes a **stationary prescribed uniform electric field** along +x between grid entrance x=0 and exit x=0.0007 m, a nonrelativistic positive independent test ion starting from rest, and zero electric potential at the entry. Real ion thruster space charge, grid fringing, collisions, magnetic forces and source backreaction are excluded.

**Author-derived inputs, not source givens and not native inverse solving:** electric field E = 1300 V / 0.0007 m = **1,857,142.857 N/C**; acceleration a=qE/m; exit time t=sqrt(2d/a)=**3.2195317385273e-8 s**. The packet uses 21 saved samples and exactly one observation: native **speed in m/s at saved index 20**. The original source requests **km/hour**, so the explicit conversion by a factor of 3.6 is performed outside the native report. No expected answer is embedded in the data-only packet.

## Original first local native attempt

Original qualified main source Git tree: **a82188148568653311581d9d4c02e8c96a37d3cf**. Offline Linux, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0. The original source freeze, packet validation and first public assessment succeeded. The original question/packet/receipt/native-result/assessment/state files were retained separately without rewriting the source.

- Original frozen question SHA256: **cd797751a84d86caa57c2024620215895c1414169c6682b96933e4b4cf25cc23**.
- Original authored packet SHA256: **f86211065ec99e3e82181de256d321a6ebb054f9b397440996529a3ec6ccfeda**.
- Original first native-result JSON SHA256: **e52abdc544dc5677703931d6194c85939dd74e02943690ca4c92324f1d6d5ae3**.
- Actual returned native speed: **43,484.58452036887 m/s**, status **ok**, actual saved index **20**, time **3.2195317385273e-8 s**.
- Explicit unit conversion: **156,544.50427332794 km/hour**.
- Assessment: **native_measurement_coverage=complete** for 1/1 named supported native SI measurements, no issues, execution_complete=true. Separately: interpretation_fidelity **not_verified**, independent_physics_correctness **not_evaluated**, educational_usefulness **not_evaluated**, textbook_answer_completeness **not_evaluated**.

An independent **same-author mathematical expression**, speed=sqrt(2qΔV/m), agrees within 1e-9 relative. It is not independent teacher/physics grading or a certified global integrator error bound.

**Critical negative:** deliberately doubling the authored electric field without changing the observation ID, unit, native quantity or saved context still returns *native coverage complete*, despite a physically inconsistent speed for the published givens. The assessment leaves interpretation fidelity not_verified. Structural completeness is therefore not source interpretation or independent physical correctness.

## Public answer-key observation (not blind adjudication)

NASA's sheet gives about **159,000 km/hour** for Problem 1; using its printed source givens directly yields **156,545 km/hour**, about 1.5% lower, plausibly reflecting coarse intermediate rounding. Do not tune the model or source to force exact agreement.

NASA's adjacent Problem 2 gives a force around **1.6e-13 N**, whereas the prescribed uniform field of 1300 V across 0.7 mm yields **qE ≈ 2.97e-13 N**. This is a *reference-versus-assumptions discrepancy requiring separate expert judgement*, not definitive independent certification that NASA's answer is wrong. Problem 2 force/acceleration do **not** count as native measurements answered by this one-request Problem 1 exercise.

## Reproduce from a qualified checkout

    python -m emfeeld.observations examples/nasa_ion_public_v0/packet.json --validate-only
    python verification/question_first_trial_v1.py assess examples/nasa_ion_public_v0 --packet examples/nasa_ion_public_v0/packet.json --output output/nasa-ion-public-replay-001

Both committed source and receipt must remain unmodified; all outputs must use fresh directories. Linux/Windows release CI will re-freeze the exact question into a fresh lock, re-execute the native packet, and archive original replay evidence; it will not retroactively replace the first local attempt.

**Nonclaims:** no independently unseen teacher question, authenticated original PDF bytes, separately withheld judge, proven interpretation fidelity or full textbook answer completeness, classroom usefulness, real ion thruster simulation, certified numerical accuracy or independent teacher endorsement. Issue #36 remains open.
