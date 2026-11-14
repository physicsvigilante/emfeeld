# Machine-readable authoring catalogue

Generate the catalogue for the engine you actually have installed:

```text
python -m emfeeld capabilities
python -m emfeeld capabilities --output output/capabilities.json
```

`python -m emfeeld.capabilities` is equivalent. Neither command evaluates fields,
integrates particles, imports the viewer, or contacts an LLM service. It also works
from a normal wheel installation outside the repository checkout.

## What it describes

The version-1 JSON document lists electric and gravitational sources separately:
point, uniform solid sphere, thin spherical shell, infinite line, infinite plane,
and uniform field. Required/optional source keys and defaults, SI units, potential
references and trajectory restrictions are explicit. Source key definitions are
shared with `scene.py`; observation names, quantities, units, directions and the
rest-launch policy come from the existing runtime modules. Other structural and
semantic descriptions are checked against the actual parser by regression tests.

Static probes, saved-sample selectors, plane/radial crossings, local turning
points and the optional exact-rest policy are covered. The catalogue provides
small source/request fragments, not answers to textbook problems. It is descriptive
discovery data, **not a complete JSON Schema or a replacement validator**. Runtime
validation and numerical execution remain authoritative.

It distinguishes:

- electric potential in V from gravitational potential in J/kg;
- static source availability from trajectory availability;
- a schema-valid request from an accurate, physically appropriate measurement;
- `no_event` from a located crossing, and a local extremum from global closest approach;
- a fixed prescribed charge distribution from a conductor responding to an external field.

The JSON source list is flat; nested composition is available through the Python
API, not an invented nested JSON source type. All sources in a scene have one
physical kind. A charge parameter on a gravitational particle is ignored metadata,
not simultaneous electric and gravitational dynamics.

## Use it while authoring

First record the problem's sources, assumptions, supplied values and requested
measurements. Keep unit conversions, author-derived values and illustrative values
separate. Consult the catalogue before choosing source or observation names.
Declare unsupported requirements rather than substituting different physics.

Create an observation packet with an embedded scene and named measurements. Then:

```text
python -m emfeeld.observations packet.json --validate-only
python -m emfeeld.observations packet.json --output output/result.json
```

Inspect individual statuses, units, shapes and numerical diagnostics. Exit code
zero can include `no_event`: it is not by itself a successful answer to a crossing
question. For a visual preview, save the packet's `scene` object separately and
pass that scene file to `python -m emfeeld view`; the viewer does not accept the
observation-packet wrapper directly. Use a separate hash-locked reference manifest
with `tools/replay_packets.py` for verification. See `AUTHORING_WORKFLOW.md`.

## Two runnable examples

`examples/authoring/discovery_electric.json` and `discovery_gravity.json` each
combine two translated uniform spheres and a uniform field with a moving test
body, static probes, saved states and a plane crossing. Their requested results
are obtained by the existing observation command, not problem-specific solver code.

```text
python tools/replay_packets.py verification/discovery_examples.json --output output/discovery-001
```

The complete motion remains inside both spheres. Parameters give acceleration
`-(position-equilibrium)` in SI. The separate preparation script
`verification/build_discovery_references.py` uses the harmonic solution and
analytic interior potentials without importing emfeeld. This supplies 36 numerical,
unit and refinement checks across 10 observations. These are deliberately
illustrative same-author checks, not new textbook coverage or a blind LLM study.
The manifest hashes the exact published packets; it is not regenerated during replay.

## Export corrections accompanying the catalogue

A scene command now captures its JSON text once and embeds that same document in
its NPZ output. A file edited during calculation cannot replace the provenance
record with a different model. This preserves document text, not a raw-byte hash;
use the replay runner when exact-byte identity is needed.

Screenshot export stages the image in the destination directory and replaces an
existing output only after rendering succeeds. A failed render/write keeps the
prior image. Extensionless screenshot requests use the actual `.png` destination
for input-alias protection; they cannot bypass that guard and overwrite an input
named `scene.png` by requesting `--screenshot scene`.

No source law, integration algorithm, event policy, viewer implementation,
existing numerical tolerance, dependency range or historical pilot is changed.
The catalogue is one step in a chat-driven authoring workflow, not an autonomous
natural-language model generator or an independent correctness judge.
