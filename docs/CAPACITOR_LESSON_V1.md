# JEE capacitor V1 — ideal parallel plates, full-gap dielectric

Scope/owner approval: [Issue #57](https://github.com/physicsvigilante/emfeeld/issues/57).
The official JEE Advanced 2026 syllabus lists capacitance, parallel plate
capacitors with/without dielectrics, capacitor combinations, and stored energy.
This *first* lesson addresses only the uniform whole-gap plate case. Series/
parallel circuits, dielectric partial insertion and spherical capacitors are not
implemented, even though these are valid future JEE topics.

## Physical assumptions

- Two *parallel*, opposite, isolated conductor faces (or connected to an ideal
  fixed-voltage battery); area `A`, separation `d`, fully filled with a homogeneous
  linear isotropic dielectric of relative permittivity `kappa`.
- **No fringing**: field is uniform between plates, zero outside, as in the
  infinite-parallel-sheet idealization. The actual *finite-looking rectangular*
  plates are a schematic: no claim of an exact finite-plate capacitance or edge
  fields. The input domain enforces `d/sqrt(A) <= 0.1` as a teaching restriction,
  **not** a certified bound on the edge-error.
- Free charges lower `+Q` and upper `-Q`, lower located at `z=-d/2`; `V` is
  `V_lower-V_upper`. A negative `Q/V` reverses the polarity and field.
- `C=kappa*epsilon0*A/d`, `Q=CV`, `E_z=V/d=Q/(kappa*epsilon0*A)`,
  `U=Q*V/2`. The constitutive polarization `P_z=epsilon0*(kappa-1)*E_z`
  gives bound face densities `-P_z` (lower) and `+P_z` (upper). Vacuum has P=0.
- Mode `isolated_charge` fixes signed free `charge_C` and derives voltage.
  Mode `battery_voltage` fixes signed `voltage_V` and derives charge. Each
  model state is **one static hypothetical**. No transient current, charge
  flow, mechanical force/work, battery energy transfer, dielectric motion,
  breakdown, external fields or general conductor solve is calculated.
  **Do not** call a change in U alone the work done by the battery or the
  plates; these are distinct energy accounts.

A point exactly on an ideal plate has two one-sided E limits, so `field_at_z`
explicitly refuses that ambiguous point rather than interpolating/softening it.
Potential is continuous with `V_upper=0` reference. Exact SI numbers only and
bounded representable display/physics domain; unknown, duplicate, string,
boolean or nonfinite JSON inputs are refused. This is not arbitrary-precision
or generic hostile JSON security.

**Explicit nonzero teaching bounds (zero is valid):** an independently authored
free charge must have `1e-18 <= |Q| <= 1e-4 C`, or a voltage-controlled
configuration `1e-12 <= |V| <= 1e5 V`. **Both derived Q and V must also remain
above these lower bounds when nonzero**, so a physically positive stored energy,
field, free surface density or dielectric polarization cannot silently collapse
to zero through underflow; switching control modes is safe for admitted states.
If an extreme geometry/control combination violates either derived bound, it is
refused even when its controlling input alone falls within range. Numeric JSON
literals such as `1e-400` are refused before float64 conversion rather than
being interpreted as exact zero. The bounds are practical lesson/admission
limits, not additional laws of capacitance or universal precision guarantees.
The dielectric slider spans the complete admitted `1 <= kappa <= 10` and must
agree with the live physical state after native interaction and reset.

## Architecture

`src/emfeeld/capacitor_lesson.py`: immutable typed physical state, measurement
and strict JSON schema. `capacitor_presentation.py`: immutable detached SI
sample buffers and *separately normalized* diagram coordinates; imports neither
PyVista nor VTK. `capacitor_view.py`: native PyVista actors/slider/prediction/UI,
not a second physics solver. The `x/y` drawing scale is `sqrt(A)` and the `z`
scale is `d`; the diagram therefore exaggerates the gap by `sqrt(A)/d`
(usually x20). Labels show the physical SI inputs and this nonuniform display
transformation explicitly.

A physical edit regenerates the prepared data **before** replacing current
state. `V` prediction/reveal and camera actions redraw existing immutable data
without recalculating physics. Mode changes `I/B` adopt current Q/V once so
that current state does not suddenly change when reinterpreted; subsequent
edits hold the selected quantity fixed. Presets `1/2/3/4` are *explicitly
teacher-created independent states* based on the first authored Q/V and A,d.
They do not model a sequence of battery/dielectric physical operations.

## Source/evidence/independent validation

`tests/test_capacitor_lesson.py` contains separate Decimal/Gauss SI checks,
negative polarity, energy identities and full-vs-partial mode refusal;
`tests/test_capacitor_presentation.py` checks detached immutable arrays and
visible schematic arrows; `viewer_tests/test_capacitor_runtime.py` executes
actual PyVista widgets/key events, prediction state, source/current snapshot
and failed-state recovery. `tools/qualify_capacitor.py` saves original native
screenshots, source bytes, actual current SI sample arrays, hashes and failure
receipts. Headless users do not import graphics libraries.

**Educational status:** the three conceptual questions in the companion guide
are JEE-style author-created examples, *not verified original exam solutions*.
Human teacher/student usefulness and manual Windows GUI acceptance are open.
Preserve the upstream physical law, trajectory and original specialized JEE
modules unchanged, and keep this separate draft branch pending independent
physics/data/display review and fresh Linux+Windows/real-native qualification.
