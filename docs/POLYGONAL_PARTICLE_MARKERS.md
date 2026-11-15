# Polygonal particle markers — implementation candidate

Parent source: a84f13aea6f7d2081b43a8eae00835924e4b7d25, tree
3aa8d681e79c9fd47695f95e75e1f5500ecb1817. This is an approved implementation
candidate, not merge acceptance or a claim of completed Windows qualification.

## Observed failure and approved correction

The supplied E1 Windows report identifies enabled magenta single-point actors at
correct saved coordinates, with only one unrelated magenta pixel in each normal
or decluttered capture. A separate polygonal sphere at the saved midpoint is
visible (218 strong-magenta pixels). Decluttering did not fix the point marker.
This supports avoiding that point-rendering path; it does not identify a unique
low-level VTK/GPU cause. Original screenshots and reports remain unchanged.

## Display contract

Only src/emfeeld/viewer.py changes in production. Each moving particle uses a
magenta, unlit polygonal sphere with 24 azimuthal and 24 polar samples, instead
of a sphere-rendered vertex. Mesh geometry is local to the origin, radius 1;
actor scale is 0.025 times the largest authored viewing span and actor position
is exactly the selected saved float64 position. The mesh is not incrementally
translated. Surface representation is explicit; the point-sprite path is not used.

The radius is display-only, independent of charge and mass, not a collision or
material size. Unlike the prior 28-pixel marker, its screen size changes with
camera zoom and depth. This is a deliberate presentation-contract change.
Actor bounds are excluded from automatic framing; authored axes/camera policy,
black paths, field arrows, potential sampling/opacity/references and source
geometry remain unchanged. Source point markers are outside this fix.

Playback selects the same saved samples. Slider, keyboard and timer callbacks
only change actor position; no integration or interpolation is introduced.
Different particles retain their own particle_N actors and recorded trajectory
association. All are magenta: additional identity colours/labels are not added.

## Prospective verification and preserved history

Presentation-specific tests/tools now inspect the polygon mesh and its actor
transform instead of asserting a one-point dataset or 28-pixel point size.
Existing numerical tolerances, pixel thresholds (80 locally projected magenta
pixels), playback semantics and historical frozen tests are not weakened.
Prior test files and results remain recoverable from the pinned parent and
original evidence. The new E1/G1 scene fixtures copy the sealed baseline physical
inputs and bounds; they are not new first-attempt authoring or new physics.

New headless checks cover local-unit geometry and exact positioning at spans
1e-9, 1 and 1e11, and every E1/G1 baseline sample without reintegration.
New real-PyVista checks cover both cases in isometric/top views, normal and
decluttered captures, actor identity, array/axis preservation, and actual VTK
key/timer/slider events. These are not human Windows interaction tests.

## Executed in this implementation session

- 1,118 headless tests passed, warnings treated as errors.
- 18 historical behavioral tests passed; the one historical all-file freeze
  guard remains unchanged and explicitly deselected on current code.
- The exact eight sealed diagnostic runs loaded successfully. Across twelve
  recorded trajectories, all 1,212 saved actor positions matched exactly using
  the recording backend. All original run files remained byte-identical.
- Only viewer.py differs among the production Python modules. No solver,
  physical data, source laws, energy settings, dependency range or schema changed.
- Full native PyVista collection was attempted and failed because PyVista is
  absent. Package retrieval was unavailable. No real-render or new Windows pass
  is claimed for this candidate; it is intentionally not silently skipped.

The full-suite environment was corrected to provide an explicit PYTHONPATH to
subprocess tests. Earlier interrupted logs and a missing-module test failure are
retained. Two early test-harness defects (decimal float equality and an incomplete
recording backend missing add_points) were corrected without changing production
physics or tolerances. They are not first-pass successes.

## Remaining acceptance

Use the isolated preview package to reopen the preserved E1/G1 native runs on the
user's existing Windows graphics environment. It uses this production viewer, not
a diagnostic fallback. Capture projected pixels and native interaction evidence,
and obtain human confirmation that the particles remain visible during playback.
Fresh native-render regression qualification remains required before merge.
The candidate has not been published to GitHub or merged in this session.

Visibility under every camera, extreme zoom, occlusion or coincident projection
is not guaranteed. Pixel counts are supporting evidence, not educational acceptance.
No broader viewer redesign or new physical capability is part of this correction.

## Interface references (not qualification evidence)

- https://docs.pyvista.org/api/utilities/_autosummary/pyvista.sphere
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.prop3d.position
- https://docs.pyvista.org/api/plotting/_autosummary/pyvista.actor.use_bounds
