# Electric dipole in a uniform external field — JEE lesson V1

Issue #50. This is a bounded opt-in teaching adapter, not a native model-store
observation type, an inverse solver or rotational dynamics. The existing
electrostatic/gravity source and test-particle engines are unchanged.

## Run

```sh
python -m emfeeld.dipole_view examples/lessons/dipole_uniform.json
python -m emfeeld.dipole_view examples/lessons/dipole_uniform.json --snapshot output/dipole-001
python -m emfeeld.dipole_view examples/lessons/dipole_uniform.json --headless output/dipole-002
python -m emfeeld.dipole_view examples/lessons/dipole_uniform.json --snapshot output/dipole-small --window-size 840 560
```

Use a new output directory. Headless operation does not import PyVista.
Graphics use the already-declared optional viewer dependencies. No installation
on the owner's computer is made by this change.

## Physical model and meanings

Two held opposite charges +q and -q form a rigid pair in a prescribed spatially
uniform external electric field. Charge magnitude q is nonnegative; reversing
the dipole swaps the two locations. Position data are in metres, q in coulombs,
external E in N/C. The rod is a schematic constraint, not a charged conductor.

- p = q (r_positive - r_negative), from negative to positive, in C m.
- F_positive = q E; F_negative = -q E; net external force is zero.
- Torque about any origin is p cross E, in N m: a force couple.
- U_external = -p dot E, in J, with zero at perpendicular orientation.
  This is the orientation-dependent interaction with the external field.
  The constant mutual energy of the rigid charges is **not included**.
- At fixed q, separation and E, quasistatic external work is delta U_external;
  electric-field work is its negative. No angular speed or inertia is inferred.

These finite-pair formulas are exact for a uniform external field. There is no
far-field approximation, conductor redistribution, feedback, radiation, free
rotation or time integration. Mutual internal forces do not change the external
couple calculation. The existing `UniformField` supplies the external field.

Parallel and antiparallel are both zero-torque equilibria for nonzero p and E;
the first minimizes U and the second maximizes it. At zero q or zero E the
orientation has no preference and the angle between p and E is unavailable.
No zero-vector direction arrow is drawn. Small nonzero torque is not snapped
to zero or silently classified as an exact equilibrium.

## Bounded numerical domain

q is zero or 1e-30 through 1e-3 C, including the elementary-charge scale.
Separation is 1e-9 through 1e3 m, even for zero q. Position/origin coordinate
magnitudes are at most 1e6 m. Nonzero field magnitude is 1e-12 through 1e9 N/C.
Finite real numeric inputs only; booleans, strings, complex/nonfinite values,
duplicate keys, unknown keys and unsupported dynamics are refused.

The pair separation must exceed a conservative coordinate-subtraction resolution
indicator, `64*eps*(norm(r_positive)+norm(r_negative))`. A small pair at enormous
world coordinates is refused rather than rendered as overlapping charges.
Torque is evaluated from the separation before multiplying by q, avoiding
cancellation of large origin-dependent torque terms. Near cancellation of the
three-term analytic arithmetic, a standard-library exact-rational product-sum
fallback resolves the represented input numbers. A nonzero result below float64
range is explicitly refused, not reported as a successful zero.

Rotation-work eligibility requires identical q and E and separation agreement
within 256 float64 eps relative, to accommodate rounding of rigid rotations.
A changed constraint produces an unavailable/null work result, not a substituted
energy difference claimed as rotation work. These bounds are not an arbitrary-
scale error proof. The underlying field laws and existing tolerances are unchanged.

## Controls and display

The mouse rotates only the camera. Six sliders set dipole and E polar/azimuthal
directions independently, separation relative to its initial value, and E strength
relative to its initial value. A zero initial E uses a declared illustrative
1 N/C control reference; a zero initial q uses a 1 nC charge-control reference.

Keys: **N** swaps charges; **Q** cycles zero/original/double charge magnitude
(with the documented upper bound); **T** translates the pair; **O** changes the
torque origin; **1/2/3** select parallel/perpendicular/antiparallel to nonzero E;
**V** predicts/reveals; **B** freezes the current work reference; **0** resets.
There is no preferred-orientation preset at zero field. Changing E, q or length
invalidates the previous rotation-work comparison until a suitable reference is
chosen. Original authored input bytes are never replaced by the work reference.

The diagram is recentered and scaled using `(world-center)/separation` so tiny
and large valid pairs remain inspectable. The exact transform is recorded.
Force arrows start at the actual charge locations under this transform.
All vector glyph lengths use **separate schematic scales**, not a common
magnitude scale across C m, N/C, N and N m. Purple torque is an axial vector;
the plane/curved cue uses its right-hand sense, not a solved angular velocity.
No origin marker is drawn when that origin lies outside the declared view radius;
its SI coordinates and visibility remain in the receipt.

Prediction shows the charge geometry and prescribed field but hides derived
arrows and numerical answers; the saved internal calculation remains available.
Supported window sizes start at 840x560 pixels; default is 1440x960.
Native resize changes annotation fonts only, not the camera or physical state.
Offscreen rendering is not manual Windows or all-DPI acceptance.

## Actual source mapping

The original committed `01_theory_elec.pdf`, SHA256
`dfed5a5cf241a365a2d94ebfeb73a9473aad66184d73af38be7fbfd81e6876ab`,
was opened and PDF page 48 / printed 1.48 visually inspected. Illustration 35
specifies +e at (1,2,1), -e at (0,1,0), E=(2,3,0). Its symbolic results are
p=e(1,1,1) and torque=e(-3,2,1). The coordinate/field SI interpretation is
explicitly adopted here; those units are not printed beside all original givens.
The example chooses q=1 nC as an **illustrative value for the positive parameter
e**, not a textbook numerical given or a claim that e means 1 nC universally.
A separate test uses `scipy.constants.elementary_charge` to check small charges.

The same page's orientation-energy derivation motivates U=-p dot E;
Illustration 36 motivates delta-U work. The rotating-rod exercise below is
outside this static V1. The book is a visible, non-blind reference; this does
not satisfy the held-out teacher trial in Issue36. No book diagrams/prose are
copied into the application.

Additional primary reference: MIT 8.02T Coulomb's Law, sections 2.8–2.8.1,
https://ocw.mit.edu/courses/8-02t-electricity-and-magnetism-spring-2005/c31cd03c1b74a450ec131921f5625f0a_chap2coulomb_law.pdf .
Rendering API reference: https://docs.pyvista.org/api/utilities/_autosummary/pyvista.arrow .

## Evidence, qualification and scope

Snapshot output retains immutable current physical state, original authored bytes,
work-reference state, physical arrays, displayed transform/glyph/control/camera
data, actual screenshot hash, dependency versions and all package-module hashes.
Shared output-safety preflight protects existing evidence and descendants.
Late failures retain incomplete, unsealed outcomes. Hashes detect drift, not
independent authorship or hostile resealing.

`tests/test_dipole_lesson.py` uses separately written endpoint-force torques,
potential differences, rotations, small-charge and cancellation challenges,
energy gradients/work signs, zero cases and schema refusals.
`tests/test_dipole_io.py` checks bytes, current state, unavailable angles/work,
output protection and failures. `viewer_tests/test_dipole_runtime.py` executes
real widgets, geometry, resize, camera and snapshot checks.
`tools/qualify_dipole_lesson.py` retains ten actual production scenes; the
dedicated workflow also preserves original source and tests.

Author checks are not independent R2 review. Keep the feature draft/unmerged
until exact-head independent physics/graphics review and all premerge gates.
Guarded integration and new actual-main qualification remain separate.
No teacher usefulness, unseen-JEE success or free-rotation capability is claimed.
