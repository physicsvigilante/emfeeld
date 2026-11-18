# JEE 3D Gauss-law lesson V1

The bounded physics core was independently reviewed and released through
PR #47 / Issue #46. The presentation follow-up described below is tracked by
Issue #48; its own PR/release state determines when those refinements ship.
This opt-in lesson is not a new native observation-packet request or conductor
solver. Automated graphics and technical review do not establish human Windows
operation or classroom effectiveness.

## Run

```sh
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json --validate-only
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json --headless output/gauss-numerics-001
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json --snapshot output/gauss-image-001
```

Use new output directories. Interactive/offscreen graphics use the existing
optional PyVista dependency; headless physics does not import it. The JSON
contains explicit SI positions, charges, surface dimensions and cube rotation.
The surface is **imaginary**, not matter, and carries no induced charge.

## Learn by changing one configuration at a time

Start with the charge at the cube centre. All six integrated face fluxes are
equal even though the local field and its normal component vary across a face.
Move the charge off-centre: the face values change, but the exact total remains
Q_enclosed / epsilon_0. Move it outside: positive and negative contributions
cancel, without making the local field zero. Switch to a sphere, compare the
sampled integral with the exact total, and refine without rescaling the samples.
An opposite-sign pair shows that zero total flux need not mean zero field.

Rotate the camera with the mouse. The first three sliders move the selected
charge; **M** switches those sliders to translating the surface while holding
charges fixed. Coordinates on these sliders are relative to the initial surface
centre, in units of its initial radius/half-side. The size slider changes the
surface radius/half-side relative to its initial size, not the charges.
Yaw and tilt orient a cube relative to its authored rotation; a sphere is
rotationally symmetric. SI values and the target are recorded separately.

Keys: **S** changes shape; **N** reverses the selected charge; **A** selects the
next authored charge; **D** explicitly replaces the charge list with a preset
pair (first charge plus an opposite charge), or returns to the first charge
alone. Up to three prescribed charges may be authored in JSON. **C** toggles a
visual cutaway; the mathematical surface remains closed. **V** hides/reveals
numeric answers for prediction. **R** cycles sphere quadrature orders
24, 48, 96, 192, then 24. **0** restores the initial physical configuration and
camera. None of these changes represents a trajectory or a charge-transfer
process in time.

## What each visual quantity means

Surface colors are signed local **E dot n in N/C**, sampled on the analytic
surface. They are not face-integral values. Cube probes lie on the plane of each
face; sphere probes are projected onto the analytic sphere, not evaluated at
inside-the-sphere triangle centroids. The colored display mesh itself is a
finite geometric approximation. Black arrows show outward normals; green
arrows show E direction. Arrow lengths are fixed display lengths, not field
magnitudes or calibrated flux. Source markers have schematic size.

The separate panel reports signed cube-face integrals in N m^2/C, their
unadjusted sum, and an independently classified Gauss-law total. For spheres it
reports the exact total, an unrenormalized sampled total, and sample-minus-exact
error. Local display resolution and quadrature order are distinct. Close to a
surface source the quadrature may be inaccurate; its error is not concealed or
converted into a correctness certificate. Cutaway and camera settings do not
change any integral.

## Analytical implementation and bounded domain

Only one to three held point charges and closed cubes/spheres are admitted.
Nonzero |q| is 1e-18..1e-3 C. Cube side is 1e-6..1e3 m; sphere radius is
1e-6..1e3 m. Each centre coordinate is bounded by 1e6 radii/half-sides, and
charge offsets by 1e8 radii/half-sides. Shape/size controls refuse configurations
outside the target shape's bounds rather than changing units or softening E.
Cube orientation must be a finite, right-handed orthonormal matrix; strings,
booleans, reflections and non-orthogonal matrices are rejected.

Boundary classification includes uncertainty from world-coordinate subtraction
and rotation, not just a fixed metre tolerance. A charge on a face, edge,
corner or sphere, or numerically unresolved against that surface, yields
`undefined_boundary`, with a null exact total. The viewer clears stale flux
colors/arrows. V1 also conservatively applies this geometry policy to a
zero-strength charge marker. No half-charge or vertex fraction is assigned.
Those textbook limiting constructions require a separately specified policy.

Cube faces use q Omega/(4 pi epsilon_0). Away from a face plane, each oriented
rectangle is split into two outward triangles. For rays a,b,c the triangle
formula is 2 atan2(det(a,b,c), |a||b||c| + a.b|c| + b.c|a| + c.a|b|).
For these fixed faces the determinant is evaluated as 4 times signed plane
separation in half-side units, avoiding cancellation between large rays.
Near a face plane the equivalent rectangular antiderivative is used:
sign(d) atan2(u v, |d| sqrt(d^2+u^2+v^2)), evaluated at its four corners with
alternating signs. This integrates d/(d^2+u^2+v^2)^(3/2) directly. The switch
is a numerical evaluation strategy, not a physical source cutoff. Coplanar
exterior faces have exactly zero flux. No face is adjusted to close the total.

The triangle formula is the separately selected implementation technique of
Van Oosterom and Strackee (1983), *The solid angle of a plane triangle*,
IEEE Transactions on Biomedical Engineering, BME-30, 125–126,
doi:10.1109/TBME.1983.325207. It is not attributed as an algorithm taught in the
owner's chapter. Sphere integration reuses `integrals.sphere_flux`; accepted
orders are bounded to 2..256 polar and 2..512 azimuth samples.

## Exact source mapping

Original `01_theory_elec.pdf`: SHA256
`dfed5a5cf241a365a2d94ebfeb73a9473aad66184d73af38be7fbfd81e6876ab`.
The original page text and diagrams were inspected, not just a search snippet.
**Illustration 47**, printed pages **1.60–1.61** (PDF pages 60–61), supplies the
selected problem: a square of edge 2l with charge +Q a perpendicular distance
l from its centre, followed by a cube of side 2l with that charge at its centre.
The square-face result is Q/(6 epsilon_0); the six-face total is Q/epsilon_0.
The example JSON chooses l=1 m and Q=1 nC for display; these numerical choices
are illustrative, not numeric givens quoted from the book. Illustration 46 on
page 1.60 is a different cuboid/nonuniform-field exercise, not the selected
point-charge example. Moving/exterior/dipole tasks are authored extensions,
not claimed reproductions of additional unseen textbook questions.

## Evidence and checks

Snapshots retain original input bytes separately from the current physical
state, numerical results, SI surface samples, current controls/camera, image
hash, implementation-module hashes, constants and dependency versions. A
boundary snapshot can finish executing while `flux_available` is false; it is
not a successful numeric answer. Late failures retain an incomplete outcome.
Writers use shared output-safety preflight and never overwrite sealed evidence.
Unkeyed hashes detect drift, not independent authorship or malicious resealing.

Focused author checks are in `tests/test_gauss_lesson*.py` and
`viewer_tests/test_gauss_runtime.py`. They include independently written
rectangular field quadrature, signs/closure, rigid motion/scale, far and near
geometry, invalid inputs, output safety, actual widget events, outward mesh
orientation, real arrow geometry and current-state snapshots.
`tools/qualify_gauss_lesson.py` retains eight actual production scenes.
Full existing release workflows remain unchanged; a separate Gauss-lesson
workflow collects source, tests and screenshots on PRs and main pushes.


## Sampling caution and supported window layout (Issue #48)

The sphere panel shows a prominent **SAMPLING CAUTION** when

`abs(sampled_total - exact_total) > 0.01 * sum(abs(q_i)) / epsilon_0`.

This 1% threshold is a **teaching attention rule**, not a solver tolerance,
rigorous error bound, or measurement acceptance test. The scale includes all
prescribed charges (inside and outside), so the comparison remains defined
when enclosed net charge is zero. All-zero charges give zero scale and no
warning; there is no division by net flux. Opposite-sign sampling errors can
cancel: **absence of a banner is not an accuracy certificate**. Local surface
samples can be poorly resolved even when the total discrepancy is small.

Exact total, sampled total and signed sample-minus-exact discrepancy remain
unchanged. Refinement can still leave a large discrepancy near the surface.
The warning is hidden during prediction, cleared for undefined boundary
configurations, and never applied to the analytic cube-face integrals.
No source distance cutoff, smoothing, rescaling or extra field solver is added.

The supported minimum render-window size is **840 x 560 pixels**, with
**1440 x 960** as the default. Text size adapts on real render-window resize;
resizing annotations does not recalculate flux or alter geometry or camera.
The scalar bar, directions inset and keyboard instructions have distinct
regions; a wider results panel and larger slider titles improve legibility.
Text/slider values are formatted for display, not full-precision input records;
near-surface 0.9999 and 1.0001 positions remain visibly distinct. The original
SI values remain in `lesson.json` and the current-state receipts.

Snapshots additionally record actual window size, annotation font settings and
the display-only caution criterion/visibility. Numerical physics, availability,
original input preservation and protected-output rules remain the same.
`tools/qualify_gauss_usability.py` captures six actual production scenes,
including near-inside/outside, zero enclosed net charge, boundary refusal and
an off-centre cube at reduced size. Offscreen checks are not manual Windows
acceptance. Windows below the stated minimum are not qualified for legibility.
