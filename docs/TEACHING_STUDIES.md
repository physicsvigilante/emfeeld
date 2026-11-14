# Verified two-configuration teaching study V1

## Purpose and authority

An LLM frames a supported physical system and an investigation. The engine computes
its consequences; the viewer presents them without inventing physical geometry.
This bounded adapter compares a baseline with exactly one changed source-strength
scalar. It is not an inverse solver, natural-language interpreter, new physical
law, or general experiment compiler. Runtime packet validation remains authoritative.

Five dimensions remain separate: interpretation fidelity, physical/numerical
correctness, simulation coverage, educational usefulness and textbook-answer
completeness. The last is optional; explicitly requested measurements cannot be
silently omitted. Numerical execution and successful rendering never establish
teacher usefulness or faithful source interpretation automatically.

## Data contract

A study has `study_version: 1`, `title`, `interpretation`, `baseline`, `change`
and `checks`. Unknown fields are rejected. See `examples/studies/electric.json`.

`baseline` is an existing observation packet, not executable code or a path.
`change` records `source_index`, `parameter`, `from_value`, `to_value`, `origin`
and `reason`. V1 admits only charge/mass or their line/surface densities. The
old value must match exactly; the new value must differ and be finite. No radius,
geometry, particle, source type, horizon, sampling or observation change is admitted.
The variant is a deep copy with one replacement, not a second freely authored model.
Changing a sphere's charge at fixed radius changes its prescribed density; it does
not model charging dynamics or conductor polarization.

`interpretation` contains a statement and separate arrays for givens, assumptions,
illustrative choices, computed inputs, unresolved information and requirements.
These are author-recorded assertions, not authenticated source extraction. V1
recognizes `fixed_prescribed_sources` and `independent_nonrelativistic_test_particles`.
An unrecognized requirement (for example `conductor_polarization`) stops before
physics. An unresolved source fact stops the study as incomplete. An author who
mislabels a conductor without declaring the requirement can still be wrong; human
interpretation review is essential. Computed inputs must not be relabelled as givens.

`checks` explicitly supplies positive finite position/velocity absolute comparison
tolerances, relative tolerance and maximum normalized energy drift. These compare
captured full-horizon trajectories against a second existing DOP853 solve with
half the step cap and tenfold tighter solver tolerances. They are not solver
parameters themselves, certified error bounds, or independent physical verification.
No automatic tolerance relaxation or retry occurs.

## Execution, failure and recorded visualization

```text
python -m emfeeld.study run examples/studies/electric.json --output output/study-001 --render
python -m emfeeld.study view output/study-001 --configuration baseline
python -m emfeeld.study view output/study-001 --configuration variant
```

Output must be a new directory. It retains the exact authored study document,
both derived packets, native per-request reports, complete trajectory arrays,
checks, byte hashes, runtime source identities, a comparison summary and a
readable REPORT.md. Images are optional. All numerical outputs remain usable
without PyVista installed. Do not delete failed attempts to manufacture first-pass claims.

The observation API's optional `capture={}` keyword reuses its existing saved-state
cache and explicitly captures every particle needed for the study view. Omit the
keyword and the original requested-only behavior and report structure remain.
Each base trajectory is computed once; one refined trajectory checks it. Native
event requests still perform their separately qualified terminal searches. Event
measurements are labelled as separate event states, not values at a common time.
The images display the captured full-horizon trajectory, not an interpolated event
path or a later hidden reintegration.

If any particle lacks a complete checked trajectory, full-scene preview is
unavailable; particles are not silently removed. Valid observations and other
particle results remain recorded. `no_event`, domain errors, failed expectations,
and unsupported requests are not successful requested measurements. A bad variant
is retained with its rejection while a valid baseline can still run. Missing facts
and declared unsupported physics are preserved rather than substituted.

Return code 0 means every requested observation succeeded, trajectory checks
passed, and requested rendering completed. Code 1 means an explicit limitation,
unfulfilled request or failed check/render. Code 2 means malformed input or I/O
failure. An interrupted output initially records `execution_complete: false`.
Unexpected numerical/programming exceptions are not relabelled as successful physics.

`view` verifies captured file hashes, scene/packet identities, initial states,
physical constants and the field implementation before showing recorded arrays.
These are integrity guards, not cryptographic authenticity or independent judgment.
The field-source identity canonicalizes Python line endings only; authored study
and captured packet hashes remain hashes of exact bytes. No pickled arrays are used.

## Honest comparison

Only source strength changes, so geometry, potential references, launch data,
physical kind and measurement requests are held fixed. Both previews use the same
bounds, explicit camera and common finite sampled potential colour range. The
range covers the shared display slice, not every possible point in space.
Equal-length field arrows show direction only; numerical probes compare strength.
Undefined samples remain holes. Point sizes are schematic; infinite sources remain
visually truncated. Snapshot files record configuration, sample time and checksum.
Playback controls on separate windows are independent, not synchronized sliders.

Static values and matched saved-time measurements show baseline, variant and
difference with units. Events can occur at different times and are displayed as
separate states. No general ratios, vector expression language or inverse operations
are added. Changing requested outputs does not create physical couplings.

## Qualification cases and limits

Electric example: two penetrable prescribed charged spheres and one positive test
charge; double the first negative source charge. All numbers are illustrative.
Gravity example: reuse `examples/ideal_sun.json` unchanged as the baseline; increase
only the fixed Sun mass by 20 percent. Both launches stay fixed. There are no mutual
planet forces or source recoil. The unsupported example declares conductor
polarization and must not run the uniform-sphere substitute.

Regression expectations use separate harmonic and Kepler expressions, not answers
entered in the study runner. They are same-author checks, not independent review
or a blind LLM reliability benchmark. A teacher must still assess whether the
comparison explains the intended physics. No new shell/plane motion, material
collisions, general conductor response, mixed electric/gravity force, global
extrema or guaranteed event detection is claimed.

Historical reports and evaluation totals are unchanged. Live guidance recognizes
that PR #1 is merged; new study implementation remains a separate unmerged candidate.
The primary cross-platform CI gate covers relevant PRs targeting main and main
pushes. Human Windows mouse/keyboard qualification remains separate from offscreen CI.
