# Three.js renderer proof of concept — draft, not released

This is a **second rendering adapter**, built on PR52's renderer-neutral snapshot.
It has no field law, force calculation or trajectory integrator. Three.js is pinned
to 0.180.0. This browser-only dependency is not added to the Python application.

```sh
python -m pip install -e .
npm install --prefix web/three_preview --ignore-scripts --no-audit --no-fund
python tools/export_browser_preview.py --output output/browser-demo
python -m http.server 8000 --bind 127.0.0.1 --directory output/browser-demo
```

Open http://127.0.0.1:8000 locally. The generated folder contains the small required
Three.js runtime subset and its license, not a CDN link. Nothing is deployed and
no simulation data is sent to a remote service. Installation needs npm/PyPI network
access; after export, viewing needs only the local HTTP server, not the internet.

Three existing scenes exercise electric superposition, saved gravitational orbits,
and finite visual patches of infinite line/plane sources. The exporter calls the
existing engine once. The page verifies each JSON against its export SHA256 and
validates the supported data shape/units; it is a bounded demonstration, not a
hostile-input sandbox or universal LLM schema validator. Unrecognized geometry
fails visibly; explicitly undrawn sources remain disclosed.

Drag/touch orbits the camera; the slider and play button select **saved samples**.
Replay lasts 12 display seconds and is not a physical animation-speed claim.
There is no browser interpolation of trajectories or re-integration. Changing the
physics requires a new Python export; there are no browser charge/force editors.

All physical data remains in SI. Display coordinates are `(world-origin)/scale`
with the origin at the authored bounds center and scale equal to the largest span.
This keeps astronomical positions usable in WebGL without changing saved numbers.
Magenta marker size is schematic; gray equal-length arrows depict sampled field
**directions**, not field magnitude or calibrated flux. Black curves are particle
trajectories, not field lines. Infinite sources are finite display patches, not
boundaries. Potential colors interpolate precomputed scalars for display only;
any cell touching JSON null is omitted, never set to zero. The color range has
physical units and is not comparable across independently autoscaled scenes.

Tests: `npm test --prefix web/three_preview` exercises the rendering-only helpers.
`tools/qualify_browser_preview.py` executes actual Chromium WebGL, checks saved
marker positions and source immutability after slider/replay/camera events, and
retains PNGs. Test-only Playwright 1.57.0 is separate from runtime requirements.
The CI artifact preserves source, dependency lock, actual results and a runnable
folder. Failure logs remain failures. This is author automation, not independent
review, human Windows testing or pixel equivalence to PyVista.

This draft targets `main` after the renderer-neutral PR52 integration; the distinct
dipole PR51 and renderer-neutral releases retain their separate actual-main gates.
The browser proof must receive a focused independent physical-display and real-
WebGL review, fresh merged-preview CI and its own integration checks before any
production release. No specialized Gauss, conductor-cavity or dipole viewer is
migrated, and no existing Python physics or general PyVista file is modified.


## Corrected browser-admission boundary (PR53 R2-01 through R2-03)

The browser now requires the exported V1 meaning roles (including shape-specific
source roles, potential, marker and annotation roles), nonempty unique IDs within
each list, SI timeline units, literal Boolean display flags, normalized source
line/plane directions, and matching physical-field array shapes. Unknown or absent
required meaning metadata is refused, not inferred or rewritten. This validates
the consumed snapshot contract, not the physical correctness of arbitrary data.

The browser has an explicitly bounded **display domain**, not a new physics limit:
ordered bounds must have finite positive binary64 spans; the midpoint is computed
as `lo + (hi-lo)/2`, avoiding same-sign sum overflow. Transformed source centers,
all saved trajectory points, potential vertices and arrow origins must be finite,
within +/-1e6 display units, and must not turn a nonzero offset into binary32 zero.
Transformed radii and line/plane spans must be in [1e-6, 1e3]; arrow lengths must
be in [1e-3, 1e3] to avoid Three.js ArrowHelper's built-in minimum shaft silently
stretching them. Lengths are fractions of the largest authored bounds span.
Unrepresentable ranges/underflow are refused before scene construction; no
clamping of physical data or resampling occurs. These are numerical rendering
limits, not a guarantee that every object is inside the camera or pixel-visible.
Signed extreme potential color ranges use overflow-safe display-only ratios.

Only the adapter's displayed text for `playback_help` is replaced by the actual
browser button/slider instructions. Original annotation and snapshot bytes are
unchanged. Refusal clears scene actors, stale physical readouts and controls;
a later valid selection can recover, including after an initially invalid scene.

The Chromium qualifier supplies 31 altered JSON payloads with matching test
checksums to exercise validation rather than only checksum failure. It checks
visible errors, zero actor construction, empty stale readouts and disabled
controls, plus 14 real scene-selection/replay recovery paths. The original
three-scene controls, marker/origin transforms, screenshots and payload-immutability
checks remain. Hosted author automation is not reviewer-owned browser acceptance;
independent review and actual-main qualification remain separate gates.


### Review-02 follow-up: preserve Float32 primitive geometry

Individual finite coordinates are insufficient: distinct binary64 points can
become the same Float32 buffer vertex. Before any scene actor is constructed,
validation now checks each **physically nonzero consecutive trajectory segment**
and both rendered endpoints of a truncated line source using `Math.fround`, the
same conversion as the renderer's Float32 buffers. Exact repeated physical saved
positions remain valid, including stationary samples and paths that return to a
previous point. A physically distinct pair lost during binary64 translation is
also rejected. No original positions are rounded in place, dropped or resampled.

Each actually emitted potential triangle must have **nonzero area after Float32
conversion**. Three distinct but collinear Float32 vertices are also refused, as
are already-degenerate rendered triangles. Null-cell holes emit no triangles and
are not falsely tested as surfaces. This is a primitive nondegeneracy condition,
not a claim of exact Float32 metric fidelity or guaranteed pixel visibility.

Regressions retain review-02's exact in-bounds 61-sample path and nonzero triangle,
separate each failure to avoid masking, and exercise a far-translated path, line
source endpoint collapse, and three-distinct-vertices area loss. Genuine Chromium
checks matched-checksum refusals, zero new construction, stale-readout clearing,
and both invalid-startup recovery and running-replay -> refusal -> valid replay
for all six Float32 fixtures. Historical review-01/review-02 failures remain;
new author tests do not replace focused independent acceptance.
