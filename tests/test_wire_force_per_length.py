import hashlib
import json
import math
from pathlib import Path

import pytest
from scipy.constants import mu_0

from emfeeld.capabilities import get_capabilities
from emfeeld.cli import main
from emfeeld.magnetic_probes import evaluate


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/magnetic/parallel_wires_force.json"


def packet():
    return json.loads(EXAMPLE.read_bytes())


def run(model):
    return evaluate(json.dumps(model).encode())


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _wire_B_analytic(origin, axis, current, point):
    norm = math.hypot(*axis)
    t = tuple(v / norm for v in axis)
    d = tuple(p - o for p, o in zip(point, origin))
    proj = sum(di * ti for di, ti in zip(d, t))
    r_perp = tuple(di - proj * ti for di, ti in zip(d, t))
    r2 = sum(v * v for v in r_perp)
    scale = mu_0 * current / (2.0 * math.pi * r2)
    c = _cross(t, r_perp)
    return tuple(scale * v for v in c)


def test_parallel_wires_example_through_cli(tmp_path, capsys):
    dest = tmp_path / "wire_force_report.json"
    raw = EXAMPLE.read_bytes()
    assert main(["magnetic-field", str(EXAMPLE), "--output", str(dest)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads(dest.read_bytes())
    assert report["report_version"] == 4
    assert report["kind"] == "static_magnetic_field"
    assert report["input_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["mu_0_T_m_per_A"] == mu_0
    assert report["status"] == "ok"

    f_mag = mu_0 * 5.0 * 5.0 / (2.0 * math.pi * 2.0)
    b_mag = mu_0 * 5.0 / (2.0 * math.pi * 2.0)
    rows = {r["id"]: r for r in report["wire_force_observations"]}

    left = rows["force_on_left"]
    assert left["wire_id"] == "wire_left"
    assert left["excluded_source_id"] == "wire_left"
    assert [c["source_id"] for c in left["external_contributions"]] == ["wire_right"]
    assert left["external_B_T"] == pytest.approx([0.0, -b_mag, 0.0], rel=2e-15, abs=0)
    assert left["force_per_length_N_per_m"] == pytest.approx([f_mag, 0.0, 0.0], rel=2e-15, abs=0)

    right = rows["force_on_right"]
    assert right["wire_id"] == "wire_right"
    assert right["excluded_source_id"] == "wire_right"
    assert [c["source_id"] for c in right["external_contributions"]] == ["wire_left"]
    assert right["external_B_T"] == pytest.approx([0.0, b_mag, 0.0], rel=2e-15, abs=0)
    assert right["force_per_length_N_per_m"] == pytest.approx([-f_mag, 0.0, 0.0], rel=2e-15, abs=0)

    # Fresh-output protection: refusing overwrite of existing report file
    original = dest.read_bytes()
    assert main(["magnetic-field", str(EXAMPLE), "--output", str(dest)]) == 2
    assert dest.read_bytes() == original


def test_capabilities_lists_version_4():
    v4 = get_capabilities()["static_magnetic_field"]["version_4"]
    assert v4["kind"] == "static_magnetic_field"
    assert v4["required"] == ["model_version", "kind", "sources", "wire_force_observations"]
    assert v4["wire_force_observation"] == ["id", "wire_id", "axis_distance_m"]
    assert v4["units"] == "N/m"
    assert v4["example"] == "examples/magnetic/parallel_wires_force.json"


def test_antiparallel_repulsion_by_current_or_axis_reversal():
    f_mag = mu_0 * 5.0 * 5.0 / (2.0 * math.pi * 2.0)

    neg_current = packet()
    neg_current["sources"][1]["current_A"] = -5
    r1 = run(neg_current)
    rows1 = {r["id"]: r for r in r1["wire_force_observations"]}
    assert rows1["force_on_left"]["force_per_length_N_per_m"] == pytest.approx([-f_mag, 0.0, 0.0], rel=2e-15, abs=0)
    assert rows1["force_on_right"]["force_per_length_N_per_m"] == pytest.approx([f_mag, 0.0, 0.0], rel=2e-15, abs=0)

    rev_axis = packet()
    rev_axis["sources"][1]["axis_direction"] = [0, 0, -1]
    r2 = run(rev_axis)
    rows2 = {r["id"]: r for r in r2["wire_force_observations"]}
    assert rows2["force_on_left"]["force_per_length_N_per_m"] == pytest.approx([-f_mag, 0.0, 0.0], rel=2e-15, abs=0)
    assert rows2["force_on_right"]["force_per_length_N_per_m"] == pytest.approx([f_mag, 0.0, 0.0], rel=2e-15, abs=0)


def test_oblique_wire_nonuniform_composition_and_axis_distance():
    target_origin = (0.5, -1.0, 0.25)
    target_axis_raw = (1.0, 2.0, 2.0)  # norm = 3
    target_tangent = (1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0)
    target_current = -4.5

    ext_origin = (-1.5, 0.5, 0.0)
    ext_axis = (0.0, 1.0, -1.0)
    ext_current = 7.0
    uniform_B = (0.2, -0.3, 0.15)

    model = {
        "model_version": 4,
        "kind": "static_magnetic_field",
        "sources": [
            {
                "id": "target_wire",
                "type": "infinite_straight_wire",
                "origin_m": list(target_origin),
                "axis_direction": list(target_axis_raw),
                "current_A": target_current,
            },
            {
                "id": "skew_wire",
                "type": "infinite_straight_wire",
                "origin_m": list(ext_origin),
                "axis_direction": list(ext_axis),
                "current_A": ext_current,
            },
            {
                "id": "bg_field",
                "type": "uniform_magnetic_field",
                "B_T": list(uniform_B),
            },
        ],
        "wire_force_observations": [
            {"id": "obs_neg", "wire_id": "target_wire", "axis_distance_m": -3.0},
            {"id": "obs_pos", "wire_id": "target_wire", "axis_distance_m": 6.0},
        ],
    }

    report = run(model)
    assert report["status"] == "ok"
    rows = {r["id"]: r for r in report["wire_force_observations"]}

    for obs_id, s in [("obs_neg", -3.0), ("obs_pos", 6.0)]:
        row = rows[obs_id]
        pos = tuple(o + s * t for o, t in zip(target_origin, target_tangent))
        assert row["position_m"] == pytest.approx(list(pos), rel=1e-15, abs=0)
        assert row["tangent"] == pytest.approx(list(target_tangent), rel=1e-15, abs=0)
        b_wire = _wire_B_analytic(ext_origin, ext_axis, ext_current, pos)
        b_ext = tuple(bw + bu for bw, bu in zip(b_wire, uniform_B))
        f_expected = tuple(target_current * c for c in _cross(target_tangent, b_ext))
        assert row["external_B_T"] == pytest.approx(list(b_ext), rel=3e-15, abs=0)
        assert row["force_per_length_N_per_m"] == pytest.approx(list(f_expected), rel=3e-15, abs=0)

    # Local force per length differs at two points along a skew external field
    assert rows["obs_neg"]["force_per_length_N_per_m"] != rows["obs_pos"]["force_per_length_N_per_m"]


def test_single_wire_no_external_sources_yields_zero():
    model = {
        "model_version": 4,
        "kind": "static_magnetic_field",
        "sources": [
            {
                "id": "solo",
                "type": "infinite_straight_wire",
                "origin_m": [0, 0, 0],
                "axis_direction": [0, 0, 1],
                "current_A": 10,
            }
        ],
        "wire_force_observations": [
            {"id": "solo_obs", "wire_id": "solo", "axis_distance_m": 1.5}
        ],
    }
    report = run(model)
    assert report["status"] == "ok"
    row = report["wire_force_observations"][0]
    assert row["status"] == "ok"
    assert row["external_contributions"] == []
    assert row["external_B_status"] == "ok"
    assert row["external_B_T"] == [0.0, 0.0, 0.0]
    assert row["force_per_length_N_per_m"] == [0.0, 0.0, 0.0]


def test_zero_current_target_defined_and_undefined_external_field():
    defined = packet()
    defined["sources"][0]["current_A"] = 0
    r_ok = run(defined)
    assert r_ok["status"] == "ok"
    left = r_ok["wire_force_observations"][0]
    assert left["external_B_T"][1] != 0.0
    assert left["force_per_length_N_per_m"] == [0.0, 0.0, 0.0]

    intersecting = {
        "model_version": 4,
        "kind": "static_magnetic_field",
        "sources": [
            {
                "id": "target_zero",
                "type": "infinite_straight_wire",
                "origin_m": [0, 0, 0],
                "axis_direction": [1, 0, 0],
                "current_A": 0,
            },
            {
                "id": "crossing_wire",
                "type": "infinite_straight_wire",
                "origin_m": [0, 0, 0],
                "axis_direction": [0, 1, 0],
                "current_A": 3,
            },
        ],
        "wire_force_observations": [
            {"id": "at_intersection", "wire_id": "target_zero", "axis_distance_m": 0},
            {"id": "away_from_intersection", "wire_id": "target_zero", "axis_distance_m": 2},
        ],
    }
    r_part = run(intersecting)
    assert r_part["status"] == "partial"
    at_x, away = r_part["wire_force_observations"]
    assert at_x["status"] == "domain_error"
    assert at_x["external_B_T"] is None
    assert at_x["force_per_length_N_per_m"] is None
    assert away["status"] == "ok"
    assert away["force_per_length_N_per_m"] == [0.0, 0.0, 0.0]


def test_numerical_overflow_errors_and_cli_exit_code(tmp_path):
    overflow_total_B = {
        "model_version": 4,
        "kind": "static_magnetic_field",
        "sources": [
            {"id": "w", "type": "infinite_straight_wire", "origin_m": [0, 0, 0], "axis_direction": [0, 0, 1], "current_A": 1},
            {"id": "b1", "type": "uniform_magnetic_field", "B_T": [1e308, 0, 0]},
            {"id": "b2", "type": "uniform_magnetic_field", "B_T": [1e308, 0, 0]},
        ],
        "wire_force_observations": [{"id": "obs", "wire_id": "w", "axis_distance_m": 0}],
    }
    r1 = run(overflow_total_B)
    assert r1["status"] == "failed"
    row1 = r1["wire_force_observations"][0]
    assert row1["status"] == "numerical_error"
    assert row1["reason"] == "unrepresentable_external_field"
    assert row1["external_B_T"] is None
    assert row1["force_per_length_N_per_m"] is None

    overflow_force = {
        "model_version": 4,
        "kind": "static_magnetic_field",
        "sources": [
            {"id": "w", "type": "infinite_straight_wire", "origin_m": [0, 0, 0], "axis_direction": [0, 0, 1], "current_A": 1e3},
            {"id": "b1", "type": "uniform_magnetic_field", "B_T": [0, 1e307, 0]},
        ],
        "wire_force_observations": [{"id": "obs", "wire_id": "w", "axis_distance_m": 0}],
    }
    r2 = run(overflow_force)
    assert r2["status"] == "failed"
    row2 = r2["wire_force_observations"][0]
    assert row2["external_B_status"] == "ok"
    assert row2["status"] == "numerical_error"
    assert row2["reason"] == "unrepresentable_force_per_length"
    assert row2["force_per_length_N_per_m"] is None

    src_path = tmp_path / "failed_v4.json"
    src_path.write_text(json.dumps(overflow_force), encoding="utf-8")
    assert main(["magnetic-field", str(src_path)]) == 1


@pytest.mark.parametrize("change", [
    lambda m: m.update(kind="static_electromagnetic_field"),
    lambda m: m.pop("wire_force_observations"),
    lambda m: m.update(wire_force_observations=[]),
    lambda m: m.update(probes=[{"id": "p", "position_m": [0, 0, 0]}]),
    lambda m: m["wire_force_observations"][0].update(wire_id="missing_wire"),
    lambda m: (
        m["sources"].append({"id": "bg", "type": "uniform_magnetic_field", "B_T": [0, 0, 1]}),
        m["wire_force_observations"][0].update(wire_id="bg"),
    ),
    lambda m: m["wire_force_observations"][1].update(id="force_on_left"),
    lambda m: m["wire_force_observations"][0].update(axis_distance_m=True),
    lambda m: m["wire_force_observations"][0].update(axis_distance_m=1e5 + 1.0),
    lambda m: (
        m["sources"][0].update(origin_m=[10, 0, 0], axis_direction=[1, 0, 0]),
        m["wire_force_observations"][0].update(axis_distance_m=1e5),
    ),
    lambda m: m["wire_force_observations"][0].update(extra=1),
])
def test_schema_refusals(change):
    model = packet()
    change(model)
    with pytest.raises(ValueError):
        run(model)
