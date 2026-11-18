# JEE 3D conductor cavity lesson V1 — draft

This opt-in lesson serves Issue #43 and the owner's **JEE-first, 3D-first** scope.
It is not a general conductor/PDE solver and does not modify `fields.py`, existing
scene/observation dispatch, particle integration, solver tolerances or old runs.
It is a new analytical boundary-condition adapter with a separate lesson schema.
Implementation and author tests do not constitute independent R2 acceptance.

## Exact supplied reference, actually inspected

The owner's `01_theory_elec.pdf` was read from the original GitHub source-snapshot
artifact 14398012911. Its original file SHA256 is
`dfed5a5cf241a365a2d94ebfeb73a9473aad66184d73af38be7fbfd81e6876ab`, Git blob
`e8bf45cb2bc8206be0681d5c5367d0943e8b6c95`, 140 PDF pages. Text extraction and
rendered pages were inspected, not inferred from the filename. Relevant source:

- PDF page 115 / printed **1.115**, *Conductor with Charge Inside a Cavity*: inner
  induced total -q, outer total Q+q, zero field and constant potential in metal.
- PDF page 117 / printed **1.117**, *Test Your Concepts-XI*, question 5: central
  point charge in a conducting shell with distinct inner/outer radii; question 7:
  off-centre positive charge at R/2 in a neutral **thin** spherical shell, asking
  for field-line sketches inside and outside.
- PDF pages 123–124 / printed **1.123–1.124**, *Method of Images*: auxiliary
  mathematical charges and the grounded-plane construction.

**Source versus this implementation:** the core Gauss-law lesson and the
centre/off-centre comparison follow these topics. The spherical-cavity image
formula and sampled surface density are separately derived analytical machinery,
not claimed to be printed on those pages. The default numerical values (R=1 m,
B=1.25 m, q=1 nC) are illustrative author choices. The thick-shell off-centre
view is an adaptation, not an exact numerical reproduction of question 7's thin
shell geometry. Question 5's central configuration is reached with offset zero.
No content or numerical answer in the PDF is silently rewritten, and no whole
chapter/corpus or blind independent question success is claimed.

External analytical background: Richard Fitzpatrick, [Method of images](https://farside.ph.utexas.edu/teaching/em/lectures/node64.html)
and Michael Fowler, [Image Method](https://galileoandeinstein.phys.virginia.edu/Elec_Mag/2022_Lectures/EM_08_Images.html).
These are mathematical implementation references, not a change to the student's
JEE-level prerequisite or evidence that the lesson was independently validated.

## Model, units and numerical domain

One **held fixed** point charge q at vector a in a spherical vacuum cavity of
radius R, concentric outer spherical radius B, ideal electrostatic conductor,
no exterior charges. Origin is the common sphere centre. There is no contact,
charge-transfer dynamics, arbitrary geometry, multiple charges or superposition
with other sources. Moving a control selects a new equilibrium, not time evolution.

Two mutually exclusive boundary conditions:

| Mode | Inner total | Outer total | Conductor potential |
|---|---|---|---|
| Isolated, prescribed net conductor Q | -q | Q+q | k(Q+q)/B |
| Grounded, no external charges | -q | 0 | 0 |

Grounding does not change the cavity field for a fixed q/a; it changes the
additive potential constant and exterior field. Metal always has E=0. The cavity
generally does **not**. A surface has distinct one-sided electric fields, so an
unqualified field probe exactly at a charged surface is refused. Potential is
continuous. The real point charge is singular; no softened charge is used.

V1 intentionally admits R in [1e-6, 1e3] metres, B/R in [1.01,5], |a|/R <= 0.9,
and each nonzero prescribed charge magnitude in [1e-18,1e-3] coulombs. Zero is
allowed. Probes have |coordinate| <= 1e6 R. These are a **bounded lesson/display
contract**, not a claim that the law fails beyond it. Booleans, string numbers,
duplicate/unknown JSON keys, nonfinite values, a charge on/through the wall and
simultaneous grounded+prescribed nonzero Q are rejected. A distance within
128 float64 eps R of q is numerically unresolved; a charged interface within
64 eps times the normalized radius is refused for a single-valued E probe.
No single fixed physical cutoff is used and no old field tolerance is changed.

## Exact analytical field; approximate drawing

For 0<|a|<R, the virtual image is q'=-q R/|a| at b=R²a/|a|². Its Coulomb field
plus the real charge's field is used **only inside the cavity**. The metal uses
E=0 and the exterior uses the central equivalent Q+q (or zero if grounded).
Never continue the image field into the metal/exterior: an image could lie there
but is not a physical charge or a physical singularity of the exterior solution.

Implementation uses normalized vectors y=x/R, v=a/R, t=|v| and
D=|t y - v_hat|. Cavity potential is
`kq/R * (1/|y-v| - 1/D) + V_conductor`; its negative gradient gives E. For a=0,
D=1 and the regular centred limit is evaluated without a huge image at infinity.
The surface density is
`-q/(4*pi*R²) * (1-t²)/|n-v|³` on unit radial n. It reverses sign with q,
becomes uniform at the centre and has near/far density ratio 27 at t=1/2.
The ratio is a **local density ratio**, not total hemisphere charge.

Actual density samples (not normalized values) color the inner and outer meshes.
Legend units are nC/m² with a symmetric automatic range; compare printed values,
not equal colors across different equilibria. Full angular surface quadrature
reports an **unrenormalized** numerical total and error against analytic -q.
The polar sampling axis follows a; results at orders 32/64 are retained. A coarse
mesh/integral is not an exact total and sharp near-wall peaks need refinement.

Field curves use bounded RK4 steps of the normalized field direction, seeded
near the real charge, and stop just inside the cavity wall. For negative q their
stored direction is reversed so arrows point toward q. They never enter metal;
separate exterior curves begin outside B. Seed spacing/count is illustrative,
not a numerical measurement of flux or an animation of moving particles. Step
limits are retained explicitly, not silently treated as completed field lines.

## 3D interaction

Requires the existing optional `[view]` dependencies; no added package dependency.

```sh
python -m emfeeld.cavity_lesson examples/lessons/conductor_cavity.json
python -m emfeeld.cavity_lesson examples/lessons/conductor_cavity.json --validate-only
python -m emfeeld.cavity_lesson examples/lessons/conductor_cavity.json --headless output/cavity-numbers-001
python -m emfeeld.cavity_lesson examples/lessons/conductor_cavity.json --snapshot output/cavity-view-001
```

Rotate/zoom the left 3D view. Four sliders change offset a/R, polar angle,
azimuth, and the isolated Q setting. Keyboard **G** switches grounding,
**N** reverses q, **C** toggles the cutaway and **L** toggles field curves (use
lowercase keys without Shift). The metal rim is a **display cut**, not a physical
opening: no loss of shielding or new rim charge is calculated. Markers are
schematic and coordinates displayed as x/R, y/R, z/R; physical quantities remain SI.
No physical image charge is drawn. Grounded mode ignores the stored isolated Q;
switching back restores that prescribed setting. This is not simulation of
connecting/disconnecting an earthing wire and retaining the discharged charge.

This shows only equilibria. Existing particle integration must not be attached
to the lesson and mislabelled as self-consistent conductor dynamics.

## Saved snapshots and qualification

Snapshot destinations must be fresh and outside old sealed evidence, question
locks and model stores. Shared `protect_saved_evidence` runs before writes or
renderer creation. A snapshot records current lesson state, optional original
input bytes separately, actual rendered camera/settings, PNG hash, field-line
arrays, quadrature errors, constants/environment and implementation hashes.
`integrity.json` seals successful output; failed attempts retain their inputs
and failure outcome. Saving a modified live controller records its **current**
state, never the original state with a different screenshot.

`tools/qualify_cavity_lesson.py` renders centred/off-centre, grounded, negative,
charged-isolated and rotated full-shell cases, tests actual VTK slider events,
field regions, line direction, camera/cutaway and source-bound snapshots. The additional
`cavity-lesson.yml` workflow retains these **new Linux lesson artifacts**. The
existing Linux/Windows release suite also executes the new real-viewer tests;
its historical artifact contract is unchanged. Headless tests compare independent
image formulas, field/potential gradients, normal surface limits, charge balance,
rotation covariance, mesh refinement, correct refusals and output protection.

An initial author quadrature test requested excessive accuracy from only 96
angular nodes at a/R=.9 and failed; the test now actually refines to 256 nodes
without relaxing its 2e-13 relative target or rescaling charge. Both first logs
are preserved outside the source. This is a sampling-resolution correction,
not a change to the analytical field or source question.

Pending: exact-head hosted CI, original archive audits, separate-context R2
review and real teacher/student Windows interaction. Automated render success
is not independent physics approval, human visual acceptance or pedagogical
usefulness. Issue #36 (unseen independent question) and #41 (human walkthrough)
remain separate. Do not merge this draft merely because its examples look right.
