# Rectangular current loop in a uniform magnetic field — analytic 3D V1 candidate

**Development candidate for [Issue #66](https://github.com/physicsvigilante/emfeeld/issues/66); not yet independently reviewed, merged or released.** This introduces a genuinely 3D JEE magnetism situation without adding a field solver. Existing static wire, circular-loop, Gauss, capacitor and electrostatics/gravity modules are unchanged.

## Physical model and exact SI meaning

One ideal rigid, planar, **one-turn rectangular current filament**, width a, height b, centre c, carrying signed steady DC current I. The external field is **spatially uniform and prescribed**, not computed from the current loop. The field has a permanent reference direction `d` (unit) and a signed scalar strength, `B=field_strength_T*d`. This makes reversing B explicit.

A right-handed orthonormal plane `(e1,e2,u)` is constructed, with width along e1, height along e2, **positive geometric normal** `u=e1×e2`, and positive current circulating through corners `-e1-e2 → +e1-e2 → +e1+e2 → -e1+e2`. The normal's **tilt angle** is in degrees relative to **the fixed +d reference**, not necessarily the signed physical B or signed magnetic moment if current reverses.

```text
A = a*b                                            [m²]
magnetic moment m = I*A*u                         [A m²]
torque tau = m × B                                 [N m]
orientation potential U = -m · B                  [J]
F on each edge = I * (edge displacement) × B      [N]
sum F_i = 0
sum (r_midpoint_i-c) × F_i = tau
```

For positive I and positive signed external B, `U=-IAB cos(theta)`, `|tau|=IAB|sin(theta)|`. Thus the **parallel normal** at theta=0 has **zero torque and lower energy**, the **perpendicular normal** at theta=90 has maximum |torque| and U=0, and the **antiparallel normal** at theta=180 has **zero torque and higher energy**. Reversing current or B changes signs of U and tau appropriately: the lower-energy alignment switches. This is not an instruction to animate physical rotation; all controls select distinct **static hypothetical orientations**. Potential is defined with zero at perpendicular orientation.

At exactly zero current, magnetic moment, forces and torque vanish; an external nonzero B can still be drawn. At exactly zero external B, torque, forces and orientation energy vanish, while signed magnetic moment may remain. Even at nonzero I and B, an individual edge parallel to B feels no magnetic force. The net force on the closed loop is always zero in this strictly uniform field, although **torque may not be**.

All physical quantities use SI; only forces on prescribed current segments are evaluated. No dynamics, moving loop, Lorentz test-particle trajectories, induced emf, self-field, field lines, materials, heat or battery work are calculated. Normal, current, external field, magnetic moment, force and torque *display arrows are direction-only schematic*, never tesla/ampere/N·m-proportional physical lengths. The view draws one representative filament; it does not depict a multi-turn winding.

### Angle and torque representability

The binary64 model evaluates acute and obtuse tilts using their distance in degrees from the nearer aligned endpoint. A positive tilt whose radian value falls below the smallest normal binary64 number is rejected during state construction. For other tilts, the orientation calculation requires the transverse part of the normal to survive addition in world coordinates to relative precision `1e-10`. At nonzero current and field, an interior angle must also yield a nonzero torque scale, and both the moment cross product and the sum of the segment torques must agree with the signed analytic torque vector to that relative precision. Unresolved configurations raise a domain error. These checks preserve exact zero torque at 0° and 180°.

The torque check divides the stored SI vectors and reported magnitude by the sine of the tilt before comparing them to the analytic reference. This keeps the comparison tolerance representable even for subnormal SI outputs. Orientation energy uses the authored angle with its signed degree offset from 90° so that perpendicular energy is exactly zero and its two neighboring angles retain opposite signs for nonzero current and field.

## How to launch in your already installed Conda environment

From the repository root, after this feature is released and the branch installed in the *same* existing `emfeeld[view]` environment:

```sh
python -m emfeeld.rectangular_loop_view examples/lessons/rectangular_loop_uniform_field.json --case 1
```

The `--case 1` launch starts in prediction mode before revealing physical values. Mouse orbit/zoom is independent of the physics.

**Current controls:** keys `1` positive normal parallel to reference direction, `2` perpendicular, `3` antiparallel, `4` reverse signed I at 90°, `5` zero I, `6` zero external B; each preset hides values. `V` reveals/hides, `N` reverses current, `B` reverses signed external field, `F` shows/hides the four force glyphs, and `0` resets. The right pane contains a **0–180° tilt slider** and **0–2× initial signed-field magnitude** slider. Moving the slider after reversing B preserves the reversed field sign. If the authored baseline field is zero, the magnitude-ratio slider has no nonzero reference and `0` resets; use an authored nonzero baseline for demonstrations.

**Color conventions**: dark/copper wire is a schematic one-turn filament; orange is signed current; green is prescribed external B; blue is **fixed positive geometric normal** (not automatically the moment), pink is signed magnetic moment, purple is torque, and cyan is the force on each segment. The vector directions all rotate correctly with the physical frame; their sizes and thicknesses are *not* physical SI magnitudes.

### Predict first

1. Select `1` and `3`: why is torque zero in both? Which is a lower-energy alignment if both I and B are positive?
2. Select `2`: predict torque direction and magnitude relative to case `1`, and the four segment force directions; reveal with `V`.
3. Select `4` or press `N`: which physical arrows reverse, and does the blue geometric normal reverse? What happens to the lower-energy alignment?
4. Press `B` and then change the signed-field slider: does B remain reversed? Is net force ever nonzero in a uniform B?
5. Compare `5` (zero I) to `6` (zero B). Which of current, magnetic moment, external field, torque and force arrows should disappear?

## Headless and genuine 3D evidence

```sh
python -m emfeeld.rectangular_loop_view examples/lessons/rectangular_loop_uniform_field.json --case 2 --headless output/loop-torque-report-new
python -m emfeeld.rectangular_loop_view examples/lessons/rectangular_loop_uniform_field.json --case 2 --snapshot output/loop-torque-image-new
```

Both output paths **must be new**; the first writes numerical evidence only and does not claim a real rendering. The second captures a real PyVista screenshot and original/current-state SI receipts. Genuine native key/slider tests and archived images belong to the dedicated qualification workflow, and are distinct from student learning or manual Windows GUI acceptance.

**Release gates:** fresh exact-head analytic, physical refusal, native 3D and original artifact checks, independent physics/graphics R2 review if requested, guarded integration and fresh actual-main Linux/Windows and archive qualification. No learner or exam-effectiveness claim. [The earlier human usability pilot, Issue #64](https://github.com/physicsvigilante/emfeeld/issues/64), remains pending; this new module does not close or substitute for it.
