# Gauss-law 3D V2 — renderer-neutral desktop pilot

Tracks Issue #54. Development candidate, not independent acceptance or a release.
The V1 authored JSON and all physical functions in `gauss_lesson.py`, `fields.py`
and `integrals.py` are unchanged. No browser migration, server or new solver.

## Responsibilities

`gauss_lesson.measure` owns exact closed totals, signed cube-face integrals,
unadjusted sphere quadrature and boundary refusal. `gauss_presentation.py`
prepares geometry, SI probes/normals, sampled field vectors, E dot n, report and
sampling caution without importing PyVista or VTK. Its detached NumPy buffers
are backed by immutable bytes and its report is read-only. This is an internal
trusted-data boundary, not a new JSON authoring/security or evidence protocol.

The controller uses one `PresentationCache` keyed by the immutable physical
state, display sampling resolution and quadrature order. A different state or
sampling request creates a complete new result before committing the cache.
Camera orbit, resize, selected face, cutaway, prediction/reveal, active-charge
selection and move-target selection reuse the same prepared data. The PyVista
adapter constructs its own meshes from copies and cannot change those buffers.
It does coordinate/display transforms and glyph construction, not a Coulomb or
flux evaluation. `surface_mesh` remains a compatibility adapter.

Snapshots retain the original authored bytes separately from current physical
state, actual widgets/camera, current SI arrays and PNG, plus new face/preset
metadata. Saving a live unchanged state reuses its prepared physical report.
The headless numerical command remains usable without installing graphics.

## Geometry preservation and explicit difference

Cube geometry/probe ordering and arithmetic are retained from V1; face IDs use
cube-local +x,-x,+y,-y,+z,-z, including translated/rotated cubes. The selected
face is outlined on the existing closed surface; selecting or clipping it never
changes the integration domain. Field coloring is still **local E dot n**, not
integrated face flux. The face readout is taken from the unchanged physical report.

Sphere display triangles keep the same longitude/latitude connectivity as V1.
Their vertices now come from float64 analytic angles rather than PyVista/VTK's
float32 sphere generator. Thus sphere *display samples are not byte-identical*.
The native comparison test checks unit-point/probe differences below 5e-8 at
resolutions 4,6,12,40; this is a presentation-comparison bound, not a physics
acceptance tolerance. Probes are projected onto the exact analytic sphere, never
onto flat triangles for evaluating the field. The physical sphere quadrature
and exact total do not use this mesh and are unchanged. No pixel-equivalence
or all-GPU assertion is made.

## Student controls added

- `F` cycles no selection and the six cube-local faces. A sphere has no named
  cube faces; shape switching clears selection. Boundary states never display
  stale selected-face flux. `V` hides/reveals the selected value as well as totals.
- `1`, `2`, `3`, `4` select explicitly synthetic centered, off-center, exterior,
  and equal-and-opposite-inside teaching cases. They reuse the **initial authored
  surface** (center, size, orientation) and first signed charge, intentionally
  replacing the charge list. A zero first charge is refused rather than silently
  inventing a physical strength. Each case starts in prediction mode. Numerical
  answers are always recomputed by the unchanged engine, never encoded in presets.
- A physical edit clears the exact-preset label. `0` restores the initial authored
  configuration. Camera rotation and cutaway never imply an opening in the
  mathematical Gaussian surface. Charge moves select independent static states;
  they are not integrated particle motion or conductor redistribution.

All old controls and minimum supported window size 840 x 560 remain.
`--case center|offcenter|outside|zero_net` also selects a teaching configuration;
it does not change the meaning/version of the input JSON.

## Qualification

New pure-Python tests cover unchanged physical reports, actual field sampling,
immutable buffers, closed outward mesh topology, cache reuse/invalidation,
no-graphics import, undefined-boundary clearing/recovery and synthetic cases.
Real PyVista tests exercise actual keys/sliders, selected rotated-face geometry,
minimum-window text layout, live snapshot binding, and zero physics calls on
display-only events. `tools/qualify_gauss_v2.py` retains new screenshots and states.
Existing headless, original Gauss runtime and sampling-caution tests remain.

The guided questions in `GAUSS_V2_TRY_IT.md` are author-created conceptual checks,
not a held-out JEE score, original examination reproduction or human teaching
acceptance. One focused independent review is required on the new boundary and
controls before guarded integration, followed by fresh actual-main qualification.
