# Circular current loop, on-axis magnetic field — candidate V1 (Issue #62)

**Development only.** This document describes draft [PR #63](https://github.com/physicsvigilante/emfeeld/pull/63); it does not certify a release, an independent review, a human GUI trial, or classroom usefulness.

## Analytic physics and visible JEE questions

One perfectly thin circular filament of radius `R > 0` lies in the plane spanned by `e1,e2`, centred at `c`. The fixed positive unit normal is `u=e1 × e2`. Positive signed steady current `I` follows `e1 → e2`, counterclockwise when looking from the tip of `u` towards the loop. Reverse current reverses its tangent arrow and magnetic-field direction.

At the centre and **only at axial points** `x=c+z*u`, in vacuum,

```text
B(x) = [mu0 * I * R**2 / (2 * (R**2+z**2)**(3/2))] * u   [T]
B(c) = mu0*I/(2*R) * u
```

`mu0` is the `scipy.constants.mu_0` SI constant. The signed scalar report is `B·u`: positive for I>0, negative for I<0, exactly zero for I=0, and it has the **same sign for z>0 and z<0**. At the centre, fixed I and doubled R halves B. At fixed `z/R`, doubling R also halves B; at fixed nonzero z in metres, the ratio is not generally one-half. Physical units are A, m and T.

This is *not* a full 3D field, Biot–Savart integration, or a field-lines solver. The viewer draws a 3D loop and a rotatable axial probe so a student can reason spatially about the field **at those permitted points**, not off-axis.

## Separation of responsibility

- `circular_loop_magnetism.py`: validates strict authored JSON and directly constructed state; rejects duplicate/unknown/Boolean/nonfinite/underflowed values; computes SI fields; refuses off-axis Cartesian probes; provides immutable author state and three centre comparison presets.
- `circular_loop_presentation.py`: prepares detached, read-only SI buffers and schematic display coordinates/directions; **no PyVista imports**.
- `circular_loop_view.py`: a PyVista adapter; draws a translucent loop plane and positive-normal arrow, signed current-tangent arrow, and centre/axial B arrows. The **rendered loop radius and axial distance use the authored initial radius as a common display scale**, so the R×2 preset visibly doubles the loop size. The immutable SI physics report and schematic display metadata are held separately, including in snapshots. All tube thicknesses and arrow lengths are illustrative, **not field strengths**. Physical state edits rebuild prepared physics; reveal and camera-only edits do not.
- `tools/qualify_circular_loop.py`: exercises actual native key/slider events, creates real screenshot PNGs and source-bound SI/current-state integrity receipts.
- `viewer_tests/test_circular_loop_runtime.py`: actual PyVista/VTK tests distinct from the headless analytic tests.

## Launch without reinstalling each time

In an environment where `emfeeld[view]` is already installed:

```sh
python -m emfeeld.circular_loop_view examples/lessons/circular_current_loop.json
```

For headless SI evidence without a graphics backend:

```sh
python -m emfeeld.circular_loop_view examples/lessons/circular_current_loop.json --headless output/loop-headless-new
```

For one real offscreen scene:

```sh
python -m emfeeld.circular_loop_view examples/lessons/circular_current_loop.json --snapshot output/loop-3d-new
```

Output directories **must be new**. The headless command does not claim to render. Interactive keys: `1` positive-at-centre, `2` reversed-at-centre, `3` doubled-radius-at-centre; each hides numerical values until `V` reveals. `N` reverses current, `K` sets it to zero, `P` restores the positive authored magnitude, `0` resets, and mouse orbit rotates the 3D view. Sliders are visibly retained in the lower-right information pane across every redraw, including offscreen screenshots; tests assert actual slider pixels instead of relying only on native VTK event dispatch. They change radius and on-axis probe position; the second slider measures z in units of the *authored initial* radius, even if radius subsequently changes.

## Interpretation limits

Blue +normal arrow is a **fixed convention**, not the magnetic field. Orange current circulation changes sign with I (absent at zero current). Green B arrows reverse or disappear with I. For very distant axial probes the numeric SI value remains valid but the marker is omitted from the finite schematic camera window, with an explicit panel note. Off-axis B, magnetic forces, time variation, multiple coils, materials and induction are unsupported.

## Required gates

Before merge: independently check analytic identities against a separately authored reference; negative and adversarial JSON cases; real PyVista native keys/sliders/screenshots; original archive CRC/source integrity; all relevant Linux and Windows regressions; exact-head independent scoped physics + viewer review. After a permitted exact-head guarded merge, qualify actual merged `main` independently on both OSs and audit its genuine original artifacts. Human classroom acceptance is separate.
