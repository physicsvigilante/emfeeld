"""Headless scene execution and optional desktop preview."""
import argparse
import json
from pathlib import Path
import platform
import sys
import numpy as np
import scipy
from .fields import G, epsilon_0
from .scene import load_scene


def run_scene(scene):
    trajectories = scene.trajectories()
    summary = {"title": scene.title, "kind": scene.model.kind,
               "source_count": len(scene.model.sources), "trajectory_count": len(trajectories),
               "assumptions": "static prescribed sources; nonrelativistic test particles; no collisions/backreaction",
               "solver": "SciPy DOP853; rtol=1e-10; position atol=1e-9 m; velocity atol=1e-9 m/s; max_step=duration/200",
               "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
               "constants_SI": {"G": G, "epsilon_0": epsilon_0}, "trajectories": []}
    for trajectory in trajectories:
        summary["trajectories"].append({
            "samples": len(trajectory.time_s), "evaluations": trajectory.evaluations,
            "final_position_m": trajectory.position_m[-1].tolist(),
            "final_velocity_m_s": trajectory.velocity_m_s[-1].tolist(),
            "max_energy_drift_J": trajectory.max_energy_drift_J,
            "normalized_energy_drift": trajectory.normalized_energy_drift})
    return trajectories, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "run", "view"))
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", type=Path, help="run only: compressed NPZ numerical output")
    parser.add_argument("--screenshot", type=Path, help="view only: offscreen PNG instead of desktop window")
    args = parser.parse_args(argv)
    if args.output and args.command != "run":
        parser.error("--output is only valid with run")
    if args.screenshot and args.command != "view":
        parser.error("--screenshot is only valid with view")
    try:
        scene = load_scene(args.scene)
        if args.command == "validate":
            print(json.dumps({"valid_schema": True, "title": scene.title,
                              "trajectory_supported": scene.model.trajectory_safe or not scene.particles}))
        elif args.command == "run":
            trajectories, summary = run_scene(scene)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                arrays = {"summary_json": json.dumps(summary),
                          "scene_json": args.scene.read_text(encoding="utf-8")}
                for i, trajectory in enumerate(trajectories):
                    for key in ("time_s", "position_m", "velocity_m_s", "kinetic_J", "potential_J"):
                        arrays[f"particle_{i}_{key}"] = getattr(trajectory, key)
                # File handle prevents NumPy from silently changing the supplied filename.
                with args.output.open("wb") as handle:
                    np.savez_compressed(handle, **arrays)
            print(json.dumps(summary, indent=2, allow_nan=False))
        else:
            from .viewer import make_plotter
            plot = make_plotter(scene, off_screen=bool(args.screenshot))
            try:
                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    plot.show(screenshot=str(args.screenshot))
                else:
                    plot.show()
            finally:
                plot.close()
    except (ValueError, RuntimeError, OSError, TypeError) as exc:
        print(f"emfeeld: {exc}", file=sys.stderr)
        return 2
    return 0
