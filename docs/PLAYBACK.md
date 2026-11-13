# Sample-based motion playback — 2026-11-13

## Scope and status

Parent: `fa95d1c82947e944e1538455cd418eb6a79da5f9`, tree `cfe48046654937967857ae32f2e9e002b55a12f3`. Following the user's request to continue in chat, this bounded slice adds controls for replaying existing trajectories. It does not extend the physics. PR #1 remains draft and unmerged; continuing development is not treated as an instruction to merge. The chat-only author-verification decision remains in force; no independent review is claimed.

## Controls and numerical contract

Moving scenes start paused. Focus the viewer window, then use:

| Control | Action |
|---|---|
| Space | Play/pause; playing again after completion restarts from the beginning |
| Home | Return to the first sample and pause |
| Left / Right | Move back/forward one saved sample and pause |
| Time slider | Pause at drag start; select the nearest saved sample |

Playback stops at the final sample rather than wrapping. The default replay spans the entire simulated interval in approximately 12 wall-clock seconds. This is a display-time scale, not 12 seconds of physical evolution. The physical sample time is shown separately. Python callers can change `make_plotter(..., replay_seconds=12.0)` without changing scene data or solver settings.

The controller selects precomputed positions, never recalculates forces or trajectories, and never interpolates invented particle positions. Dropped or delayed render events may skip displayed samples: elapsed monotonic wall time, not timer-event count, controls the replay rate. Every selected position is still an actual saved sample. Manual stepping makes each saved sample inspectable.

Source geometry, field arrows, potential values, trajectory curves, SI units, sample arrays and axis bounds are unchanged. Static field-only scenes get no playback controller. Controllers are local to each plotter; closing the plotter destroys its active timer and removes its timer observer before graphics teardown. The plotter is still a PyVista Plotter subclass.

Implementation separates a graphics-free `PlaybackState` from the PyVista binding. Windowed playback requests a repeating 33 ms VTK timer. Offscreen PyVista uses a generic interactor without a native event loop; capture tests drive real VTK events with a controlled clock instead. This distinction is not hidden behind a simulated desktop pass.

## Executed evidence

Environment: Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, PyVista 0.48.4 and VTK 9.6.2. The six previously uploaded wheels were rechecked against their transfer manifest and installed offline into a container-local package directory. No user-machine installation, dependency-range change or new dependency was introduced.

A verified source copy was reconstructed from the earlier evidence bundle: 29 files matched their published parent Git blob IDs, checked against the live repository tree. Four other parent entries (workflow, gitignore and two historical documents) are inherited unchanged when publishing, not fabricated into a local Git checkout. Required historical documents were read through the connector/conversation. Historical validation and correction reports remain unchanged.

| Check | Result |
|---|---|
| Unchanged parent suite | 162 passed, no skips |
| Final cumulative suite, warnings as errors | **191 passed, no skips** |
| Original capture harness | **8 scenes, 14 frames passed** |
| Flat/nested composition captures | Geometry and PNG bytes still identical |
| Real native windowed timer smoke check | PASS on Linux Xvfb/X11 |
| Compilation of source/tests/viewer tests/tools | PASS |
| Motion preview captures | 61 real-render frames each for ideal Sun and electric sphere |

The 191 tests comprise 182 headless/configuration cases and nine real-viewer cases. The 29 added cases comprise 24 graphics-free clock tests and five real-viewer event tests. Existing assertions were retained; the presentation recorder gained only the key/render/widget methods needed by the new controls. No xfail, skip, or weaker physics tolerance was introduced.

The three moving examples were checked with real VTK key, slider and TimerEvent callbacks: play/pause/resume, scrub while playing, stepping, restart, completion and replay. Marker positions equal the saved numerical positions; potential samples and numerical trajectory arrays remain unchanged. Tests forbid a second trajectory calculation during playback. Axis bounds, labels, potential legends and physical time text are preserved. Separate windows advance independently, and close cleanup is idempotent. Static scenes have no timer controls.

The separate native smoke check used `vtkXOpenGLRenderWindow` and `vtkXRenderWindowInteractor` under Xvfb. It did not invoke TimerEvent manually: the final run received 28 native timer events, paused at sample 264, resumed to sample 1000, restarted, then closed while playing. Timer/observer cleanup passed. The earlier smoke run received 29 events and paused at sample 262; event counts are observations, not deterministic acceptance criteria. The smoke test explicitly selects a 1.2-second replay to bound its run; the viewer default remains 12 seconds.

The first preview's horizontal help line crowded the top axes. It was replaced by a left-side control block and recaptured. Midpoint Sun and electric-sphere frames were visually inspected after that adjustment. Preview arrows and ticks remain small, as in the accepted working direction. Raw initial/final captures and logs are retained in the chat evidence bundle. GIFs are assembled from real viewer frames and loop for convenient viewing; the application itself stops at the end.

## Reproduction

From a genuine source checkout with the existing `[dev,view]` extras:

```text
python -m pytest -q -W error tests viewer_tests
python -m compileall -q src tests viewer_tests tools
python tools/qualify_viewer.py --output output/viewer-qualification
python -m emfeeld view examples/ideal_sun.json
```

Optional native timer check on a working Linux display (Xvfb is test infrastructure, not an application dependency):

```text
xvfb-run -a python tools/check_native_playback.py --output output/native_timer.json
```

The chat bundle also includes the deterministic preview-capture script and a source-copy wrapper for the unchanged eight-scene capture harness. Neither invents a Git HEAD or claims a complete local clone.

## Limits and next decision

This establishes sample-based playback and native timer delivery in the recorded Linux environments. It is not Windows keyboard/mouse qualification, an independent review, a guarantee of exact wall-clock frame rate, or a test of every dependency version. Headless event delivery and virtual-display timers do not establish human desktop usability on Windows.

All existing physics restrictions remain, including rejection of shell/plane trajectories, no conductor polarization, no collision events, no backreaction and no electromagnetic radiation. Field lines, equipotential surfaces and visual integral explanations remain separate future work. Source formulas, dynamics, schema, examples, dependency declarations and license are unchanged.

Relevant upstream interfaces (API references, not validation evidence):
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.renderwindowinteractor.create_timer
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.renderwindowinteractor.add_observer
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_key_event
