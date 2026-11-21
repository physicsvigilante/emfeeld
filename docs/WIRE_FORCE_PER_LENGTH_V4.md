# Local magnetic force per unit length on a named straight wire

Run the [two parallel wires example](../examples/magnetic/parallel_wires_force.json) with

```sh
python -m emfeeld magnetic-field examples/magnetic/parallel_wires_force.json
```

Model version 4 uses kind `static_magnetic_field` with exact top-level keys `model_version`, `kind`, `sources` and `wire_force_observations`. It reuses the [static magnetic sources from V1](STATIC_MAGNETIC_FIELD_V1.md) and keeps V1–V3 inputs and outputs unchanged.

Each entry in the nonempty `wire_force_observations` array has a unique `id`, a `wire_id` referencing an `infinite_straight_wire` source in `sources`, and a finite signed `axis_distance_m` in metres along that wire's normalized axis. Both `axis_distance_m` and the resulting world observation point `origin_m + axis_distance_m * tangent` must lie within ±1e5 m.

For each observation the evaluator excludes only the target wire's own magnetic field by `source_id`, evaluates every other source at the observation point to form `external_contributions` and `external_B_T` (tesla), and computes the instantaneous local magnetic force per unit length in N/m:

**f** = I (**t** × **B**<sub>external</sub>)

where I is the target wire's signed current in amperes and **t** is its directed unit tangent. The wire remains prescribed and fixed; no motion, backreaction or self-force is modeled. For a nonuniform external field, the reported vector is the local force per unit length at the authored point.

A target with no external magnetic sources has defined zero `external_B_T` and zero `force_per_length_N_per_m`. A zero-current wire in a defined external field also yields defined zero force per unit length. If any external source is undefined or numerically unrepresentable at the observation point (for example, a distinct intersecting current-carrying wire), `external_B_T` and `force_per_length_N_per_m` are null with `domain_error` or `numerical_error`, even when the target current is zero. Exact rational arithmetic on the represented current, tangent and external field avoids intermediate overflow and cancellation before final binary64 conversion; components overflowing or losing more than eight binary64 epsilons yield `numerical_error`.

Exit codes, input SHA-256 provenance, runtime μ₀ recording, fresh-output protections and CLI discoverability (`python -m emfeeld capabilities`) follow V1–V3.
