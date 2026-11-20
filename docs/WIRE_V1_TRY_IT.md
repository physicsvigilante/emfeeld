# Try a magnetic field around an infinite straight wire (five minutes)

This uses **PyVista desktop**, not the separate Three.js mini prototype. In a checkout with an already installed compatible Python/PyVista environment:

```sh
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json
```

You can orbit/zoom with the mouse, move the **Ampère loop radius** slider, and use **1/2/3/4** for four static examples. Press **V** to reveal answers, **N** to reverse the current, and **0** to restore the authored state. The circle is perpendicular to the wire even if the camera rotates.

**1. Direction (key 1):** With a positive current upwards along +z, use the right-hand thumb/curled-fingers rule: at +x, is B along +y or -y? The computed answer is **+y**. Rotate the view; a change in camera does not change the physical sign.

**2. Radius (key 2):** Before revealing, predict B and the signed Ampère circulation when the physical loop radius doubles at fixed I. **Expected:** B magnitude halves; the loop circumference doubles, so the exact signed circulation remains \(\mu_0 I\). The blue loop's displayed size remains constant, so read the actual metre value on the right.

**3. Reverse current (key 3 or N):** Predict how arrow directions and signed circulation change. **Expected:** The **orange signed-current arrow and green B arrows reverse**, and the **signed circulation changes sign**; the blue **positive Ampère traversal arrow stays fixed**. B magnitude is unchanged. At I=0 (key 4), B and circulation vanish, green B arrows disappear, and the fixed blue traversal arrow still shows the chosen positive path.

**4. Distinguish representations:** Blue is the oriented circle, green arrows are *direction-only* B glyphs, and orange is signed wire current. The dark wire is a **schematic truncated segment** of an ideal infinite wire. Do not treat glyph lengths as tesla, nor compute an Ampère integral from the drawn arrows. The model does not compute near-wire material effects, finite-wire ends, magnetic force, induction or solenoids.

Capture a new actual native scene or headless report:

```sh
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json --case 2 --snapshot NEW_SNAPSHOT
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json --case 3 --headless NEW_REPORT
```

Judge whether a JEE learner can correctly predict these sign, radius and circulation effects **before** pressing V. Human usefulness is not certified by CI. The authored figures are illustrative, not copied original JEE question statements.
