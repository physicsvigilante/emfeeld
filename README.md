# emfeeld

A local, LLM-authorable explorer for **analytic electrostatic and Newtonian gravitational fields, potentials, and test-particle motion in 3D**.

**Status: initial implementation candidate.** The numerical core is tested. The optional PyVista viewer is implemented but has not been launched or visually qualified in the authoring environment. Independent review and a Windows desktop smoke test are still required. This is not a general electromagnetic or conductor solver.

## Install and run

Use Python 3.11 or newer in a dedicated virtual environment. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,view]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m emfeeld run examples/ideal_sun.json --output output/ideal_sun.npz
.\.venv\Scripts\python.exe -m emfeeld view examples/ideal_sun.json
```

On Linux/macOS, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. Headless calculations need only `pip install -e .`; PyVista is optional. Dependency ranges are compatibility intentions, not proof that every combination has been tested. See [validation](docs/VALIDATION.md) for the actual environment.

```text
python -m emfeeld validate examples/electric_composition.json
python -m emfeeld run examples/electric_composition.json --output output/composition.npz
python -m emfeeld view examples/shell_fields.json
python -m emfeeld view examples/ideal_sun.json --screenshot output/sun.png
```

`validate` checks the schema and reports whether trajectories are supported; it does not integrate or certify the physics. `run` computes trajectories and prints energy diagnostics. NPZ files contain SI arrays, input JSON, version/constant metadata, and no pickled objects. `view` requires a working PyVista/VTK graphics environment; screenshot mode also needs graphics support.

## What works in the numerical core

- Point sources, uniform solid spheres, thin spherical shells, infinite lines, infinite planes, and uniform fields, in both physical domains.
- Vectorized field/potential evaluation and arbitrary same-domain superpositions. No named apparatus profiles or source-count-dependent physics.
- DOP853 motion for nonrelativistic test particles in supported static, continuous fields; several independent particles can share a scene.
- Midpoint line-integral contributions and spherical flux quadrature with individual contributions retained for later visualization.
- Strict, data-only JSON authoring and explicit invalid-domain errors. No `eval`, softened singularities, or hidden conductor approximations.

The preview code combines source geometry, equal-length field-direction arrows, a potential slice, trajectory curves, and a sample-time slider. It is **not yet visually verified**. Field lines, equipotential surfaces, autoplay, and animated integral explanations are future additions, not delivered features.

## Examples

| File | Purpose |
|---|---|
| `electric_sphere.json` | Test charge entering a prescribed uniform insulating sphere; not a conducting sphere or hard collision surface |
| `electric_composition.json` | Two translated spheres plus a uniform field, authored entirely as data |
| `shell_fields.json` | Zero interior field with nonzero constant interior potential |
| `line_plane_fields.json` | Prescribed infinite line and plane with explicit potential references |
| `ideal_sun.json` | Fixed point-Sun and two independent test planets, including an inclined trajectory |

The Sun example uses illustrative SI parameters, not an ephemeris. Planet masses are 1 kg test masses; there is no planet-planet interaction or solar recoil. Rendering markers do not represent planetary radii. A solid sphere is a penetrable prescribed density, not an automatic material collision boundary.

## Authoring and extending

```python
from emfeeld import SolidSphere, UniformField, Superposition, Particle, integrate
import numpy as np

field = Superposition((
    SolidSphere("electric", -1e-9, center=(0, 0, 0), radius=1),
    UniformField("electric", (0, 0, 0.2)),
))
particle = Particle(mass_kg=1e-3, charge_C=1e-6,
                    position_m=(2, 0, 0), velocity_m_s=(0, 0.02, 0))
result = integrate(field, particle, np.linspace(0, 20, 401))
```

Python sources implement `kind`, `trajectory_safe`, `field(points)`, and `potential(points)`. Evaluation accepts shape `(..., 3)`; potentials have shape `(...)`. New physics needs a reusable source implementation and tests. New combinations of existing sources need only a new model. The JSON source registry and viewer geometry adapters are separate from field composition and integration.

JSON uses explicit unit-bearing keys: `charge_C`/`mass_kg`, `radius_m`, `center_m`, line densities `charge_per_m_C_m`/`mass_per_m_kg_m`, and plane densities `charge_per_m2_C_m2`/`mass_per_m2_kg_m2`. Lines require `reference_radius_m`. Uniform fields use `field_N_C` or `field_m_s2`. See the examples and [physics contract](docs/PHYSICS.md).

## Deliberate boundaries and next work

Shell/plane fields and potentials work, but motion involving them is rejected until surface-crossing behavior has been qualified. Point/line singular encounters are not collision handling. No source reaction, radiation, induced conductor charge, relativistic motion, simultaneous electric-plus-gravity coupling, or self-consistent many-body dynamics is implemented.

Next: independent review of the source/domain contracts, a Windows viewer launch and visual inspection, then qualified boundary events and an integral teaching view. Do not add a general mesh solver or a large application framework merely to run another supported arrangement.

No license has yet been selected by the repository owner.
