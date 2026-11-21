# Instantaneous test-charge magnetic force

Run the [wire and uniform field example](../examples/magnetic/test_charge_force.json) with

```sh
python -m emfeeld magnetic-field examples/magnetic/test_charge_force.json
```

Model version 2 reuses the [static sources and probes from V1](STATIC_MAGNETIC_FIELD_V1.md). Add a nonempty `force_observations` array. Each observation has a unique `id`, a `probe_id` referencing a probe in the same model, a signed finite `charge_C`, and a Cartesian `velocity_m_s` with speed below the speed of light. The supplied velocity is the instantaneous laboratory velocity. The charge is a test body with no backreaction. This observation needs no mass, timestep or dynamical solver.

The force in newtons is **F** = q (**v** × **B**), where **B** is the reported total field at the selected probe. Any number of charges or hypothetical velocities can reuse one probe. In the example a current along +z contributes a +y field east of the wire, and a uniform bias contributes +z. The positive charge moving east experiences approximately (0, −2e-9, +1e-9) N. Reversing the charge reverses the force.

Report version 2 retains the full probe results and adds a row per force request, including the source probe ID, charge, velocity, status and `force_N`. A resolved parallel velocity, zero charge or zero speed yields zero force in a defined field. If the probe is unavailable its force is null, including for zero charge or speed. Exact arithmetic on the represented charge, velocity and field avoids intermediate overflow and cancellation before converting the force to binary64. A component that overflows or loses relative precision beyond eight binary64 epsilons yields a numerical error. Other requests still run. The aggregate status and exit codes follow V1 and count both probes and forces. Version 1 continues to require its original four keys.
