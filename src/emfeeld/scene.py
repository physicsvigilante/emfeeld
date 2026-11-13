"""Strict JSON authoring: data only, no eval/import/executable expressions."""
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
from .fields import (PointSource, SolidSphere, SphericalShell, InfiniteLine,
                     InfinitePlane, UniformField, Superposition, scalar, check_kind)
from .dynamics import Particle, integrate

REGISTRY = {"point": PointSource, "solid_sphere": SolidSphere,
            "shell": SphericalShell, "line": InfiniteLine, "plane": InfinitePlane}


def strict_keys(data, allowed, required=()):
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    unknown = set(data) - set(allowed)
    missing = set(required) - set(data)
    if unknown or missing:
        raise ValueError(f"unknown keys: {sorted(unknown)}; missing keys: {sorted(missing)}")


def source_from_dict(kind, data):
    if not isinstance(data, dict):
        raise ValueError("source must be an object")
    source_type = data.get("type")
    if source_type == "uniform":
        key = "field_N_C" if kind == "electric" else "field_m_s2"
        strict_keys(data, ("type", key, "origin_m"), ("type", key))
        return UniformField(kind, data[key], data.get("origin_m", (0, 0, 0)))
    if source_type not in REGISTRY:
        raise ValueError(f"unsupported source type: {source_type!r}")
    key = "charge_C" if kind == "electric" else "mass_kg"
    if source_type == "line":
        key = "charge_per_m_C_m" if kind == "electric" else "mass_per_m_kg_m"
    elif source_type == "plane":
        key = "charge_per_m2_C_m2" if kind == "electric" else "mass_per_m2_kg_m2"
    extras = {"solid_sphere": {"radius_m": "radius"},
              "shell": {"radius_m": "radius"},
              "line": {"direction": "direction", "reference_radius_m": "reference_radius"},
              "plane": {"normal": "normal"}, "point": {}}[source_type]
    # Radius and line reference must be explicit in authored scenes.
    required = ["type", key] + [k for k in extras if k in ("radius_m", "reference_radius_m")]
    strict_keys(data, ["type", key, "center_m", *extras], required)
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
    keys = ("schema_version", "title", "kind", "sources", "particles", "duration_s", "samples", "bounds_m")
    strict_keys(data, keys, ("schema_version", "title", "kind", "sources", "bounds_m"))
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
        particles.append(Particle(**p))
    if particles and "duration_s" not in data:
        raise ValueError("moving scenes must specify duration_s")
    duration = scalar(data.get("duration_s", 1), "duration_s", positive=True)
    count = data.get("samples", 401)
    if type(count) is not int or not 2 <= count <= 100000:
        raise ValueError("samples must be an integer from 2 through 100000")
    bounds = np.asarray(data["bounds_m"], dtype=float)
    if bounds.shape != (6,) or not np.isfinite(bounds).all() or np.any(bounds[::2] >= bounds[1::2]):
        raise ValueError("bounds_m must be [xmin,xmax,ymin,ymax,zmin,zmax] with min < max")
    return Scene(data["title"], model, tuple(particles), duration, count, tuple(bounds))


def load_scene(path):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    with Path(path).open(encoding="utf-8") as handle:
        return scene_from_dict(json.load(handle, object_pairs_hook=no_duplicates))
