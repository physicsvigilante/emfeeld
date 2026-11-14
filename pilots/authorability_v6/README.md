# Question-only authorability pilot v6

**Frozen engine:** `08571d3`. Ten **new first-attempt scene-and-observation JSON packets** represent seven previously unused PDF questions. They all executed successfully without post-run packet edits. Three question types were correctly declared unsupported. There were no modifications to source laws, numerical integrator, viewer, dependencies or historical tests.

## First-attempt and task-level scoring

- **10/10** runnable packets executed on first attempt. **35/35** post-freeze, same-author analytical checks passed.
- **7/7** supported question interpretations produced verified numerical forward simulations. **0/7** original generic/symbolic/inverse problem answers were natively solved without LLM-side algebra/interpretation; the engine was used as a numerical verifier.
- **3/3** unsupported questions were explicitly rejected rather than silently approximated.
- Historical core/pilot-v1 **783**, live pilot-v2 compatibility **10**, existing real-PyVista viewer **9**, and new benchmark **18** tests: **820 passed, no skips**.
- Four event step-cap checks for the line-charge motion agreed to far below 1e-8 seconds.
- Initial reference-verifier indexing exception was corrected after the first run. Both versions and all logs are in the accompanying chat evidence archive. **No authored packet was edited after its first execution.**

**Problem results:** SC9 field towards missing vertex; SC17 surface offset R/3; Numerical Q10 approximately 11.633656 cm (12 cm rounded); Numerical Q18 Q=-33 nC; JEE Advanced 2014 Q4 point/line/plane field changes by 4/2/1 at half radius; 2013 Q6 touching-sphere density ratios 4 and -32/25; JEE Main 2019 Q5 speed proportional to sqrt(log(r/r0)), numerical sample v=0.499187m/s, event t=1.788769s.

### Reproduce

```sh
python -m emfeeld.observations pilots/authorability_v6/first_attempt/NUM18-THREED-EX.json --output output/num18.json
python -m emfeeld.observations pilots/authorability_v6/first_attempt/MAIN19-Q5-LINE-OUTWARD.json --output output/line-motion.json
```

The 10 JSON packets use data-only source configurations and observation requests, with no embedded expected values. The exact locally tested initial packets, frozen SHA256 locks, separate scorer code, original error, native JSON reports, tests, and two PyVista screenshots are in the **chat evidence ZIP**. **GitHub versions are reserialized numerical equivalents, not byte-for-byte identical to the initial frozen packets; they have not been independently rerun from GitHub bytes.**

### Limits and integrity

Questions were fresh relative to prior study cohorts; source solutions/answer key were not read. However the same assistant prepared questions, authored the models and implemented the checker inside the ongoing chat with access to prior context. **Not a genuinely blind or independent LLM benchmark**, not an autonomous authoring success probability, and not native symbolic/inverse support. A future independent evaluation needs a fresh model context and separately prepared hidden references. No Windows UI qualification. Keep PR #1 draft and unmerged.