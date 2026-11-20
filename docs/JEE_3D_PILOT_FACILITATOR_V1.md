# JEE 3D pilot V1 — facilitator protocol and answer key

**Facilitator only: do not show this guide before the learner has committed each prediction.** Approved preparation for [Issue #64](https://github.com/physicsvigilante/emfeeld/issues/64); **no human session has yet been conducted or certified**. The learner-facing questions live in [JEE_3D_PILOT_V1.md](JEE_3D_PILOT_V1.md). This is a small conceptual/usability trial, **not** an independently designed JEE assessment, effectiveness study, or modification of physics code.

## Preflight (about 1 minute)

- Use an existing Python/Conda environment in which the PyVista lessons already launch. From the intended checkout, record `git rev-parse HEAD`, `python --version`, OS, environment type, approximate screen/window size, and whether each viewer opened without installing anything new. The released qualification baseline is `cf884b6d91cb685993e07a1c65236b65d185e521`; a different actual checkout is permitted only if recorded and identified, not silently treated as that release.
- **Avoid answer leakage on startup:** without a preset, the viewers initially show numerical answers. The learner-sheet commands deliberately pass `--case 1` so the first visible interactive window already hides values. If the learner saw an unrevealed answer before predicting, record that contamination instead of scoring it as independent prediction.
- Do not reveal the answer key. Ask a neutral question and **capture the exact pre-reveal response** before using `V`. Prompt for explanation, not simply the arrow/color choice. After the reveal, record whether the learner can now explain *why*.
- Ask the participant to operate **at least one real key and slider** in each viewer where available. Note whether the controls are actually visible/clickable and whether camera orbit affects physical interpretation. Do **not** equate CI screenshot pixels or synthetic VTK events with a human trial.
- Start three viewer commands from [the learner sheet](JEE_3D_PILOT_V1.md), **one at a time**; allow about four minutes each. The shared source can be used without reinstalling in the same environment. If the environment cannot launch, mark the trial blocked and preserve a truthful report.
- Keep source records anonymous: do not collect names, contact details or unneeded screen content. Where a genuine live UI screenshot is taken via the OS, identify it as such; a CLI `--snapshot` generates a new noninteractive scenario and is **not** evidence of a learner's live camera/control state. Use fresh, distinct evidence paths; do not overwrite historical/qualified runs.

## Expected physical references (compare only after predictions)

### A — One ideal circular current filament, axis-only B

- `I>0` circulates along the chosen positive tangent; **orange** is signed current. **Green** is the signed **B direction**, while **blue** is the fixed positive loop **normal**, a coordinate/orientation convention (not an arrow for B). With `I<0`, **orange and green reverse; blue stays fixed**. Exact zero current removes current and B arrows but leaves the blue normal.
- Along the axis `u`, `B(z) = [μ₀ I R² / (2(R²+z²)^(3/2))]u`, so `B(0)=μ₀ I/(2R)u`. At fixed current, **R×2 halves the centre |B|**. The loop's rendered radius doubles on the shared initial-R display scale; arrows remain direction-only, not proportional to tesla.
- At `z=+R` and `z=−R`, B points the **same direction**, with **equal magnitude** `|B(R)|=|B(0)|/(2√2)`, not oppositely directed. The 3D display is a loop in space, but the field is calculated **only at its centre and along its axis**, not off-axis.

### B — Ideal infinite straight current wire

- For `I>0` along `+z`, at the positive x-side the magnetic field points **+y**, by the right-hand rule. **Orange** denotes signed wire current. **Green** denotes magnetic B. **Blue** denotes the fixed **positive Ampère circulation traversal**, a different convention than the loop's blue normal.
- Reverse I: **orange and green reverse**; **blue stays fixed**, even at `I=0`. The **signed** circulation `∮ B·dl=μ₀ I` reverses sign; `|B|` at fixed radius is unchanged by current sign, while `I=0` removes B arrows/integral.
- `B(R)=μ₀ I/(2πR)` in magnitude; doubling the **Amperian** radius at fixed current gives **|B| ÷2** but leaves signed `μ₀I` unchanged. The blue circle's drawn radius is normalized for visual comparison and may **not visibly grow**. The original physical loop-radius value in metres updates; it is not the physical radius of the ideal wire.

### C — Uniform-field ideal parallel-plate capacitor

`C=κ ε₀ A/d`. In the **isolated fixed-Q** case, `V=Q/C`, `|E|=|Q|/(κ ε₀ A)`, `U=Q²/(2C)`. In the **battery fixed-V** case, `Q=CV`, `|E|=|V|/d`, `U=CV²/2`.

| Ratio after κ changes from 1 to 4 | Held free Q (keys 1→2) | Held voltage V (keys 3→4) |
| --- | --- | --- |
| Capacitance C | ×4 | ×4 |
| Free charge Q | ×1 | ×4 |
| Voltage V | ÷4 | ×1 |
| Field magnitude E | ÷4 | ×1 |
| Stored field energy U | ÷4 | ×4 |

These are **ratios between static constrained states**, not a calculation of actual battery or mechanical work. The dielectric fills the entire gap. The plate gap is visually **exaggerated** and drawn finite-looking plates **do not produce fringe fields** in the model; green/turquoise arrows indicate **E direction**, not SI vector-length magnitude. The available gap slider is `0.5–1.5` times initial spacing; do not ask the interface to demonstrate `2×`.

## What to record, without claiming effectiveness

Use [the blank session template](../pilots/jee3d_v1/SESSION_TEMPLATE.md) for each actual run. For task IDs A1–C3, preserve a **verbatim or faithful pre-reveal prediction**, any post-reveal explanation, controls actually operated, what visibly happened, and whether the prompt could be completed without a hint. Record failures/confusions even when the expected physics is correct.

Distinguish **conceptual misconception**, **UI/usability obstacle**, **scientifically misleading visual convention**, and **execution/install obstacle**; list reproducible severity and any screenshot evidence. A teacher-led session, student-led session, and owner self-evaluation have **different evidentiary weight**—record the category explicitly. If no trial occurred, leave status **NOT CONDUCTED**. One short session can identify UX problems but does **not** prove general JEE effectiveness or exam gains.

## Follow-up decision rule

The observation record, not a successful test workflow, determines the next step. If a specific defect is reproduced, create a **narrow documentation/UI follow-up** with an explicit observed source and affected lesson; preserve validated magnetic/electric formulas. If nothing problematic is observed, record *no issue observed in this small session*, **not** “learners proven to benefit.” Link findings to [pilot Issue #64](https://github.com/physicsvigilante/emfeeld/issues/64) and to the existing [capacitor pilot Issue #59](https://github.com/physicsvigilante/emfeeld/issues/59) as relevant. [Gauss usability Issue #56](https://github.com/physicsvigilante/emfeeld/issues/56) remains separate.