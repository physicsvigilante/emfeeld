# Authorability v5 — source-withheld question cohort

**Candidate added without modifying the engine.** Frozen source commit: `08571d366a0499d2110de0929d91db7d5caa6c7f`; all 16 modules were verified by Git blob SHA. The task cohort includes seven previously untested PDF questions (five fully native; two partially supported) and two unsupported textbook tasks, represented by eight runnable JSON packets and three rejection controls.

The eight runnable packets passed on their first native execution, without packet edits. Three controls were rejected with exit code 2. Final separately expressed same-author checks: **39/39**; the initial reference judge had **38/39**, and its cancellation-to-zero tolerance was corrected with a floating-point-scale bound. All **865 current behavioral and pilot tests** passed in bounded batches. Five offscreen PyVista frames rendered using the existing viewer.

| Question | Book page | Task assessment |
|---|---|---|
| SC38 | 1.165 | Full: potential difference unchanged after giving outer shell -3Q |
| Numerical 20 | 1.210 | Full: centre potential for equal-density shells, about 8.98755 V |
| JEE Main January 2019 Q16 | 1.215 | Full: vector E=(6291.286,-2696.266,0) N/C, textbook option A with rounded k |
| JEE Main 2018 Q28 | 1.217 | Full: shell B potential; illustrative 56.47045 V |
| SC60 | 1.168 | Full: released particle kinetic energy; illustrative 0.02 J |
| Multiple Correct 25 | 1.187 | Partial: signed restoring-force probes and two small-amplitude motions, not native symbolic SHM classification |
| SC43 | 1.166 | Partial: author derived x=.08m, native field checked it; no inverse engine solver |
| JEE Main 2018 Q29 | 1.217 | Unsupported: square-patch flux observation |
| SC68 | 1.169 | Unsupported: mixed qE plus gravity |

**Scope:** This was held out from earlier authorability *packet cohorts* and source solutions/answer keys were not consulted. It is **NOT a genuinely blind independent LLM benchmark**—prior chat context remained available, and the same assistant authored source models and separate mathematical references. The success count measures this specific selected cohort only. Symbolic questions use labelled representative values; multiple scenes/observation requests do not equal independent problem trials. Historical model and test evidence remains intact. The PR must stay draft and unmerged.

**Source/packet identity:** All GitHub JSON packets have the same numerical source and requested-observation parameters as the tested chat-local originals but have been **reserialized**, not byte-identically published. Exact initial packets, hashes, the first-run CLI output JSON, failed initial reference check, corrected final check, scripts, raw logs and PyVista PNGs are in the accompanying ChatGPT evidence ZIP. Do not apply the original first-attempt hashes to these reserialized files.

Run from an installed checkout: `python -m emfeeld.observations pilots/authorability_v5/packets/main19_16_vector.json --output output/vector.json`

Limitations retained: the engine does not automatically find zero-field locations, prove SHM, integrate an arbitrary square patch flux, or combine electric and gravitational forces within one scene. No Windows desktop qualification, independent reviewer or mathematical event-completeness claim.
