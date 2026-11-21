# Static magnetic field composition V1

Run the [two-wire model](../examples/magnetic/two_wires.json) with

```sh
python -m emfeeld magnetic-field examples/magnetic/two_wires.json
```

The two 5 A currents point along +z, one metre to either side of the origin. These are illustrative inputs. At the midpoint their y components cancel. At (3, 0, 0) m their y components add to about +7.5e-7 T. At the left wire, the right wire contributes about −5e-7 T along y, the left contribution is undefined, and the total is null. This example therefore returns a partial report and exit code 1.

Each source has a stable ID. Reversing the right current changes the midpoint total to about +2e-6 T along y. Adding a source such as `{"id":"bias","type":"uniform_magnetic_field","B_T":[0,0,2e-6]}` adds a prescribed z component wherever the total is defined. These edits use the same command.

## Model and physical domain

Use exactly the four top-level keys in the example, with at least one source and one probe. IDs are unique within each list and match `[A-Za-z][A-Za-z0-9_.-]{0,63}`. Each probe has exactly `id` and `position_m`. All vectors have three finite Cartesian components. Boolean values, numeric strings, duplicate JSON keys, unknown properties and unsupported laws are refused.

- **Infinite straight wire.** Supply `origin_m`, `axis_direction` and signed `current_A`. For unit axis **u** and perpendicular displacement **ρ**, the field is μ₀ I (**u** × **ρ**) / (2π |**ρ**|²). Positive current flows along **u**. The shared wire evaluator accepts origin coordinates up to 100 m in absolute value, direction norm from 1e-8 through 100, and current zero or magnitude 1e-6 through 1e4 A. Its axis and unresolved near-axis domain checks apply to every active wire individually. Zero current contributes exact zero everywhere.
- **Uniform field.** Supply the prescribed vector `B_T` in tesla. It has the same value at every probe.
- **Probe.** Each world coordinate is bounded to ±1e5 m. The sources are static and prescribed. The sole observation is magnetic field in tesla.

## Report and failure behavior

The shared wire evaluator forms cross products and squared distances using exact fractions of the represented coordinates before converting each SI field component to binary64. A direction component must survive normalization. A subnormal direction or field component whose relative rounding error exceeds eight binary64 epsilons is refused. The near-axis resolution test remains separate from these representability checks.

The JSON report includes the input byte SHA-256, the runtime value of μ₀ in T m/A, a status and the probe results in authored order. For each probe it records every source ID, contribution status and `B_T`, followed by the componentwise sum `total_B_T`. A failed contribution retains its reason and has a null field. Any failed contribution or unrepresentable total makes the total null. Other probes still run.

Exit 0 means all probes succeeded. Exit 1 accompanies a report marked `partial` (some probes succeeded) or `failed` (none succeeded). Exit 2 means invalid input or an I/O failure. Optional `--output NEW_REPORT.json` also writes the report to a fresh file outside protected evidence. Use `python -m emfeeld capabilities` to discover the model and command.
