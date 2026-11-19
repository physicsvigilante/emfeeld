# JEE magnetostatics 3D V1 — single ideal infinite straight wire

Tracks Issue #60. **Candidate on a separate branch until source CI and a focused independent review pass.** This deliberately small magnetostatic lesson introduces the 3D right-hand rule and Ampère's circulation; it does not modify or extend the existing electrostatics/gravitational field/trajectory engine, and is not a time-dependent solver.

## Physical definition

A *single infinitely long, perfectly thin* wire carries a **steady prescribed signed current** \(I\) in the unit-axis direction \(\hat u\), passing through physical point \(r_0\). Define the perpendicular displacement \(\rho=(r-r_0)-[(r-r_0)\cdot\hat u]\hat u\). In vacuum, for nonzero resolved \(|\rho|\),

\[
\mathbf B(\mathbf r)=\frac{\mu_0 I}{2\pi}\frac{\hat u\times\boldsymbol\rho}{|\boldsymbol\rho|^2}\quad \text{(tesla)}.
\]

A right-handed orthonormal pair \(e_1,e_2\) spans a circle perpendicular to \(\hat u\): \(e_1\times e_2=\hat u\), \(\rho=R(e_1\cos\phi+e_2\sin\phi)\), and the positive loop tangent is \(-e_1\sin\phi+e_2\cos\phi\). The signed tangential field is \(\mu_0 I/(2\pi R)\), and exact Ampère circulation is

\[
\oint \mathbf B\cdot d\mathbf l=\mu_0 I\quad \text{(T m)}.
\]

The numerical lesson separately samples **actual SI B** at physical circular probes and forms the oriented tangent-weighted sum with real physical arc weights \(2\pi R/N\); it **does not normalize** that sum to Ampère's formula. Its value and the separately computed exact result are displayed side by side. The circle drawn in PyVista is a polygonal approximation, *not* the integration path used for physics. \(B\), \(I\), and circulation reverse sign consistently for reversed current. At fixed current, doubling radius halves \(|B|\) but keeps circulation the same. Zero current has zero field including at the axis.

The actual SI source is infinite. **The 4.4-radius wire segment, arrow lengths, and the default rendered loop radius are display-only choices**; the drawing normalizes the physical radius to one unit. Its green B arrows show **direction, not magnitude**, and have separate schematic lengths. No magnetic force, scalar electric potential, particle motion, induction, finite-segment end effects, wire thickness or permeability calculation is present. Do not infer a solenoid or linked-wire calculation from the diagram. These formulas assume magnetostatics in vacuum; there is no new general Maxwell solver.

## Numerical admission and refusals

JSON is strict and versioned (`lesson_version=1`, `lesson_type=ideal_infinite_straight_current_wire`), with exactly the seven declared fields, no duplicates, unknown fields, booleans masquerading as numbers, string numbers or nonfinite values. Signed current is zero or has \(10^{-6}\le |I|\le10^{4}\) A; loop radius \(10^{-3}\le R\le100\) m; loop samples must be an integer 12–192; origin magnitude components are within ±100 m; the input direction must be a finite resolved nonzero vector with component magnitudes ≤100 and norm between 1e-8 and 100 before normalization. These are finite-precision lesson limits, not fundamental restrictions on the wire law.

JSON floating tokens such as `1e-400`, which are mathematically nonzero but would silently underflow to float64 zero, are rejected **before** conversion. Field probes must be finite three-vectors with absolute coordinates ≤1e5 m. For nonzero I, a probe on or numerically unresolved near the ideal singular axis is refused using an explicit float64-coordinate-relative resolution indicator, **not** an arbitrary fixed metre softening. Nonrepresentable nonzero output is also refused. Physical charge, current and magnetic field must not be conflated; the module is separate from `fields.py` and does not add `kind='magnetic'` to existing electric/gravity scenes.

The sampled circulation is a floating-point approximation to the ideal integral; no universal roundoff tolerance is promised, especially for tiny R far from the represented origin. The actual exact analytic expression is presented independently, and tests compare the vector **norm** rather than pretend every ideally zero Cartesian component has relative precision. No numerical source/current cutoff silently changes the law.

## Architecture and use

- `src/emfeeld/wire_magnetism.py`: immutable typed physical state, strict JSON and analytic B/SI oriented circulation; no graphics imports.
- `src/emfeeld/wire_presentation.py`: detached, immutable physical probes, B vectors, tangents, arc weights, schematic drawing data; no PyVista/VTK imports.
- `src/emfeeld/wire_view.py`: PyVista 3D drawing, camera, keys, radius slider, reveal and saved real current-state snapshot; no magnetic equation in the renderer.

Run with **existing** compatible Python/NumPy/SciPy/PyVista environment:

```sh
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json --case 2 --snapshot NEW_IMAGE_DIRECTORY
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json --case 3 --headless NEW_REPORT_DIRECTORY
```

A fresh output is required; the public writer performs shared evidence protection before creating a directory, and its receipt records **original authored JSON bytes separately from current state**, source-code hashes, physical SI arrays, screenshot hash (when present), camera and full viewport/controls. Hidden numerical answers are still present in saved evidence; hiding is **pedagogical**, not an information-security boundary. The GUI uses only the previously computed renderer-neutral snapshot when rotating the camera, toggling reveal or redrawing without a physical edit. Changing radius or current computes a new physical state first and never mutates the previous prepared result.

The four cases (original radius, double radius, reversed current, zero current) are **author-created teaching examples**, not unseen examination problems. Read `docs/WIRE_V1_TRY_IT.md` for suggested predictions and limits. Validation is physics/source/render evidence, not a claim of teacher approval or human Windows mouse acceptance. Full prior physics-source implementations and archived studies remain byte unchanged.
