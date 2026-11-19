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
