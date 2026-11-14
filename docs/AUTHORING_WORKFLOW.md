# Question-to-packet workflow

## 1. Interpret before authoring

Record the actual givens, requested quantities, source geometry and relevant
boundary conditions. Separate supplied numbers, unit conversions, author-derived
parameters and illustrative numbers. A fixed prescribed charge distribution is
not a polarizable conductor; test bodies do not interact with each other.

Declare unsupported requirements instead of silently replacing them. Inverse
algebra performed by the LLM is not a native inverse-engine solution. A numerical
instance does not prove a symbolic statement for every parameter value. A
conditional field equivalence is usable only in its stated physical domain.

## 2. Author data, then validate

Create an observation packet with `observation_schema_version: 1`, an embedded
scene and named observations. Use the existing contracts in OBSERVATIONS.md,
TRAJECTORY_OBSERVATIONS.md, PLANE_EVENTS.md, RADIAL_EVENTS.md, TURNING_EVENTS.md
and REST_LAUNCH_TURNING.md. These documents specify units and failure semantics.

Use real JSON numbers, never strings such as `"1e-6"` or booleans as coordinates.
Do not put expected answers inside the simulation packet for an authoring study.
The author must choose and disclose horizons and numerical settings, rather than
alter an initial condition to bypass a limitation.

```text
python -m emfeeld.observations path/to/packet.json --validate-only
python -m emfeeld.observations path/to/packet.json --output output/result.json
```

Validation checks syntax/schema, not physical interpretation. Numerical success
is not a completeness guarantee: `no_event` is not proof that no event exists,
and it is not a successful answer to a request that required a detected event.

## 3. Freeze and replay the published inputs

Keep references separate from model data. A replay manifest uses repository-
relative packet paths, exact SHA256 hashes, expected per-observation statuses
and separate comparisons. `verification/v6_published.json` is a working example.
Its references are same-author analytic checks; their preparation is retained in
`verification/build_v6_references.py`, which does not call the engine.

```text
python tools/replay_packets.py verification/v6_published.json --output output/replay-001
```

The runner checks the entire manifest and all hashes before any physics. It
refuses existing output directories, captures the original bytes, evaluates those
copies, and saves native reports, per-check assessments and engine-source hashes.
It has no question-specific physics or replacement answers. A changed input,
missing state, wrong shape/unit/value or unexpected `no_event` cannot pass.
A deliberate schema rejection is verified separately and is not a solved task.

Exit 0 means every declared regression outcome passed; exit 1 means a comparison
failed; exit 2 means a manifest, hash, input or I/O error. Unexpected programming
errors propagate rather than becoming supported or unsupported physics claims.

## 4. Report the right level of evidence

Distinguish schema validity, execution, numerical reference agreement, physical
interpretation and original-question coverage. Preserve corrections and failed
attempts. Publish the same bytes that were tested and verify their Git blob
identities before moving the branch. Do not replace evidence with a retyped
"equivalent" model or call shared-baseline test counts cumulative across pilots.

This workflow runs in this chat or locally without another coding agent. A true
held-out reliability study still needs an author context without the answers and
a separately prepared judge. The ongoing source-aware chat cannot establish
that independence merely by naming folders `author` and `verifier`.

## 5. Teaching studies rather than answer-format benchmarks

The simulator accompanies teaching and exploration. Report interpretation
fidelity, physical correctness, simulation coverage, educational usefulness and
textbook-answer completeness separately. Original answer reproduction is optional;
fulfilling an explicitly supported measurement request is not. Preserve the old
pilot scoring and frozen evidence rather than retrospectively improving them.

For a controlled comparison, author a V1 study with one baseline packet and one
source-strength replacement. Record assumptions, illustrative choices, computed
inputs and unresolved source information. See TEACHING_STUDIES.md. The adapter
validates both configurations and records arrays/diagnostics before presentation.
It neither interprets natural language nor certifies an author's interpretation.
Supported inverse mathematics and new source laws remain separate work.
