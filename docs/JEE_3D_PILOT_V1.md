# JEE 3D — 14-minute prediction-first walkthrough (V1)

**Learner-facing prompts only — answers are deliberately omitted.** This is a usability walkthrough of three released *analytic* desktop PyVista lessons, not a JEE exam paper and not evidence of teaching effectiveness until a real session is observed and recorded. Facilitator instructions and answers are separate in [JEE_3D_PILOT_FACILITATOR_V1.md](JEE_3D_PILOT_FACILITATOR_V1.md).

## How to use

Start in an **existing** Conda/venv environment where `emfeeld[view]` already works. From the repository root, open one viewer at a time using the commands below. All three commands use **`--case 1` to open in prediction mode with the numerical answers hidden**, before the learner sees the screen. No reinstallation is needed for each lesson. A facilitator can start each window, but you should operate at least one key or slider in each.

**Before pressing `V`**, say or write a prediction and an explanation. A numbered preset generally hides the numeric answer; `V` reveals it. When changing a scenario, hide the answer again before the next prediction if necessary. If a control is missing, unreadable or unresponsive, record what happened rather than quietly skipping it. Orbiting the camera changes the view, not the physical model.

Suggested time: **1 minute setup, 4 minutes circular loop, 4 minutes straight wire, 4 minutes capacitor, 1 minute debrief**. If a station cannot run, record "not attempted/blocked", do not invent an answer from a screenshot. The facilitator records observations on the [blank session sheet](../pilots/jee3d_v1/SESSION_TEMPLATE.md).

## A. Magnetic field of a circular current loop (4 minutes)

```sh
python -m emfeeld.circular_loop_view examples/lessons/circular_current_loop.json --case 1
```

**A1 — Right-hand direction.** Press `1` (positive current, probe at centre). In the drawing, what are the roles of the **orange**, **green**, and **blue** arrows? Which of the three should change direction when the current reverses? Predict first, then press `2` and `V` to check.

**A2 — Loop size.** Press `3` (twice the initial physical loop radius, at the centre). At fixed current, what should happen to the *magnitude* of the centre field? Does a larger-looking circle necessarily mean a longer magnetic-field arrow? Reveal with `V`.

**A3 — Either side of the axis.** Press `1` again; use the **Probe z / initial R** slider to visit `+1` and `−1` (one initial radius on either side of the centre). Before each reveal, predict the **sign** and relative **magnitude** of B. Use `V` to hide/reveal as needed. Is the loop showing B everywhere in space, or only on its axis?

Optional: press `K` for zero current and predict what should remain visible; `0` resets. Mouse orbit/zoom may help identify the plane and normal.

## B. Magnetic field of an ideal straight wire (4 minutes)

```sh
python -m emfeeld.wire_view examples/lessons/straight_current_wire.json --case 1
```

**B1 — Direction.** Press `1` (positive current along +z). At a point on the +x side of the wire, predict whether B points along +y or −y. Point out what **orange**, **green** and **blue** mean here. Check by rotating the view and pressing `V` for numeric information.

**B2 — Reversing current.** Press `3` (reversed current). Which arrows should reverse? Does the blue Ampère-loop **positive traversal** arrow reverse? Predict the sign of the *signed circulation* before `V`.

**B3 — Radius versus circulation.** Press `2` (double the **Amperian circle radius**, not the radius of a physical wire). Predict the change in `|B|` and in `∮B·dl` while current stays fixed. Does the displayed blue circle actually grow? Check the numerical radius and reveal.

Optional: press `4` for zero current; predict whether the fixed blue traversal marker remains and whether green B arrows disappear.

## C. Ideal parallel-plate capacitor (4 minutes)

```sh
python -m emfeeld.capacitor_view examples/lessons/parallel_plate_capacitor.json --case 1
```

**C1 — Add a dielectric while isolated.** Press `1` (vacuum, isolated **fixed free Q**), then `2` (dielectric filling the gap, `κ = 4`, still fixed Q). Predict the factors by which **capacitance C, free Q, voltage V, electric field E and stored energy U** change. Explain which quantity is held fixed. Press `V` to reveal.

**C2 — Add a dielectric while connected to a battery.** Press `3` (vacuum, **fixed V**), then `4` (`κ = 4`, same battery voltage). Predict the same five ratios. What can the battery exchange with the capacitor? Reveal using `V`.

**C3 — Read the picture critically.** Do the finite-looking plates and the widened gap represent computed fringing fields and exact-to-scale physical dimensions? Do field arrows encode magnitudes or directions? Distinguish stored energy from any claimed battery or mechanical work.

Optional: move **Gap / initial** within its actual available range (up to `1.5`, not `2`) while holding one electrical constraint; note any control or label difficulties. `0` resets each viewer.

## One-minute debrief

Without checking the answer key, describe **one thing the 3D view clarified**, **one thing it might mislead someone about**, and **one control or label you would change**. An unclear or incorrect prediction is useful data; recording it honestly is more important than appearing to get every answer right.

**Boundaries:** The circular-loop model computes **on-axis magnetic field only**. The straight wire is **infinitely long** and its drawn segment is schematic. The capacitor is **uniform-field, no-fringing**, with a schematic plate gap. All three use static hypothetical configurations; they do not animate changing currents, charging dynamics or forces.