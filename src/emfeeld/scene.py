"""Strict JSON authoring: data only, no eval/import/executable expressions."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import numpy as np
from .fields import (PointSource, SolidSphere, SphericalShell, InfiniteLine,
                     InfinitePlane, UniformField, Superposition, scalar, check_kind)
from .dynamics import Particle, integrate

REGISTRY = {"point": PointSource, "solid_sphere": SolidSphere,
            "shell": SphericalShell, "line": InfiniteLine, "plane": InfinitePlane}


# Shared with the generated capability catalogue. Constructor dispatch stays here.
SOURCE_PARAMETERS = {
    "solid_sphere": {"radius_m": "radius"},
    "shell": {"radius_m": "radius"},
    "line": {"direction": "direction", "reference_radius_m": "reference_radius"},
    "plane": {"normal": "normal"},
    "point": {},
}
SCENE_REQUIRED = ("schema_version", "title", "kind", "sources", "bounds_m")
SCENE_OPTIONAL = ("particles", "duration_s", "samples")


def source_keys(kind, source_type):
    """Return required/optional authored keys used by parser and discovery."""
    check_kind(kind)
    if not isinstance(source_type, str):
        raise ValueError("source type must be a string")
    if source_type == "uniform":
        field = "field_N_C" if kind == "electric" else "field_m_s2"
        return ("type", field), ("origin_m",)
    if source_type not in REGISTRY:
        raise ValueError(f"unsupported source type: {source_type!r}")
    strength = "charge_C" if kind == "electric" else "mass_kg"
    if source_type == "line":
        strength = "charge_per_m_C_m" if kind == "electric" else "mass_per_m_kg_m"
    elif source_type == "plane":
        strength = "charge_per_m2_C_m2" if kind == "electric" else "mass_per_m2_kg_m2"
    extras = SOURCE_PARAMETERS[source_type]
    required = ("type", strength, *(key for key in extras if key in ("radius_m", "reference_radius_m")))
    optional = ("center_m", *(key for key in extras if key not in required))
    return required, optional


def strict_keys(data, allowed, required=()):
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    unknown = set(data) - set(allowed)
    missing = set(required) - set(data)
    if unknown or missing:
        raise ValueError(f"unknown keys: {sorted(unknown)}; missing keys: {sorted(missing)}")


def _json_number(value, name):
    """Reject coercion at the data-only boundary; Python field APIs are separate."""
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite JSON number")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must fit a finite float64 value") from exc
    if not finite:
        raise ValueError(f"{name} must be a finite JSON number")


def _numeric_fields(data, *, exclude=()):
    for name, value in data.items():
        if name in exclude:
            continue
        if isinstance(value, list):
            for index, item in enumerate(value):
                _json_number(item, f"{name}[{index}]")
        else:
            _json_number(value, name)


def source_from_dict(kind, data):
    if not isinstance(data, dict):
        raise ValueError("source must be an object")
    source_type = data.get("type")
    if not isinstance(source_type, str):
        raise ValueError("source type must be a string")
    _numeric_fields(data, exclude=("type",))
    if source_type == "uniform":
        key = "field_N_C" if kind == "electric" else "field_m_s2"
        required, optional = source_keys(kind, source_type)
        strict_keys(data, (*required, *optional), required)
        return UniformField(kind, data[key], data.get("origin_m", (0, 0, 0)))
    if source_type not in REGISTRY:
        raise ValueError(f"unsupported source type: {source_type!r}")
    required, optional = source_keys(kind, source_type)
    key = required[1]
    extras = SOURCE_PARAMETERS[source_type]
    strict_keys(data, (*required, *optional), required)
    kwargs = {dst: data[src] for src, dst in extras.items() if src in data}
    return REGISTRY[source_type](kind, data[key], data.get("center_m", (0, 0, 0)), **kwargs)


@dataclass(frozen=True)
class Scene:
    title: str
    model: Superposition
    particles: tuple
    duration_s: float
    samples: int
    bounds_m: tuple

    def trajectories(self):
        times = np.linspace(0, self.duration_s, self.samples)
        # At most 1/200 of the requested interval per accepted solver step.
        return tuple(integrate(self.model, p, times, max_step_s=self.duration_s / 200)
                     for p in self.particles)


def scene_from_dict(data):
    strict_keys(data, (*SCENE_REQUIRED, *SCENE_OPTIONAL), SCENE_REQUIRED)
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("only schema_version 1 is supported")
    check_kind(data["kind"])
    if not isinstance(data["title"], str) or not data["title"].strip():
        raise ValueError("title must be a nonempty string")
    if not isinstance(data["sources"], list) or not data["sources"]:
        raise ValueError("sources must be a nonempty array")
    model = Superposition(tuple(source_from_dict(data["kind"], s) for s in data["sources"]))
    raw_particles = data.get("particles", [])
    if not isinstance(raw_particles, list):
        raise ValueError("particles must be an array")
    particles = []
    for p in raw_particles:
        strict_keys(p, ("mass_kg", "charge_C", "position_m", "velocity_m_s"),
                    ("mass_kg", "position_m", "velocity_m_s"))
        if data["kind"] == "electric" and "charge_C" not in p:
            raise ValueError("electric test particles must specify charge_C")
        _numeric_fields(p)
        particles.append(Particle(**p))
    if particles and "duration_s" not in data:
        raise ValueError("moving scenes must specify duration_s")
    _json_number(data.get("duration_s", 1), "duration_s")
    duration = scalar(data.get("duration_s", 1), "duration_s", positive=True)
    count = data.get("samples", 401)
    if type(count) is not int or not 2 <= count <= 100000:
        raise ValueError("samples must be an integer from 2 through 100000")
    if not isinstance(data["bounds_m"], list):
        raise ValueError("bounds_m must be an array of six finite JSON numbers")
    _numeric_fields({"bounds_m": data["bounds_m"]})
    bounds = np.asarray(data["bounds_m"], dtype=float)
    if bounds.shape != (6,) or not np.isfinite(bounds).all() or np.any(bounds[::2] >= bounds[1::2]):
        raise ValueError("bounds_m must be [xmin,xmax,ymin,ymax,zmin,zmax] with min < max")
    return Scene(data["title"], model, tuple(particles), duration, count, tuple(bounds))


def scene_from_json(text):
    """Parse one captured document; callers may retain it as output provenance."""
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return scene_from_dict(json.loads(text, object_pairs_hook=no_duplicates))


def load_scene(path):
    return scene_from_json(Path(path).read_text(encoding="utf-8"))
