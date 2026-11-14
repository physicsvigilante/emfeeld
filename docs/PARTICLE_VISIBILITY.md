# Native particle visibility

## Purpose and scope

The user reported a black trajectory with no distinguishable moving particle in
the two-sphere teaching lesson. A large magenta-marker helper made the motion
visible on their Windows Conda installation. This candidate puts that distinction
in the native viewer, without requiring a helper or changing a physical model.
Parent main: `3948852d9c041adbdb7c8bd45537f25936641080`. Keep the correction branch
unmerged until explicit acceptance. This is a display correction, not new physics.

## Display contract

- Every moving test particle has a magenta, unlit, sphere-rendered point marker,
  28 screen pixels across rather than the old black 14-pixel marker. Its centre is
  the exact saved sample. Its size is schematic, not a physical radius; its colour
  does not encode charge sign, mass, speed or field strength.
- Black trajectory curves remain the full calculated paths, not field lines.
  A compact on-screen key explains both. The physical sample time, paused/playing/
  finished status, Space/Home/arrow keys and time slider remain unchanged.
- In scenes containing particles, the potential display slice uses opacity 0.35
  rather than 0.7. The 0.7 slice hid an inclined gravitational particle behind it
  in the first colour-only correction. Static field-only slices retain 0.7.
  This plane is a sampling surface, not a material obstacle. Samples, potential
  references, colour limits, source geometry and forces do not change.
- Named actors `particle_N` and `trajectory_N` are presentation handles only,
  not new physical IDs. Multi-particle scenes get one marker per saved trajectory.
- Camera framing, authored SI bounds, playback clocks and nearest-sample selection
  remain unchanged. No interpolation, coordinate displacement or new integration
  occurs during recorded playback. No physical marker radius enters any equation.

This applies through ordinary `emfeeld view`, study previews, and native recorded
`emfeeld model view`/`apply --view`, since they use the same viewer. Existing saved
runs remain usable: physics code and their arrays are unchanged. The helper is not
needed after installation of this candidate. No old run or user's installation is
automatically modified.

## Demonstration and checks

```text
python -m emfeeld view examples/opposite_spheres_visibility.json
python tools/qualify_particle_visibility.py --output output/visibility-001
python -m pytest -q -W error tests
python -m pytest -q -W error viewer_tests
```

The added example is the existing lesson's original physical scene: fixed prescribed
uniform spheres at x=-1 and +1 m, radius 0.25 m, charges +2 and -2 nC; a +1 pC,
1e-11 kg test charge released from rest at x=-0.30 m for 0.45 s with 451 samples.
It is illustrative, not conducting-sphere polarization, collision or radiation
physics. It does not use the problematic exact-zero-energy midpoint release.
The usual Home/Space controls start, pause or restart motion. Camera rotation only
changes presentation. Static scenes receive no invented moving markers or controls.

New real-render tests inspect actual magenta pixels near projected particle centres
at start, middle and end with the potential slice and black path present. They also
check exact sample positions, unchanged coordinate bounds and saved numerical arrays,
and forbid reintegration. Both isometric and top-down electric views and two inclined/
planar gravitational trajectories are exercised. The native capture command records
six PNGs with positions, times and hashes for separate visual inspection.

## Completed local qualification

- 1,067 headless tests passed, 18 historical behavioral tests passed, and 29 real
  PyVista tests passed: **1,114 behavioral cases**, warnings treated as errors.
- Six cases are new relative to the 1,108 baseline: one recording-backend test,
  one automatically collected scene-example test, and four real-render cases.
- The single historical all-file freeze assertion remains explicitly deselected
  and unchanged for its original snapshot. No numerical tolerance was relaxed.
- Original v6 replay: 10 packets / 58 checks passed. Discovery replay: 2 packets /
  36 checks passed. Source/tests/tools compilation and six new PNG captures passed.
- The archived lesson was also reopened using the actual native model-view CLI;
  its existing stored data and identities were not rewritten or recalculated.

Environment: Linux, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2,
PyVista 0.48.4 and VTK 9.6.2 with software EGL. The six previously supplied wheels
matched their transfer manifest and were installed only in a container-local target.
Direct clone failed DNS; the earlier exact source archive plus qualified changes
reconstructed the runtime. Source, tests, viewer_tests, examples, tools, verification,
pilots and CI subtree hashes matched live main before editing. Main's three design
Markdown additions are inherited, not claimed to be locally reconstructed.

Retained failure history: the initial new test filenames collided during collection;
renaming the new runtime file fixed the harness. Four new checks failed against the
parent. Increasing colour/size alone then failed the far-side Sun-particle pixel check.
Reducing only moving-scene slice opacity fixed that case without changing the pixel
threshold. An initial annotation overlapped axis labels; the final key uses shorter
lines. Earlier logs and pictures are retained in the chat evidence, not called passes.
Fresh Linux/Windows CI must be reported only after it completes for this candidate.

## Limits and next issue

This is same-author verification, not independent review. The tested views do not
prove visibility under every camera, opaque occlusion, extreme zoom, high-DPI setting
or coincident projected particle position. Markers can overlap; all use magenta.
The slice still tints geometry behind it. Read numerical values/colour-bar ranges,
not blended pixel colour as a precise potential measurement. Separate window scales
are not automatically comparable. The user's successful helper test does not qualify
human Windows interaction with this new native candidate.

Only `viewer.py` changes in production. Field laws, trajectories, energy diagnostics,
observations, revision store, schemas, playback and dependencies are unchanged.
**The zero-initial-energy diagnostic issue remains unresolved and is a separate
next task.** This change does not permit previously failed verification to render.

Upstream interface references (not execution evidence):
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_mesh
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_points
