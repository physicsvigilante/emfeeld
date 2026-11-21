"""Static magnetic source composition and point probes, in world coordinates."""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import re

from scipy.constants import c, mu_0

from .observations import ID_PATTERN
from .wire_magnetism import InfiniteStraightWire, WireAxisError, _float_token, _no_duplicate_pairs, _number, _vec


@dataclass(frozen=True)
class UniformMagneticField:
    B_T: tuple

    def __post_init__(self):
        object.__setattr__(self, "B_T", _vec(self.B_T, "B_T", math.inf))

    def field_at(self, position_m):
        return self.B_T


SOURCE_TYPES = {
    "infinite_straight_wire": (InfiniteStraightWire, ("origin_m", "axis_direction", "current_A")),
    "uniform_magnetic_field": (UniformMagneticField, ("B_T",)),
}


def _keys(record, required, context):
    if not isinstance(record, dict) or set(record) != set(required):
        raise ValueError(f"{context} requires exactly: {', '.join(required)}")


def _records(model, key):
    records = model[key]
    if not isinstance(records, list) or not records:
        raise ValueError(f"{key} must be a nonempty array")
    seen = set()
    for record in records:
        ident = record.get("id") if isinstance(record, dict) else None
        if not isinstance(ident, str) or not re.fullmatch(ID_PATTERN, ident):
            raise ValueError(f"{key} id must match {ID_PATTERN}")
        if ident in seen:
            raise ValueError(f"duplicate {key} id: {ident}")
        seen.add(ident)
        yield ident, record


def _component_sum(values):
    try:
        return math.fsum(values)
    except OverflowError:
        # An intermediate sum may overflow even if the final sum is finite.
        return float(sum(map(Fraction.from_float, values)))


def _probe(ident, position, sources):
    contributions = []
    vectors = []
    for source_id, source in sources:
        try:
            vector = list(map(float, source.field_at(position)))
        except WireAxisError:
            result = dict(status="domain_error", B_T=None, reason="on_or_unresolved_near_wire_axis")
        except (ValueError, FloatingPointError):
            result = dict(status="numerical_error", B_T=None, reason="unrepresentable_source_field")
        else:
            vectors.append(vector)
            result = dict(status="ok", B_T=vector)
        contributions.append(dict(source_id=source_id, **result))

    row = dict(probe_id=ident, position_m=position, contributions=contributions, total_B_T=None)
    failures = {c["status"] for c in contributions if c["status"] != "ok"}
    if failures:
        row["status"] = "domain_error" if "domain_error" in failures else "numerical_error"
    else:
        try:
            row["total_B_T"] = [_component_sum(component) for component in zip(*vectors)]
            row["status"] = "ok"
        except OverflowError:
            row.update(status="numerical_error", reason="unrepresentable_total_field")
    return row


def _force_observation(ident, probe, charge, velocity):
    row = dict(id=ident, probe_id=probe["probe_id"], charge_C=charge, velocity_m_s=velocity, force_N=None)
    field = probe["total_B_T"]
    if field is None:
        return dict(row, status=probe["status"], reason="unavailable_probe_field")
    # Use the recorded binary64 total as the input. Multiplying the charge
    # after a rounded cross product can erase a finite final force component.
    vx, vy, vz = map(Fraction, velocity)
    bx, by, bz = map(Fraction, field)
    cross = (vy*bz - vz*by, vz*bx - vx*bz, vx*by - vy*bx)
    components = [Fraction(charge) * x for x in cross]
    try:
        values = [float(x) for x in components]
    except OverflowError:
        return dict(row, status="numerical_error", reason="unrepresentable_force")
    tolerance = Fraction(8 * math.ulp(1.))
    if any(abs(Fraction(v) - x) > abs(x) * tolerance for x, v in zip(components, values)):
        return dict(row, status="numerical_error", reason="unrepresentable_force")
    return dict(row, status="ok", force_N=values)


def evaluate(raw: bytes):
    """Validate the complete authored model before evaluating any probe."""
    model = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs,
                       parse_float=_float_token, parse_constant=_float_token)
    version = model.get("model_version") if isinstance(model, dict) else None
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported magnetic model_version")
    keys = ("model_version", "kind", "sources", "probes")
    _keys(model, (*keys, "force_observations") if version == 2 else keys, "magnetic model")
    if model["kind"] != "static_magnetic_field":
        raise ValueError("expected kind static_magnetic_field")
    sources = []
    for ident, record in _records(model, "sources"):
        kind = record.get("type")
        if not isinstance(kind, str) or kind not in SOURCE_TYPES:
            raise ValueError(f"unsupported magnetic source type for {ident}")
        factory, params = SOURCE_TYPES[kind]
        _keys(record, ("id", "type", *params), ident)
        sources.append((ident, factory(**{k: record[k] for k in params})))
    probes = []
    for ident, record in _records(model, "probes"):
        _keys(record, ("id", "position_m"), ident)
        probes.append((ident, _vec(record["position_m"], "position_m", 1e5)))
    requests = []
    if version == 2:
        probe_ids = {ident for ident, _ in probes}
        for ident, record in _records(model, "force_observations"):
            _keys(record, ("id", "probe_id", "charge_C", "velocity_m_s"), ident)
            ref = record["probe_id"]
            if not isinstance(ref, str) or ref not in probe_ids:
                raise ValueError(f"unknown probe_id in {ident}")
            charge = _number(record["charge_C"], "charge_C")
            velocity = _vec(record["velocity_m_s"], "velocity_m_s", c)
            if sum(Fraction(v)**2 for v in velocity) >= Fraction(c)**2:
                raise ValueError("test charge speed must be below the speed of light")
            requests.append((ident, ref, charge, velocity))

    rows = [_probe(ident, p, sources) for ident, p in probes]
    report = dict(report_version=version, kind=model["kind"], input_sha256=hashlib.sha256(raw).hexdigest(),
                  mu_0_T_m_per_A=mu_0, probes=rows)
    observations = []
    if version == 2:
        by_id = {row["probe_id"]: row for row in rows}
        observations = [_force_observation(ident, by_id[ref], q, v) for ident, ref, q, v in requests]
        report["force_observations"] = observations
    good = sum(row["status"] == "ok" for row in (*rows, *observations))
    report["status"] = "ok" if good == len(rows) + len(observations) else ("partial" if good else "failed")
    return report
