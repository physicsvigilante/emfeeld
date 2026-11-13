# Rest-launch turning qualification — 2026-11-13

## Identity and approved scope

Parent: `c6b5299261dee12bb09be70ae040ec4057cbc17d`, tree `b6c52d6093a7cfe7ba95847520b748c664c8f98f`. The user approved a bounded policy for later turning observations from a genuine rest launch. This implements an explicit opt-in policy, not a source extension, autonomous benchmark, global closest-approach solver or merge. PR #1 remains draft and unmerged under the chat-only author-verification policy. No independent review is claimed.

The new `rest_turning_events.py` adapter is selected only by `initial_policy="exclude_rest_launch"` on a radial-turning request. The shared core gains a time-dependent predicate hook; the observation parser/dispatcher admits the explicit policy. Existing source laws, original integrator, saved/plane/radial/default-turning adapters, viewer/playback and dependencies are unchanged.

## Numerical policy

For d=x-c, initial distance r0>0 and exactly zero initial velocity, the event is h=d.v/(r0*t) for t>0 and h(0)=initial radial acceleration. The latter is its continuous limit along the trajectory and must be resolved/nonzero. At positive distance and time h=r*vr/(r0*t), so its later roots and directions match those of radial velocity. No artificial velocity, warm-up segment, finite exclusion interval, changed time origin or retry is introduced.

A defined-field passage through the imaginary observation centre can precede a later maximum because the numerator is nonsingular there. A detected root at the centre remains an explicit ambiguous result, not a smooth radial minimum. Physical source singularities are not regularized. Initial transverse-only/zero/unresolved radial acceleration and any nonzero initial velocity are rejected. The default policy remains unchanged, including its rejection of all initial radial stationarity.

## Executed results

| Check | Result |
|---|---|
| Pinned parent baseline | **744 passed**: 697 core/pilot-v1, 9 viewer, 38 frozen-pilot-v2 |
| New rest-launch tests | **86 passed** |
| Added live replay tests for unchanged pilot-v2 inputs | **10 passed** |
| Current-engine cumulative behavioural suite | **802 passed, no skips**, warnings treated as errors: 783 core/pilot-v1 + 10 live v2 + 9 viewer |
| Actual CLI JSON round trips | **9 packets / 21 requests** |
| Accepted new event states | **8** |
| Other successful measurements | **5 static potentials, 1 saved initial speed** |
| Explicit no-event outcomes | **2** |
| Deliberate local failures | **5**: 1 centre-root ambiguity, 3 initial-condition errors, 1 physical source-domain error |
| Prior observation report objects | **47/47 exactly identical**: 11 static, 9 saved, 8 plane, 9 radial, 10 default-turning |
| Further step-cap sweep | **16/16 accepted and checked against separate reference expressions** |
| Original authorability pilot-v1, strict mode | **11 PASS / 1 PARTIAL / 0 FAIL / 0 ERROR**, expected exit 1 |
| Compilation and preservation | PASS |

### Historical freeze is not a live behavioural test

Pilot-v2 froze *every pre-existing file*. Its original 38-test suite passed on the verified pinned parent before edits. That exact all-file hash assertion intentionally does **not** pass on a modified engine, and was not weakened, redirected or rewritten. The pilot files, input hashes and historical outcomes remain unchanged. The 802 count is the live engine suite, not a claim that all 744 historical tests execute unchanged against edited source. Ten new generic replay tests use the old packets and their existing assessor/reference data against the live API; all preserve their declared outcomes, including both unsupported controls. Reproduce the frozen suite on its historical commit; use the separate live tests for current compatibility.

## Representative native results

| Authored case | Result |
|---|---|
| SC-28 exact old scene, opt-in observation, original 40 s horizon | `no_event`; its later maximum is outside the horizon |
| SC-28 exact sources/initial state, explicitly extended 70 s horizon | Maximum at **54.6402783877122 s**; distance **1.732050807568884 m**, position `(0,-1.732050807568884,0)` m, speed approximately zero |
| Same SC-28 setup, request minimum instead | `ambiguous_event` at the observation centre; not counted or silently skipped |
| Two massive spheres plus uniform gravity, rest launch, two masses | First minimum at approximately **pi s**, distance **1 m**; first later maximum at **2*pi s**, distance **3 m** |
| Electric rest launch from an initial distance minimum | Later maximum at approximately **pi s**, distance **3 m** |
| Uniform electric field; x=-2+t^2/2, y=1 | Later minimum at approximately **2 s**, distance **1 m**, speed **2 m/s**: not a stop |

All examples are explicit numerical instances or adaptations, not new givens from a textbook or new gravitational-corpus coverage. SC-28's historical L01 is untouched. Its extra later-maximum request is not the original midpoint question, and the 70 s scene is explicitly not claimed as byte-identical reuse. Only the horizon changes; initial position, exact zero velocity and sources remain identical. The unchanged legacy packet still returns its original `initial_condition_error`.

For SC-28, a separate energy quadrature removes the release-point square-root singularity by y=A*cos(theta). The later maximum time is twice the centre-passage time, giving **54.640278387712094 s**. Reference times/positions for other cases come from constant acceleration or harmonic motion, not native trajectory output. Two different test masses in the gravitational composition give identical motion with mass-scaled energies. These reference expressions were authored by the same assistant, not an independent judge.

The sweep uses duration/20, /40, /80 and /400 for four representative examples, with the adapter's second-pass step halving/tolerance tightening. Sixteen accepted states matched reference tolerances. SC-28 time uses 1e-5 s absolute reference tolerance, with 1e-7 for other reference state components; the final manifest explicitly distinguishes those rather than applying the time tolerance to position. Earlier candidate outputs and the stricter final comparisons are retained. No existing acceptance tolerance was relaxed.

## Safeguards and limitations

Tests verify exact initial-state preservation in both native solves, time interval beginning at zero, no t_eval/frame-root substitution, zero-time predicate limit, no near-rest coercion, minimum/maximum/either, arbitrary centres/rotations, electric q/m versus gravitational coupling, local failure isolation, unchanged input objects, cache keys and separate legacy caches. Synthetic bad refinements and known solver failures return no accepted state; unexpected programming exceptions still propagate. No additional searches are made to turn a failed refinement into success.

Initial eligibility is conservative. This does not support nonzero-speed apsidal starts, equilibrium launches, vanishing initial radial acceleration or arbitrary degenerate extrema. A positive-time candidate indistinguishable from launch at the authored time resolution is rejected, not silently bypassed. No global minimum, minimum launch speed or force softening is implemented.

Native sign-change detection can miss multiple roots within a step. Two-pass agreement does not prove mathematical first occurrence or absence. `no_event` is a numerical outcome, not an absence proof. Tiny/large scales and coordinate cancellation remain float64 limitations. The earlier missed small-sphere crossing diagnostic, sphere-penetration convergence rejection and SC-158 singular-surface flux limitation remain historical evidence, not new passes.

## Execution records and preservation

Linux / CPython 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / pytest 9.0.2. The existing nine real-viewer tests passed with PyVista 0.48.4 and VTK 9.6.2. The six earlier uploaded wheel transfer hashes were rechecked; installation was offline in a container-local directory. No user-machine change, new dependency, license change, screenshot qualification or Windows interaction claim.

Before implementation, 27 of 35 new tests failed because the capability was absent; 8 invalid-input/default-policy checks passed. The initial implementation passed all 35; extended coverage reached 86. Two combined command batches hit the execution limit; complete checks were rerun separately without modifying physics or tolerances. Their incomplete logs remain. A report-collection helper initially assumed all historical manifests used the same array key; only that helper was corrected to read the two existing formats. Its failed script/log are retained.

All 153 reconstructed parent files plus four inherited Git entries reproduce the live pinned parent tree. This is a verified source copy, not a complete clone. Four existing files change: `event_core.py`, `observations.py`, and the two live observation documents. Sixteen files are added: the rest adapter, two test modules, three documents and nine example packets plus their manifest. The other 149 reconstructed parent files and four inherited entries are unchanged. All old tests, examples, pilot files and validation reports are retained. The original 34-file pilot-v1 freeze guard still passes. The main branch, source PDF and license are untouched.

Publication is bound to the tested file hashes and inherited parent entries before the branch advances. The chat bundle contains source copies, protocol, first failing tests, complete and interrupted logs, native CLI outputs, reference preparation, final sweep and exact legacy comparisons. No independent-review pass is asserted.

## Reproduction

```text
python -m pytest -q -W error tests --ignore=tests/test_authorability_v2_compatibility.py pilots/authorability_v1/test_pilot.py
python -m pytest -q -W error tests/test_authorability_v2_compatibility.py
python -m pytest -q -W error viewer_tests
python -m emfeeld.observations examples/rest_turning/sc28_later_maximum.json --output output/later-turn.json
python -m emfeeld.observations examples/rest_turning/sc28_original_horizon.json --output output/short-horizon.json
python -m emfeeld.observations examples/rest_turning/sc28_centre_rejection.json --output output/centre-rejection.json
```

The final command intentionally exits 1. The short-horizon command exits 0 while retaining `no_event`: CLI success does not mean a maximum was found. Source-only execution requires `PYTHONPATH=src`. The frozen pilot-v2 suite belongs on its pinned snapshot; it is not rerooted or hash-updated for this candidate. New authoring may reuse the opt-in policy without changing engine code. PR #1 remains draft and unmerged.
