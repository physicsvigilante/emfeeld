# Real PyVista viewer qualification — 2026-11-13

## Candidate, decision and scope

Parent candidate: `bebaafbef412fd1d3f94bf8c185570ec1927a607`, tree `fea1d3344f9739ab277f25e1869c1cc9c081e3a3`. The live branch had advanced beyond `3280371`; its newer qualification tool and presentation changes were retained. This report describes the bounded viewer correction in the commit containing this document, not an unchanged-parent pass.

The user approved chat-only author verification plus explicit user acceptance in `CHAT_WORKFLOW_DECISION.md`. **No independent review, Windows installation, mouse-drag test, or merge is claimed.** Keep PR #1 draft and unmerged pending acceptance of these previews. No physics scope, source formulas, integrator, scene schema, original examples, dependency ranges, or license changed.

## Runtime and file identity

Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, **PyVista 0.48.4 and VTK 9.6.2**. Rendering used `vtkEGLRenderWindow`, Mesa 25.0.7-2, llvmpipe (LLVM 19.1.7, 256 bits). A native X-display warning preceded successful EGL rendering; it is retained in the logs, not called a failed render.

The uploaded ZIP supplied six pinned universal wheels. All six SHA256 hashes matched its manifest; wheel names/versions and the 31-distribution runtime dependency closure were checked. Installation was offline into a dedicated container virtual environment. Its local `.pth` explicitly inherited the already-installed scientific stack because the base interpreter itself is a virtual environment. No libraries or settings on the user's computer were changed. The manifest match is a transfer-integrity check, not a newly fetched independent PyPI provenance check.

Direct cloning remained unavailable. All 24 runtime, example, test, configuration, and relevant report files used for the baseline were reconstructed from the connector and earlier evidence archives, with Git blob hashes checked against the pinned live tree. README and AGENTS were separately verified before editing. This was a verified source copy, not a complete Git clone. The local runner called the repository's real `cases()` and `capture()` functions; it did not fabricate a git HEAD for the upstream `main()` wrapper.

## Reproduced problems and corrections

1. **Qualification harness API error.** `set(plot.scalar_bars)` raised `KeyError: 0` before capture in all eight cases. PyVista's named mapping is now read using `.keys()`. These were eight manifestations of one harness bug, not eight broken physical models.
2. **Slider changed the displayed axes.** Replacing the named time-text actor made PyVista reset cube-axis bounds and label formatting to the glyph bounds. For the Sun example, authored limits of +/-299195741400 m became +/-299600248832 m and compact labels became long integers. Additional real checks failed in all three moving scenes before correction. The viewer now updates the existing text actor's `input` in place. Real tests assert unchanged authored bounds, labels, marker coordinates, and time text at every checked sample.
3. **Crowded presentation.** The camera now reserves margins and the potential legend is vertical at the right. Title size and axis-text settings were adjusted. Only the potential owns a scalar legend. Source/particle coordinates and numerical arrays were not rescaled or clipped to improve appearance.

The original failed runs and intermediate layout captures are retained in the accompanying evidence bundle. Three recording-backend helpers were adapted for the camera/text API; no physics assertions were relaxed. No xfail or skip was introduced.

## Executed results

| Check | Result |
|---|---|
| Unchanged parent numerical/presentation suite | 156 passed |
| Original real-capture harness | 8 failures: named scalar-bar iteration error |
| Corrected harness, before added axis guards | 8 scenes passed |
| Added axis guards, before text-update correction | 3 moving scenes failed; 5 static scenes passed |
| Final cumulative suite, including real viewer tests | **162 passed, no skips**, warnings treated as errors |
| Final real capture run | **8 scenes, 14 frames passed** |
| Flat/nested grouping | Same mapper geometry and byte-identical PNG captures |
| Compilation of source, tests, viewer tests and tools | PASS |
| CLI `view ... --screenshot` | PASS; Sun PNG identical to the qualification's initial frame |
| Extra tilted-source camera angle | Rendered and inspected; the line is not viewed end-on |

The 162 cases comprise 158 headless/configuration tests and four explicitly requested real-PyVista cases. The normal test discovery remains `tests/`; `viewer_tests/` requires the optional viewer dependency and graphics runtime. Missing dependencies fail rather than silently skipping those requested tests.

Three moving scenes were checked at start, midpoint, and end using actual VTK `EndInteractionEvent` calls. All 12 particle-marker comparisons matched the precomputed numerical samples exactly. Axes, time text, legend names, finite/nonfinite sample handling, image dimensions, and nonblank output were checked. Events are programmatic, not simulated Windows mouse drags.

## Author visual inspection

Inspected the eight scene overview, all three motion sequences, full-size Sun/shell/composition images, and a rotated tilted-line/plane view. Source shapes, transparent shell, potential slices, both Sun trajectories, particle positions, and separated legends are present. Grouping does not hide or deduplicate sources. Boundary masking was checked numerically; a projected screenshot alone cannot certify every undefined sample.

**Result: acceptable initial offscreen previews for this recorded environment and these scenes.** This is not polished UI acceptance. Arrows and tick labels remain small, transparent objects overlap in projection, and both test planets use the same marker style. These are presentation limitations, not new physics claims. User acceptance remains outstanding.

## Evidence and reproduction

`viewer_evidence_20261113.json` records the executed environment, summary results, tested source hashes, and screenshot hashes. The chat evidence ZIP additionally contains raw reports, failed logs, before/after images, the verified baseline source copy, corrected files, and the source-copy runner. Screenshots are delivered with that ZIP, not embedded into this repository report.

From a genuine checkout with the existing `[dev,view]` extras and graphics backend:

```text
python -m pytest -q -W error tests viewer_tests
python -m compileall -q src tests viewer_tests tools
python tools/qualify_viewer.py --output output/viewer-qualification
python -m emfeeld view examples/ideal_sun.json --screenshot output/ideal_sun.png
```

The capture tool deliberately leaves its automatic report's visual-inspection status pending; the inspection judgment is recorded separately above. Historical `VALIDATION.md`, `CORRECTION_R1_R2.md`, and earlier failures remain unchanged. Windows desktop interaction, arbitrary camera/parameter combinations, long-duration orbit qualification, autoplay, field lines, equipotential surfaces, and animated integral explanations are not established by this pass. Shell/plane trajectories remain rejected.
