# Try the Gauss-law 3D desktop lesson

This candidate uses the existing Python physics and PyVista desktop viewer.
It is not the separate Three.js browser preview.

From the extracted source folder, with Python 3.11 or newer:

```sh
python -m pip install -e ".[view]"
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json
```

For an existing installed checkout, only the second command is needed.
The operating system must support a native graphics window; the source package
is not a bundled Python installer. Camera orbit/zoom uses the existing mouse
controls. Numeric keys below are the ordinary top-row keys, not the number pad.

## A five-minute conceptual walkthrough

Press **1** for a centered charge. Before pressing **V** to reveal, predict
whether the six face fluxes are equal. For this one-charge centered cube the
engine should give q/(6 epsilon_0) per face and q/epsilon_0 in total.

Press **2** for the same charge moved inside, then **F** to outline +x (press
again to cycle faces). Predict which face gains flux and whether the closed
surface's total changes. Press **V**: face values become unequal but total
flux remains q/epsilon_0. The highlighted name follows the cube's local axes,
not the screen axes. Try the yaw/tilt sliders to see that distinction.

Press **3** for an outside charge, then **V**. Is zero total flux the same as
zero electric field? The incoming and outgoing signed face contributions
cancel, while field arrows and surface samples remain nonzero.

Press **4** for equal and opposite charges inside. Predict the net enclosed
charge and total flux. After revealing, inspect the nonzero local field even
though the net enclosed charge and total flux are zero.

Press **0** to restore the original authored state. With the supplied default
cube, move the x slider to exactly 1: a charge on the mathematical surface is
shown as undefined, not assigned a half-charge flux. Moving it to 2 restores
an available result. Press **C** for a visual cutaway: the closed mathematical
surface and flux do not change.

These four cases are synthetic teaching configurations, not printed JEE
questions. They reset the surface to the initial authored one and replace the
charge list, using the initial first signed charge. Manual physical edits clear
the case label. A zero initial first charge cannot run this walkthrough.

## What to judge

Can you identify the selected face and distinguish its flux from local E dot n
coloring? Can a learner predict the total before revealing it? Do labels remain
readable while rotating and at a smaller window size? Are the inside/outside,
zero-net-charge, and cutaway distinctions clear without a verbal workaround?
Automated rendering success does not answer these teaching questions.

To save the current interactive state programmatically, use `save_snapshot` on
the live lesson. For a fresh noninteractive illustration:

```sh
python -m emfeeld.gauss_view examples/lessons/gauss_cube.json --case offcenter --snapshot NEW_CAPTURE
```

The command starts the case in prediction mode. Snapshot reports retain the
actual physical answers as evidence even when those answers are hidden onscreen.
