# General viewer renderer-neutral data — V1

## Reason and deliberately narrow scope

`src/emfeeld/visualization.py` is the single small bridge from a **general**
`Scene` to plain NumPy/data-class presentation data. It neither imports PyVista
nor VTK. `src/emfeeld/viewer.py` renders that data with the **unchanged** PyVista
scene styling, actors, camera and `PlaybackController` contract. The public
`make_plotter(scene, ..., recorded=...)` and `viewer.sample_values` entry points
remain available; no existing scene JSON or physics/solver code changes.

```
Strict authored scene -> existing physics model + saved/integrated trajectories
                                  |
                                  v
                   visualization.build_visualization(scene)
                   VisualizationData (SI, read-only sample arrays)
                                  |
                 +----------------+----------------+
                 |                                 |
          viewer.render_pyvista(data)      future renderer adapter(data)
          existing VTK UI/timer             (not implemented in V1)
```

The authoring boundary remains `scene_from_dict` / existing model-revision APIs.
`VisualizationData.to_dict()` is a **versioned presentation snapshot**, not a
new solver configuration, executable scene-authoring language, sealed evidence
contract or native observation packet. No new Three.js implementation is shipped.

## Reusable data components

- `Units`: physical position/time/field/potential units, **N/C and V** for
  electric scenes; **m/s² and J/kg** for gravity. No mixing of those potentials.
- `SourceGeometry`: typed point/sphere/shell/line/plane or invisible uniform
  source. Retains physical strengths and their units where applicable. A
  sphere/shell radius is physical; point markers are **schematic**, infinite
  lines/planes appear only as **truncated display primitives**, and uniform
  fields have no material source shape. Unknown source visuals are warned and
  omitted, never silently substituted for a different physical source.
- `PotentialGrid`: actual model potential values and physical XY-slice probe
  coordinates, using VTK's documented x-fastest/Fortran structured-grid order.
  The translucent plane is a *sample display*, not a physical material surface.
  `DomainError` samples remain NaN in Python; portable JSON converts them to
  **null**, never zero or an interpolated value.
- `FieldSamples`: all actual sampled field vectors plus a distinct collection
  of equal-length, schematic **direction-only arrows** derived from valid
  nonzero samples. These arrows are **not calibrated flux or field lines**.
- `TrajectoryVisual`: immutable snapshots of saved physical path samples,
  explicitly **not field lines**; the magenta marker's radius is a schematic
  drawing size, never the particle's physical radius or charge sign.
- `Annotation`: renderer-neutral pedagogical labels and source caveats.
- `VisualizationFrame`: time and particle positions at one existing saved
  index. `data.frame(i)` does no interpolation, resimulation or integration.
  `PlaybackState` and its VTK timers remain renderer-specific UI behavior.

The NumPy arrays in the data classes are detached and read-only; a renderer
must not modify underlying model/recorded arrays. `to_dict()` returns JSON-
compatible objects with a `visualization_version` marker and real/null sample
values; `json.dumps(data.to_dict(), allow_nan=False)` is supported. Snapshot
creation is intentionally eager and small-scene oriented. It is **not** a
streaming protocol or a promise of graphics performance for huge datasets.

## Adding a second renderer later

A future browser adapter can consume `build_visualization(scene)` data, or a
server-authored `data.to_dict()` result, mapping geometry primitives, SI vector
samples, labels and saved animation frames to its own scene graph. It should
**not** import `viewer.py`, call VTK/PyVista, reinterpret field-sample arrow
lengths as physical magnitudes, infer particle trajectories from field lines,
or silently zero null samples. Browser transport, performance/LOD, input
security and interactive controls would require their own tests and versioned
contract; there is no Three.js implementation here.

## Preservation tests

`tests/test_visualization_data.py` tests SI types, source semantics, exact
model-sample equality and x-fastest ordering, JSON null for undefined probes,
source composition and immutability of recorded paths. `tests/test_viewer_presentation.py`
retains the original monkeypatchable sampler and UI contract.
`viewer_tests/test_visualization_runtime.py` checks real StructuredGrid order,
no physics/trajectory calls after the data has been constructed, and live
PyVista playback. All historical general-viewer graphics qualifications remain
in force. A one-time local read-only comparison of `tools/qualify_viewer.py`
against original actual-main PR49 viewer artifact `14429981956` verified all
**17 PNG hashes and nine scene geometry signatures were byte-for-byte equal**
with the exact source tree `4da6b80f53d78b2394c8516b9463e442fffb50fe`.
This local comparison is author validation, not independent scientific review,
new Windows desktop operation or automatic release approval.

## Exclusions

The specialized Gauss-law, conductor-cavity and dipole lessons are **not**
refactored here. Their existing source, qualification methods and physics
contracts remain byte-identical. The general renderer-neutral layer is not
yet claimed to cover those lesson-specific widgets or physical quantities.
