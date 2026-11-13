"""Data-only static, saved-state and bounded plane-crossing observations.

Run: python -m emfeeld.observations packet.json [--output result.json]
Static-only packets never integrate. Trajectory requests reuse one solve per
referenced particle, with explicit saved-time selection and no interpolation.
Scene-v1 and the saved-sample integrator are unchanged. Event searches are separate; no viewer is imported.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
from typing import Any

import numpy as np
import scipy

from .fields import DomainError, Field, G, epsilon_0, check_kind
from .scene import Scene, scene_from_dict, strict_keys
from .trajectory_samples import QUANTITIES, SampleRequest, TrajectorySamples
from .plane_events import PlaneRequest, PlaneEvents, DIRECTIONS

TYPES = ("field", "potential", "force", "potential_difference")
ID_PATTERN = r"[A-Za-z][A-Za-z0-9_.-]{0,63}"


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    # No booleans, strings, NaN, infinities, complex values, or coercion of units.
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite JSON number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must fit a finite float64 value") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return result


def _vector(value: Any, name: str, size: int = 3) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} must be an array of {size} finite JSON numbers")
    return tuple(_number(x, f"{name}[{i}]") for i, x in enumerate(value))


def _scene_numbers(data: dict) -> None:
    """Tighten numeric authoring at this new packet boundary; legacy API is intact."""
    for group in ("sources", "particles"):
        rows = data.get(group, [])
        if not isinstance(rows, list):
            raise ValueError(f"scene.{group} must be an array")
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"scene.{group}[{i}] must be an object")
            for key, value in row.items():
                if group == "sources" and key == "type":
                    continue
                name = f"scene.{group}[{i}].{key}"
                if isinstance(value, list):
                    _vector(value, name)
                else:
                    _number(value, name)
    if "duration_s" in data:
        _number(data["duration_s"], "scene.duration_s", positive=True)
    _vector(data.get("bounds_m"), "scene.bounds_m", 6)


@dataclass(frozen=True)
class Expectation:
    value: float | tuple[float, ...]
    atol: float
    rtol: float


@dataclass(frozen=True)
class Observation:
    id: str
    type: str
    position: tuple[float, ...] | None
    endpoint: tuple[float, ...] | None
    coupling: float | None
    expectation: Expectation | None


def parse_requests(kind: str, data: Any) -> tuple[Observation, ...]:
    """Validate the entire batch before evaluating any request."""
    check_kind(kind)
    if not isinstance(data, list) or not data:
        raise ValueError("observations must be a nonempty array")
    seen: set[str] = set()
    requests = []
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("each observation must be an object")
        ident, typ = row.get("id"), row.get("type")
        if not isinstance(ident, str) or re.fullmatch(ID_PATTERN, ident) is None:
            raise ValueError("observation id must match " + ID_PATTERN)
        if ident in seen:
            raise ValueError(f"duplicate observation id: {ident}")
        seen.add(ident)
        if not isinstance(typ, str) or typ not in TYPES:
            raise ValueError(f"unsupported observation type: {typ!r}; supported: {TYPES}")
        required = ["id", "type"]
        if typ == "potential_difference":
            required += ["from_m", "to_m"]
        else:
            required += ["position_m"]
        key = "test_charge_C" if kind == "electric" else "test_mass_kg"
        if typ == "force":
            required += [key]
        strict_keys(row, [*required, "expectation"], required)
        position = _vector(row["from_m" if typ == "potential_difference" else "position_m"], ident)
        endpoint = _vector(row["to_m"], ident + ".to_m") if typ == "potential_difference" else None
        coupling = _number(row[key], key, positive=(kind == "gravity")) if typ == "force" else None
        expectation = None
        if "expectation" in row:
            e = row["expectation"]
            strict_keys(e, ("value", "atol", "rtol"), ("value", "atol", "rtol"))
            value = (_vector(e["value"], ident + ".expectation.value") if typ in ("field", "force")
                     else _number(e["value"], ident + ".expectation.value"))
            atol, rtol = (_number(e[k], ident + ".expectation." + k) for k in ("atol", "rtol"))
            if atol < 0 or rtol < 0:
                raise ValueError("expectation tolerances must be nonnegative")
            expectation = Expectation(value, atol, rtol)
        requests.append(Observation(ident, typ, position, endpoint, coupling, expectation))
    return tuple(requests)


def _comparison(value: np.ndarray, expected: Expectation) -> dict:
    # Decimal comparison avoids overflow in subtraction and tolerance arithmetic
    # for otherwise finite values. It is not higher-precision field evaluation.
    from decimal import Decimal, localcontext
    actual = value.reshape(-1).tolist()
    target = np.asarray(expected.value, dtype=float).reshape(-1).tolist()
    with localcontext() as context:
        context.prec = 80
        a, r = Decimal.from_float(expected.atol), Decimal.from_float(expected.rtol)
        passed = all(abs(Decimal.from_float(x) - Decimal.from_float(y)) <=
                     a + r * abs(Decimal.from_float(y)) for x, y in zip(actual, target))
    return {"passed": passed, "expected_value": list(expected.value) if isinstance(expected.value, tuple) else expected.value,
            "atol": expected.atol, "rtol": expected.rtol,
            "criterion": "componentwise abs(actual-expected) <= atol + rtol*abs(expected)",
            "meaning": "agreement with authored reference, not independent correctness or an error bound"}


def _evaluate(model: Field, requests: tuple[Observation, ...]) -> list[dict]:
    results = []
    for request in requests:
        typ = request.type
        unit = ("N" if typ == "force" else
                ("N/C" if model.kind == "electric" else "m/s^2") if typ == "field" else
                ("V" if model.kind == "electric" else "J/kg"))
        result: dict[str, Any] = {"id": request.id, "type": typ, "kind": model.kind, "unit": unit,
                                 "status": "ok", "value": None,
                                 "method": "analytic_source_evaluation", "error_bound": None}
        if typ == "potential_difference":
            result.update(from_m=list(request.position), to_m=list(request.endpoint),
                          convention="potential(to_m) - potential(from_m)",
                          method="analytic_endpoint_difference")
        else:
            result["position_m"] = list(request.position)
        if typ == "force":
            result["test_charge_C" if model.kind == "electric" else "test_mass_kg"] = request.coupling
        try:
            with np.errstate(over="raise", divide="raise", invalid="raise"):
                if typ in ("field", "force"):
                    value = np.asarray(model.field(request.position), dtype=float)
                    if typ == "force":
                        value = request.coupling * value
                elif typ == "potential":
                    value = np.asarray(model.potential(request.position), dtype=float)
                else:
                    # Evaluate BOTH endpoints, including when identical. A shared
                    # singular endpoint cannot be cancelled into a fabricated zero.
                    start = np.asarray(model.potential(request.position), dtype=float)
                    end = np.asarray(model.potential(request.endpoint), dtype=float)
                    if start.shape != () or end.shape != ():
                        raise FloatingPointError("potential must return a scalar at each endpoint")
                    value = end - start
                shape = (3,) if typ in ("field", "force") else ()
                if value.shape != shape or not np.isfinite(value).all():
                    raise FloatingPointError("source returned a nonfinite value or unexpected result shape")
                if typ in ("field", "force"):
                    magnitude = float(np.hypot.reduce(value))
                    if not math.isfinite(magnitude):
                        raise FloatingPointError("vector magnitude is not finite")
                    result["magnitude"] = magnitude
                result["value"] = value.tolist()
                if request.expectation is not None:
                    result["check"] = _comparison(value, request.expectation)
        except DomainError as exc:
            result.update(status="domain_error", value=None, error={"code": "undefined_or_unresolved", "message": str(exc)})
        except (FloatingPointError, OverflowError) as exc:
            result.update(status="numerical_error", value=None, error={"code": "nonfinite_or_invalid_result", "message": str(exc)})
        if result["status"] != "ok" and request.expectation is not None:
            result["check"] = {"passed": None, "reason": "not_evaluated"}
        results.append(result)
    return results


def evaluate_observations(model: Field, observations: list[dict]) -> list[dict]:
    """Public API for same-kind fields, including arbitrary nested compositions.

    Request errors raise ValueError before any evaluation. Domain/numerical
    failures are isolated per request. Unexpected programming errors propagate.
    Forces couple an independent test charge/mass to the supplied fixed field.
    """
    return _evaluate(model, parse_requests(model.kind, observations))



@dataclass(frozen=True)
class TrajectoryObservation:
    id: str
    type: str
    sample: SampleRequest
    expectation: Expectation | None


def _trajectory_request(scene: Scene, row: dict) -> TrajectoryObservation:
    required = ("id", "type", "particle_index", "quantity")
    allowed = (*required, "sample_index", "time_s", "time_selection", "max_time_error_s", "expectation")
    strict_keys(row, allowed, required)
    ident = row["id"]
    if not isinstance(ident, str) or re.fullmatch(ID_PATTERN, ident) is None:
        raise ValueError("observation id must match " + ID_PATTERN)
    particle = row["particle_index"]
    if type(particle) is not int or not 0 <= particle < len(scene.particles):
        raise ValueError("particle_index must be a zero-based integer referring to scene.particles")
    quantity = row["quantity"]
    if not isinstance(quantity, str) or quantity not in QUANTITIES:
        raise ValueError(f"unsupported saved-trajectory quantity: {quantity!r}")
    has_index, has_time = "sample_index" in row, "time_s" in row
    if has_index == has_time:
        raise ValueError("specify exactly one of sample_index or time_s")
    if has_index:
        index = row["sample_index"]
        if type(index) is not int or not 0 <= index < scene.samples:
            raise ValueError("sample_index must be a zero-based integer within the saved grid")
        if "time_selection" in row or "max_time_error_s" in row:
            raise ValueError("index selection does not accept time_selection or max_time_error_s")
        sample = SampleRequest(particle, quantity, sample_index=index)
    else:
        time = _number(row["time_s"], "time_s")
        if not 0 <= time <= scene.duration_s:
            raise ValueError("time_s must be inside the simulated time interval; no clamping")
        mode = row.get("time_selection")
        if mode not in ("exact", "nearest"):
            raise ValueError("time_s requires explicit time_selection: exact or nearest")
        tolerance = None
        if mode == "nearest":
            if "max_time_error_s" not in row:
                raise ValueError("nearest selection requires explicit max_time_error_s")
            tolerance = _number(row["max_time_error_s"], "max_time_error_s")
            if tolerance < 0:
                raise ValueError("max_time_error_s must be nonnegative")
        elif "max_time_error_s" in row:
            raise ValueError("exact selection cannot accept a nearest-time tolerance")
        sample = SampleRequest(particle, quantity, time_s=time,
                               time_selection=mode, max_time_error_s=tolerance)
    expectation = None
    if "expectation" in row:
        e = row["expectation"]
        strict_keys(e, ("value", "atol", "rtol"), ("value", "atol", "rtol"))
        value = (_vector(e["value"], ident + ".expectation.value") if QUANTITIES[quantity][1] == (3,)
                 else _number(e["value"], ident + ".expectation.value"))
        atol, rtol = (_number(e[k], ident + ".expectation." + k) for k in ("atol", "rtol"))
        if atol < 0 or rtol < 0:
            raise ValueError("expectation tolerances must be nonnegative")
        expectation = Expectation(value, atol, rtol)
    return TrajectoryObservation(ident, "trajectory_sample", sample, expectation)


def _plane_request(scene: Scene, row: dict) -> PlaneRequest:
    required = ("id", "type", "particle_index", "condition", "occurrence", "max_step_s",
                "min_normal_speed_m_s", "accuracy")
    strict_keys(row, required, required)
    ident = row["id"]
    if not isinstance(ident, str) or re.fullmatch(ID_PATTERN, ident) is None:
        raise ValueError("observation id must match " + ID_PATTERN)
    particle = row["particle_index"]
    if type(particle) is not int or not 0 <= particle < len(scene.particles):
        raise ValueError("particle_index must refer to scene.particles")
    if row["occurrence"] != "first":
        raise ValueError("only first occurrence is supported")
    c = row["condition"]
    strict_keys(c, ("type", "point_m", "normal", "direction"), ("type", "point_m", "normal", "direction"))
    if c["type"] != "plane" or not isinstance(c["direction"], str) or c["direction"] not in DIRECTIONS:
        raise ValueError("condition must be a plane with positive, negative or either direction")
    point, normal = _vector(c["point_m"], "point_m"), _vector(c["normal"], "normal")
    length = math.hypot(*normal)
    if not math.isfinite(length) or length == 0:
        raise ValueError("plane normal must have finite nonzero length")
    normal = tuple(v / length for v in normal)
    step = _number(row["max_step_s"], "max_step_s", positive=True)
    if not scene.duration_s / 10000 <= step <= scene.duration_s or step / 2 == 0:
        raise ValueError("max_step_s must be between duration_s/10000 and duration_s; refined step must be representable")
    min_speed = _number(row["min_normal_speed_m_s"], "min_normal_speed_m_s", positive=True)
    a = row["accuracy"]
    names = ("time_atol_s", "position_atol_m", "velocity_atol_m_s", "rtol")
    strict_keys(a, names, names)
    tolerances = [_number(a[k], k, positive=k != "rtol") for k in names]
    if tolerances[-1] < 0:
        raise ValueError("accuracy.rtol must be nonnegative")
    return PlaneRequest(ident, particle, point, normal, c["direction"], step, min_speed, *tolerances)


def _packet_requests(scene: Scene, data: Any) -> tuple[Observation | TrajectoryObservation | PlaneRequest, ...]:
    if not isinstance(data, list) or not data:
        raise ValueError("observations must be a nonempty array")
    requests, seen = [], set()
    for row in data:
        if isinstance(row, dict) and row.get("type") == "trajectory_event":
            request = _plane_request(scene, row)
        elif isinstance(row, dict) and row.get("type") == "trajectory_sample":
            request = _trajectory_request(scene, row)
        else:
            request = parse_requests(scene.model.kind, [row])[0]
        if request.id in seen:
            raise ValueError(f"duplicate observation id: {request.id}")
        seen.add(request.id)
        requests.append(request)
    return tuple(requests)


def _evaluate_packet(scene: Scene, requests) -> tuple[list[dict], dict | None]:
    # Keep the static-only report shape and static public API backward compatible.
    has_motion = any(isinstance(r, TrajectoryObservation) for r in requests)
    samples = TrajectorySamples(scene) if has_motion else None
    events = PlaneEvents(scene) if any(isinstance(r, PlaneRequest) for r in requests) else None
    results = []
    for request in requests:
        if isinstance(request, PlaneRequest):
            r = {"id": request.id, "type": request.type, "kind": scene.model.kind,
                 **events.observe(request)}
        elif isinstance(request, TrajectoryObservation):
            r = {"id": request.id, "type": request.type, "kind": scene.model.kind,
                 **samples.observe(request.sample)}
            if request.expectation is not None:
                r["check"] = (_comparison(np.asarray(r["value"]), request.expectation)
                              if r["status"] == "ok" else {"passed": None, "reason": "not_evaluated"})
        else:
            r = _evaluate(scene.model, (request,))[0]
        results.append(r)
    return results, samples.runs if samples is not None else None


def packet_from_dict(data: Any) -> tuple[Scene, tuple[Observation | TrajectoryObservation | PlaneRequest, ...]]:
    strict_keys(data, ("observation_schema_version", "scene", "observations", "notes"),
                ("observation_schema_version", "scene", "observations"))
    if type(data["observation_schema_version"]) is not int or data["observation_schema_version"] != 1:
        raise ValueError("only observation_schema_version 1 is supported")
    if "notes" in data and not isinstance(data["notes"], str):
        raise ValueError("notes must be a string")
    if not isinstance(data["scene"], dict):
        raise ValueError("scene must be an embedded scene-v1 object, not a path or code")
    _scene_numbers(data["scene"])
    try:
        scene = scene_from_dict(data["scene"])
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f"invalid scene: {exc}") from exc
    requests = _packet_requests(scene, data["observations"])
    return scene, requests


def _digest(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def run_packet(data: dict) -> dict:
    """Validate the complete packet, then evaluate static, saved-state and event requests.

    Saved samples integrate once per referenced particle. Plane events use separate
    base/refined terminal searches, cached per exact request. Test particles never
    become sources. Event accuracy compares two fixed-tolerance solver runs; it
    is separate from static/sample expectation checks and from solver settings.
    """
    data = deepcopy(data)
    scene, requests = packet_from_dict(data)
    results, trajectory_runs = _evaluate_packet(scene, requests)
    good = [r["status"] in ("ok", "no_event") and r.get("check", {}).get("passed", True) is True for r in results]
    report = {
        "observation_result_version": 1, "title": scene.title, "kind": scene.model.kind,
        "status": "ok" if all(good) else "partial" if any(good) else "failed",
        "scene_sha256": _digest(data["scene"]), "packet_sha256": _digest(data),
        "input": data, "results": results,
        "counts": {"requests": len(results), "evaluated": sum(r["status"] == "ok" for r in results),
                   "domain_errors": sum(r["status"] == "domain_error" for r in results),
                   "numerical_errors": sum(r["status"] == "numerical_error" for r in results),
                   "failed_expectations": sum(r.get("check", {}).get("passed") is False for r in results)},
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "constants_SI": {"G": G, "epsilon_0": epsilon_0},
        "potential_reference": "unchanged: sum of the authored source references",
        "trajectories": "not evaluated; particle feedback and self-force are not included",
        "accuracy": "float64 direct evaluation; no certified global error bound; expectations are authored checks",
    }
    if trajectory_runs is not None:
        report["trajectory_runs"] = trajectory_runs
        report["trajectories"] = "only requested particles integrated, at most once each per packet; no feedback"
        report["trajectory_observation_contract"] = 1
        report["accuracy"] = ("existing DOP853 saved samples; no observation-layer interpolation or certified "
                              "global error bound; energy drift and authored expectations are diagnostics only")
        for key, status in (("selection_errors", "selection_error"),
                            ("unsupported_trajectories", "unsupported_trajectory"),
                            ("integration_errors", "integration_error")):
            report["counts"][key] = sum(r["status"] == status for r in results)
    if any(isinstance(r, PlaneRequest) for r in requests):
        report["plane_event_contract"] = 1
        report["event_integration_policy"] = (
            "two terminal DOP853 searches per unique event request, independently of saved-sample runs; "
            "the second halves max_step and tightens solver tolerances tenfold; exact duplicates reuse results")
        report["accuracy"] = ("Float64; event refinement agreement is not a certified error bound or root "
                              "completeness guarantee. no_event means no detection in both runs, not a proof of absence.")
        if trajectory_runs is None:
            report["trajectories"] = "event-only terminal searches; no saved trajectory arrays; no feedback"
        else:
            report["trajectories"] = "saved-sample runs and terminal-event searches are separate; no feedback"
        for key, status in (("no_events", "no_event"), ("initial_condition_errors", "initial_condition_error"),
                            ("ambiguous_events", "ambiguous_event"), ("convergence_errors", "convergence_error"),
                            ("unsupported_trajectories", "unsupported_trajectory"), ("integration_errors", "integration_error")):
            report["counts"][key] = sum(r["status"] == status for r in results)
    json.dumps(report, allow_nan=False)  # Never export NaN/Infinity as a result.
    return report


def load_packet(path: str | Path) -> dict:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def no_constant(value):
        raise ValueError(f"nonfinite JSON token: {value}")

    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=no_duplicates, parse_constant=no_constant)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, help="save the same JSON report printed to stdout")
    parser.add_argument("--validate-only", action="store_true", help="check syntax/schema only; do not evaluate fields or integrate")
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.resolve() == args.packet.resolve() or
                            (args.output.exists() and args.packet.samefile(args.output))):
            raise ValueError("output must not overwrite the input packet")
        data = load_packet(args.packet)
        if args.validate_only:
            scene, requests = packet_from_dict(data)
            report = {"valid_schema": True, "kind": scene.model.kind, "requests": len(requests),
                      "evaluation": "NOT RUN; domain validity and expectations have not been checked"}
        else:
            report = run_packet(data)
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                                 prefix=".emfeeld-", suffix=".json", delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(text)
                os.replace(temporary, args.output)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        print(text, end="")
        return 0 if args.validate_only or report["status"] == "ok" else 1
    except (ValueError, OSError, OverflowError) as exc:
        print(f"emfeeld observations: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
