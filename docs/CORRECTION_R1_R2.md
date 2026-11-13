# R1/R2 correction candidate — 2026-11-13

## Identity, scope and review status

Parent: `ded83f5a03cb4c06302f627590f17fc578c21201`, tree `ab655163ac57b035262bdc139c7cf10ba9a6ab55`. This corrects the two findings recorded on PR #1; it does not add physical sources, collision handling, or new viewer features. The analogous shell boundary policy was examined and made consistent with R1.

**Author-run verification, not independent review. Keep the PR draft and unmerged.** A separate reviewer and the real Windows/PyVista desktop check remain required. No reviewer agent was available through the connected tools in this pass; no independent approval is inferred from a second self-check. No PyVista install, launch, screenshot, slider interaction, or Windows operation was performed.

## R1: numerical geometry contract

Ideal line axes are singular; plane and shell fields have undefined values at their sheets. Equality-to-zero checks are insufficient after direction normalization, projections, and translated-coordinate arithmetic. Classification now raises `DomainError` for an exact boundary **or a location whose separation/side is numerically unresolved**. Such a rejection does not assert that an off-boundary point is mathematically singular. Continuous plane/shell potentials remain available. Zero-strength sources remain zero.

The filter is componentwise and scale-aware. Let `eps = np.finfo(float).eps` and `gamma(n) = n*eps/(1-n*eps)`. Using eps rather than half-eps is deliberately conservative. With observation point p, centre o, and d=p-o, the coordinate allowance is `e_d = gamma(2) (abs(p)+abs(o))`. This includes conservative coordinate representation/subtraction uncertainty; it can reject distinguishable but poorly resolved offsets near large translated coordinates.

For a stored line direction a, use `b = cross(d,a)`, `rho = norm(b)/norm(a)`, and `d_perp = cross(a,b)/dot(a,a)`. This avoids subtracting almost equal axial projections and preserves the analytic line geometry. Define C(u,v) componentwise as the absolute product sums in a cross product, e.g. `C_x = u_y*v_z + u_z*v_y`. The line allowance is

```text
e_b = gamma(16) C(abs(d),abs(a)) + C(e_d,abs(a))
e_rho = norm(e_b)/norm(a) + gamma(4)*rho
```

Both line field and potential reject `rho <= e_rho`. For a plane normal n, signed distance `s = dot(d,n)` rejects field evaluation when

```text
abs(s) <= gamma(16)*sum(abs(d*n)) + sum(e_d*abs(n)).
```

For a shell, `r=norm(d)` rejects field evaluation when

```text
abs(r-R) <= norm(e_d) + gamma(8)*(r+R).
```

Operation budgets allow for normalization, dot/cross products, norms and subtraction. Nonfinite classification intermediates are also rejected. These are conservative floating-point filters, **not an adaptive exact-predicate implementation or a certification for arbitrary exponents, underflow, overflow, or close-encounter trajectories**. The existing finite-range limitations remain. The constants are dimensionless operation budgets, not a fixed length in metres. There is no `max(1 metre, scale)` floor, force clipping, softening, or replacement of an undefined field by zero.

Accepted positions use the ideal analytic formulas. Samples rejected by the filter continue through the existing viewer sampler as NaN holes, preserving valid neighbors. Large tangential coordinates do not by themselves reject tiny but resolved offsets from a coordinate-aligned plane/line. Recentring/rescaling authored geometry may improve numerical resolution; changing the displayed arrow density does not.

References for floating-point background (not proof of this implementation): NumPy machine limits, https://numpy.org/doc/stable/reference/generated/numpy.finfo.html ; Shewchuk's discussion of geometric predicate roundoff, https://www.cs.cmu.edu/~quake/robust.html . No code from those references was copied.

## R2: composition-preserving geometry traversal

`emfeeld.fields.iter_sources` recursively yields leaves of a `Superposition` in authored order. It retains duplicate references; grouping is not deduplication. The viewer uses this iterator instead of only inspecting immediate children. The numerical composition and trajectory solver are unchanged.

All existing primitive geometry adapters are retained. A uniform field intentionally has no source shape and is identified as such in the display note. An unknown custom source type emits a `RuntimeWarning` and an on-screen missing-geometry note; its field and potential are not dropped. The tests compare geometry calls and parameters for equivalent flat and nested arrangements containing all built-in source types and a repeated sphere.

## Executed evidence

Environment: Linux, CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2. PyVista is absent. Direct git cloning failed because the container could not resolve github.com. All 17 original runtime/package/example/test files were reconstructed through the connector/evidence bundle and verified against their original Git blob SHAs before editing. The original physics contract was separately blob-verified. Non-runtime files not changed by this correction are inherited from the parent Git tree, not fabricated locally.

| Check | Result |
|---|---|
| Original candidate: full original suite | 84 passed, no skips |
| Original candidate: unchanged 17 review diagnostics | 11 failed, 6 passed (expected reproduction of R1/R2) |
| Corrected candidate: cumulative suite | 153 passed, no skips |
| Corrected candidate: original 17 review diagnostics alone | 17 passed, no skips |
| Corrected candidate: compilation of src and tests | PASS |
| Corrected candidate: explicit ideal-Sun CLI run and NPZ check | PASS |
| Genuine independent review | NOT RUN |
| Real PyVista/Windows/desktop/visual qualification | NOT RUN |

The 153 cases comprise 84 unchanged original tests, 17 unchanged diagnostic cases retained as `tests/test_review_regressions.py`, 49 new boundary-policy cases, and 3 new composition/geometry cases. No xfail, skip, or relaxed original acceptance criterion was introduced. `docs/VALIDATION.md` remains the unchanged historical report; this report adds new evidence rather than rewriting history.

Coverage includes both physical domains, oblique axes/planes, translations, scales from 2^-30 to 2^30, both resolved sides, near-boundary uncertainty, zero-strength exceptions, empty/vectorized batches, finite-difference gradients, downstream error propagation, source order/multiplicity, geometry parameters and unknown-geometry disclosure. Additional small-length controls show no fixed physical exclusion radius/slab.

The viewer tests use a limited recording backend, not actual PyVista/VTK. A passing spy test establishes dispatch behavior only, not rendering, visibility, camera framing or desktop correctness. The full suite executes all five original JSON examples and tests NPZ export without pickle.

## Reproduction and next review gate

From the corrected checkout, with the existing dependencies available:

```text
python -m pytest -q
python -m pytest -q tests/test_review_regressions.py
python -m compileall -q src tests
python -m emfeeld run examples/ideal_sun.json --output output/ideal_sun.npz
```

For an uninstalled source checkout, set `PYTHONPATH=src` before the last command. In PowerShell: `$env:PYTHONPATH = (Join-Path (Get-Location) 'src')`.

A genuinely separate reviewer should examine the whole current candidate, prioritizing the R1/R2 delta: challenge the uncertainty budgets and scope claims; distinguish mathematical boundaries from conservative rejections; verify valid formulas, vectorization, zero strengths and source multiplicity; inspect the cumulative tests and confirm no original acceptance was weakened. Report exact candidate identity, commands, failures, skips and unrun checks. Do not label a backend spy as visual evidence. Do not merge or expand physics scope as part of that review. After independent approval, qualify the real Windows viewer and inspect the displayed source geometry, potential scale, arrows, trajectories and time slider.
