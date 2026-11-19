# Five-minute capacitor lesson (PyVista desktop)

With Python 3.11+, NumPy/SciPy and your **existing** PyVista environment:

```sh
python -m emfeeld.capacitor_view examples/lessons/parallel_plate_capacitor.json
```

For a saved (noninteractive) real screenshot, use a new destination:

```sh
python -m emfeeld.capacitor_view examples/lessons/parallel_plate_capacitor.json \
  --case 2 --snapshot output/capacitor-demo-01
```

The drawing contains finite-looking plates but represents the ideal **uniform
no-fringing parallel-plate approximation**. The gap is visually exaggerated
relative to the plate width so that the region is visible; read the SI data
for actual lengths. Turquoise arrows show E **direction**, not strength or
field-line trajectories. Yellow translucent material represents a dielectric
that *fills the entire gap*. Changing a control selects a different static
hypothetical, **not an animation of battery charging or dielectric motion**.

## Predict first, then press V

1. Press **1** (vacuum, **fixed free Q**). Note which plate is positive and
   predict the field direction. Press **2** (dielectric `kappa=4`, **same Q**):
   which of C, V, E and stored U increase/decrease? Then press **V** to reveal.
   Expected ratios: **C ×4, V ÷4, E ÷4, U ÷4**.
2. Press **3** (vacuum, **fixed voltage**) then **4** (dielectric, **same V**).
   Before V predict Q, E, U. The exact comparison is **C ×4, Q ×4, E same,
   U ×4**. The battery supplies or removes charge in different *static* models;
   these screenshots do not calculate work done by the battery or mechanical
   forces.
3. Move **Gap / initial** while in fixed-Q then fixed-V mode. A larger gap
   lowers C. With Q fixed, E remains the same and U increases. With V fixed,
   E and U decrease. There is no modeled change in capacitor area.

**Keys:** `1/2/3/4` select the four teacher-created scenarios in prediction
mode; `V` reveals or hides values; `I` adopts **isolated fixed Q** using the
currently computed Q; `B` adopts **fixed battery V** using the currently
computed V; `0` resets. Mouse orbit/zoom changes only the view. Sliders adjust
full-gap kappa and gap/initial and preserve the currently selected electrical
constraint. Reversed polarity swaps the red/blue plate colours; energy stays
nonnegative.

## What to judge

Do students distinguish free surface charge on metal from bound dielectric
charge? Can they identify the held quantity (Q or V) *before* revealing a
comparison? Can they explain why the energy change differs between the two
constraints without assuming U is automatically mechanical work? Are the
sliders, labels and schematic gap exaggeration understandable? Record actual
student predictions, not just test-suite success.
