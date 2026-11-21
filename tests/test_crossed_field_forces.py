import json
from pathlib import Path

import pytest
from scipy.constants import epsilon_0, mu_0
import math

from emfeeld.cli import main
from emfeeld.magnetic_probes import evaluate


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/magnetic/velocity_selector.json"


def packet():
    return json.loads(EXAMPLE.read_bytes())


def run(model):
    return evaluate(json.dumps(model).encode())


def test_selector_through_cli(tmp_path, capsys):
    dest = tmp_path / "new.json"
    assert main(["magnetic-field", str(EXAMPLE), "--output", str(dest)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads(dest.read_bytes())
    assert report["electric_probes"][0]["total_E_N_C"] == [0, 2, 0]
    assert report["probes"][0]["total_B_T"] == [0, 0, .5]
    rows = {r["id"]: r for r in report["force_observations"]}
    for name, y in [("slow", 1e-6), ("selected", 0), ("fast", -1e-6),
                    ("negative", 0), ("parallel_component", 0)]:
        assert rows[name]["force_N"] == pytest.approx([0, y, 0], abs=0)
    assert rows["selected"]["electric"]["force_N"] == [0, 2e-6, 0]
    assert rows["selected"]["magnetic"]["force_N"] == [0, -2e-6, 0]
    assert rows["negative"]["electric"]["force_N"] == [0, -2e-6, 0]
    assert rows["negative"]["magnetic"]["force_N"] == [0, 2e-6, 0]


def test_nonuniform_sources_at_same_world_point_and_independent_failures():
    model = packet()
    model["electric_sources"] = [dict(id="charge", type="point", center_m=[0, 1, 0], charge_C=2e-9)]
    model["sources"] = [dict(id="wire", type="infinite_straight_wire", origin_m=[0, 0, 0],
                             axis_direction=[1, 0, 0], current_A=3)]
    model["probes"] = [dict(id=i, position_m=p) for i, p in
                       [("valid", [0, 3, 0]), ("on_wire", [0, 0, 0]), ("on_charge", [0, 1, 0])]]
    model["force_observations"] = [dict(id=p["id"], probe_id=p["id"], charge_C=1, velocity_m_s=[2, 0, 0])
                                   for p in model["probes"]]
    report = run(model)
    good, wire, charge = report["force_observations"]
    e = 2e-9 / (16 * math.pi * epsilon_0)
    b = mu_0 * 3 / (2 * math.pi * 3)
    assert good["force_N"] == pytest.approx([0, e - 2*b, 0], rel=3e-15, abs=0)
    assert report["status"] == "partial"
    for failed, missing, available in [(wire, "magnetic", "electric"), (charge, "electric", "magnetic")]:
        assert failed["status"] == "domain_error" and failed["force_N"] is None
        assert failed[missing]["force_N"] is None
        assert failed[available]["status"] == "ok" and failed[available]["force_N"] is not None


@pytest.mark.parametrize("change", [
    lambda m: m.update(model_version=2), lambda m: m.pop("electric_sources"),
    lambda m: m.update(kind="static_magnetic_field"), lambda m: m.update(electric_sources=[]),
    lambda m: m["electric_sources"][0].update(id="magnet"),
    lambda m: m["electric_sources"][0].update(field_N_C=[True, 0, 0]),
    lambda m: m["electric_sources"][0].update(type="gravity"),
])
def test_schema_refusals(change):
    model = packet()
    change(model)
    with pytest.raises(ValueError):
        run(model)


@pytest.mark.parametrize("charge, center", [
    (0.0, [1e200, 0, 0]),
    (1e-9, [1, 1e-200, 0]),
])
def test_point_field_with_mixed_coordinate_scales(charge, center):
    model = packet()
    model["electric_sources"] = [dict(id="point", type="point", center_m=center, charge_C=charge)]
    report = run(model)
    assert report["status"] == "ok"
    expected = [-charge / (4 * math.pi * epsilon_0) * x for x in center]
    assert report["electric_probes"][0]["total_E_N_C"] == pytest.approx(expected, rel=2e-15, abs=0)
    if charge == 0:
        for row in report["force_observations"]:
            assert row["force_N"] == row["magnetic"]["force_N"]
