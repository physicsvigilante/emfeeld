# Data-only static observations v1

**Additive extensions:** the same packet/command accepts [saved-trajectory requests](TRAJECTORY_OBSERVATIONS.md), [bounded first-plane-crossing requests](PLANE_EVENTS.md), and [radial-crossing requests](RADIAL_EVENTS.md). The four static operations below and their Python API are unchanged. Static-only packets never integrate.

## Purpose

An LLM can now author **the existing scene and what to measure** in one JSON packet. No per-question Python analysis is needed for field, potential, independent test-force probes, or endpoint potential differences. The evaluator dispatches on four reusable measurement types, never a book question number or apparatus name.

This is additive to the engine at `e725639f3220518e5262875d0fd48658b52e0db1`. Existing source equations, dynamics, integrals, viewer, scene-v1 schema, CLI, dependencies, examples and historical pilot files are unchanged. The new command is `python -m emfeeld.observations`; it is NOT a new subcommand of `python -m emfeeld`. Existing scene files continue to work exactly as before.

## One complete packet

```json
{
  "observation_schema_version": 1,
  "scene": {
    "schema_version": 1,
    "title": "Point-charge measurements",
    "kind": "electric",
    "sources": [{"type": "point", "charge_C": 1e-9}],
    "bounds_m": [-3, 3, -3, 3, -3, 3]
  },
  "observations": [
    {"id": "V_at_P", "type": "potential", "position_m": [2, 0, 0]},
    {"id": "E_at_P", "type": "field", "position_m": [2, 0, 0]},
    {"id": "F_at_P", "type": "force", "position_m": [2, 0, 0], "test_charge_C": -1e-6},
    {"id": "delta_V", "type": "potential_difference", "from_m": [1, 0, 0], "to_m": [2, 0, 0]}
  ]
}
```

Run an included packet and retain the machine-readable results:

```text
python -m emfeeld.observations examples/observations/num-31.json --output output/cavity-observations.json
python -m emfeeld.observations examples/observations/gravity_composition.json --output output/gravity-observations.json
python -m emfeeld.observations examples/observations/sc-55.json --validate-only
```

An installed source checkout works directly. For an uninstalled source copy, set `PYTHONPATH=src`. On PowerShell: `$env:PYTHONPATH = (Join-Path (Get-Location) 'src')`. This task adds no dependencies or user-machine installation.

The packet embeds a scene object rather than following paths, URLs, code strings, or imports. The scene can be reused with the existing viewer through `packet_from_dict(data)[0]`; the old viewer CLI still takes a scene file, not an observation packet. This first slice adds **no visual probe annotation**.

## Request and result contract

`docs/observation_contract_v1.json` is the companion machine-readable description. It is descriptive, not a JSON Schema validator. Runtime validation is authoritative.

| Type | Required data in addition to unique id/type | Result | Electric unit | Gravity unit |
|---|---|---|---|---|
| field | position_m | Three-component vector and magnitude | N/C | m/s^2 |
| potential | position_m | Scalar | V | J/kg |
| force | position_m; test_charge_C for electric OR test_mass_kg for gravity | Three-component vector and magnitude | N | N |
| potential_difference | from_m, to_m | Scalar, potential(to)-potential(from) | V | J/kg |

Coordinates are three-component JSON arrays in metres. Only finite JSON numbers are accepted; booleans, numeric strings, NaN/Infinity and implicit unit conversions are rejected. Unknown keys/types, duplicate JSON keys/observation ids, and the wrong coupling for a physical domain are errors. Ids match `[A-Za-z][A-Za-z0-9_.-]{0,63}`. Multiple requests at the same position are allowed with different ids. There is no per-apparatus or source-count limit in dispatch.

Test charge may be positive, negative or zero; test mass must be positive. A force is **qE or mg in the prescribed source field**, not a source-source force or self-force. The probe does not alter the field. Even zero test charge does not make an undefined source field well-defined. A zero-strength source retains the existing source library's zero-field convention.

All potentials retain the model's reference choices. Gravitational potential is specific energy (J/kg), not particle potential energy in joules. A potential difference is not work: the work on an electric test charge is `-q*delta_V`, and on a test mass is `-m*delta_Phi`. No work result is invented by this interface. Both endpoints must be valid, including when identical. Opposite divergent potentials or singular endpoints are not algebraically cancelled into a result.

### Failures are explicit and local

A valid request yields `status: ok`, a scalar/vector value, units, position/endpoints, method and `error_bound: null`. Vectors also include their magnitude in the same unit. An undefined or numerically unresolved source location yields `status: domain_error`, `value: null` and an explanation. Overflow, a nonfinite value or an invalid source-result shape yields `status: numerical_error`, `value: null`. Other valid requests are still evaluated. Unexpected programming exceptions are not disguised as domain errors.

For example, a thin shell's surface potential is finite while its field at that ideal sheet is unassigned. `examples/observations/domain_errors.json` deliberately returns **partial** with one valid potential and one domain error. This is correct rejection, not a zero field or a solved surface-field question.

Reports contain the input packet, canonical SHA256 hashes of the scene and packet, versions, physical constants, methods, units and counts. Canonical hashes use sorted compact UTF-8 JSON, not raw input-file bytes. No NaN/Infinity is serialized as a result. Output is written atomically; output paths resolving to the input (including hard links) are rejected.

### Optional authored reference checks

An observation can include:

```json
"expectation": {"value": [0, 0, 0], "atol": 1e-12, "rtol": 1e-11}
```

The value has the exact output shape; there is no scalar-to-vector broadcasting. Absolute tolerance uses the result unit; relative tolerance is dimensionless. Both must be finite and nonnegative. The criterion is componentwise `abs(actual-expected) <= atol + rtol*abs(expected)`.

**This tests agreement with an authored reference, not independent correctness or an estimated numerical error.** A bad reference or loose tolerance can yield a misleading check; it never changes the returned field or potential. A failed reference check leaves the computed value available and records `check.passed: false`. Domain/numerical failures record the check as not evaluated. Tolerances are not solver settings.

These are float64 evaluations of the existing analytic sources. No rigorous global error bound is provided. Potential subtraction can lose relative precision when endpoints have nearly equal large potentials; unflagged underflow and arbitrary extreme scales remain outside existing qualification. Conservative boundary rejection is inherited from the R1/R2 policy, not replaced by softening or clipping.

### CLI outcomes

Exit **0**: all requests and any supplied references succeed. Exit **1**: a domain/numerical failure or a failed supplied reference; the detailed report is still printed/saved. Exit **2**: invalid input, unsupported measurement or file-I/O error. Aggregate status is `ok`, `partial` (some requests succeed), or `failed` (none do, including reference failures). Schema-only validation returns 0 for valid syntax/schema and explicitly reports evaluation NOT RUN; it does not test domain validity or accuracy.

## LLM authoring instructions

Read the existing physics contract first, then the observation contract and a relevant packet. Translate supplied quantities into SI and record any illustrative numerical choices. Reuse supported sources and combinations; do not substitute a uniform sphere for a polarizing conductor. Embed the scene and give each requested quantity an explicit typed observation. Use the correct electric/gravitational units and potential-difference direction. Only include an expectation when its reference/provenance and tolerances are defensible. Run schema validation, then evaluation, and inspect every status. Report unsupported quantities instead of creating executable expressions, returning a known textbook answer as an engine result, or replacing a failed flux integral.

## Included packets and boundaries

Eight packets reuse **exactly the scene objects from the earlier pilot**: SC-55, SC-35, SC-96, SC-122, MC-33, NUM-31, ARCH-ADV-MC-05 and SOL-26. The SOL-26 packet measures only an endpoint potential difference; it does not claim to extract its crossing speed. Two additional illustrative packets exercise line reference potentials and gravitational composition. One deliberate shell-boundary packet demonstrates partial failure. `examples/observations/manifest.json` records references and expected statuses. There are 39 requests: 38 valid expected measurements and one intended domain error.

The Python API `evaluate_observations(model, list_of_request_dicts)` also works with nested `Superposition` objects and compatible custom field implementations. Python requests intentionally use JSON-compatible lists and built-in numbers; convert NumPy arrays/scalars with `.tolist()`/`float()`.

A packet containing **only these static request types performs no trajectory integration**, even if the embedded scene includes particles. Such particles are not included among the field sources. The additive `trajectory_sample` request is described in [its own contract](TRAJECTORY_OBSERVATIONS.md). It does not relax shell/plane trajectory restrictions. The separately qualified `trajectory_event` plane request is described in [PLANE_EVENTS.md](PLANE_EVENTS.md); it does not relax those source restrictions. Turning points, flux requests, generalized conductors, mixed electric/gravity coupling and visual annotations remain unsupported. The original SC-158 flux assessment remains PARTIAL.

See [executed evidence](OBSERVATIONS_VALIDATION.md). PR #1 remains draft and unmerged; no independent review or Windows interaction qualification is claimed.

## Radial event extension (M2B)

The same packet command now accepts `trajectory_event` with `condition.type="radial"`, a fixed centre and positive radius, and inward/outward/either direction. It shares native search/refinement machinery with plane observations; earlier packet reports retain their meanings. See [the radial guide](RADIAL_EVENTS.md), [descriptive contract](radial_event_contract_v1.json), and [qualification](RADIAL_EVENTS_VALIDATION.md). This does not implement turning points, minimum launch speed, collisions or singular-surface flux.
