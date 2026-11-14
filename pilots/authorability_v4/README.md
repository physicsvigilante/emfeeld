# emfeeld authorability v4 — solution-withheld, source-aware pilot

Engine frozen at `08571d366a0499d2110de0929d91db7d5caa6c7f`, preceding pilot-v3 addition `f077ebce5465c0857e6f29a29faaf7364b3da112`. The uploaded `01_emfields.pdf` is Git blob `6870cfb3c5bd33f9800eb851ad1fe4c6b4106787`. Question statements and diagrams were used, without consulting any worked solutions or answer key. **This is not a genuinely blind or independent LLM benchmark:** prior chat context, source docs and other examples were available to the same assistant.

**Seven new problem targets, eleven data-only executable packets, two intentionally unsupported controls.** All eleven packets succeeded at first native execution and neither packet nor engine required a post-run correction. The two controls returned unsupported-source validation errors. Five questions are direct uses of supported laws; NUM30 and NUM35 have expressly conditional physical interpretations.

## Cases

| Case | Printed page | Result |
|---|---|---|
| SC31 (4 choices plus 1 reference) | 1.164, PDF 24 | Only D has field **vector** exactly double the single-source field at R. A,C,D match the magnitude alone. |
| SC106 | 1.173, PDF 33 | Five positive charges at regular hexagon vertices, illustrative field at centre 9.170971210 N/C |
| SC121 | 1.175, PDF 35 | 400 V/m at 45 degrees; V_A-V_B = 2.82842712475 V |
| SC53 | 1.167, PDF 27 | Hollow sphere: R=.25m, V(R)-V(3R)=120V representative, E(3R)=80N/C |
| NUM35 (conditional) | 1.212, PDF 72 | Derived opposite charges ±15.118110236C, **point-charge approximation** force 2.054170184e16 N at 1cm |
| NUM30 (conditional) | 1.211, PDF 71 | Electron speed 2.515399860e7 m/s at outer radius .3m, time 9.679724876e-9s; valid analytic source equivalence **only in vacuum gap** |
| GRAV-TETRA (illustrative, not PDF) | — | Four fixed point masses, off-axis test mass; z=2.4m crossing t=0.950831175s |
| NUM41 control (unsupported) | 1.212, PDF 72 | Two moving, interacting charged spheres plus collision |
| NUM42 control (unsupported) | 1.212, PDF 72 | Electric and gravity forces simultaneously on one particle |

The Q31 magnitude-only same-author verifier error was **corrected after the first execution**, with both assessments preserved. This did not alter any authored packet or engine code. The NUM30 authored scene continues beyond the outer observation radius: only its first crossing is physically qualified; continuing the point-field animation beyond the actual outer conductor is not a valid collision model. NUM35 does not solve general conductor polarization.

## Verification and preservation

- First native execution: **11/11 supported-target packet successes**, **2/2 controls rejected**, zero packet corrections.
- Final separate mathematical checks: **43/43 passed** using symmetry, Coulomb/Gauss formulas, an independent regularized time quadrature for NUM30, and separately coded RK45 for the tetrahedral gravitational event.
- Current-engine bounded tests: **783 core + 10 historical-v2 live compatibility + 9 real-viewer + 41 new pilot = 843 passed**.
- Seven real offscreen PyVista frames for three scenes rendered and were inspected; existing viewer unchanged, no Windows user interaction qualified.
- No `src/emfeeld` files, old tests, libraries, license, older pilot, PDF, or `main` changes. Keep PR #1 draft/unmerged.

The **chat evidence bundle** contains the original byte-frozen authored packets, first-run JSON reports/logs, prospective protocol, input hashes, raw reference calculations and preserved verifier correction, runnable pytest tests, preview PNGs and verification scripts. The GitHub JSON packets in this commit have the **same scene/observation numerical data, but are reserialized**, not byte-identical to the originally tested files. Do not apply the chat bundle's raw-file hashes to these published reserializations. The evidence ZIP is accessible from the chat, not committed here.

Reproduce with `python -m emfeeld.observations pilots/authorability_v4/packets/num30_electron_gap.json --output output/v4-num30.json` (from a checkout with Python deps). The gravity case and other packets use the same command.

**Next:** measure problem-to-model interpretation quality with unseen source descriptions and explicit rejection rules, rather than treating observed conditional reductions or same-chat verification as independent reliability evidence.
