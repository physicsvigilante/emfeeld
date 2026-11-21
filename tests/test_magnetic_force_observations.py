import json
import math
from pathlib import Path
import sys

import pytest
from scipy.constants import c, mu_0

from emfeeld.cli import main
from emfeeld.magnetic_probes import evaluate


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/magnetic/test_charge_force.json"


def model():
    return json.loads(EXAMPLE.read_bytes())


def run(packet):
    return evaluate(json.dumps(packet).encode())


def test_composed_field_and_charge_reversal_cli(capsys):
    assert main(["magnetic-field", str(EXAMPLE)]) == 0
    report = json.loads(capsys.readouterr().out)
    pos, neg = report["force_observations"]
    expected = [0., -2e-9, 1e-3 * mu_0 * 5 / (2*math.pi)]
    assert pos["force_N"] == pytest.approx(expected, rel=3e-15, abs=0)
    assert neg["force_N"] == pytest.approx([-x for x in expected], rel=3e-15, abs=0)
    assert pos["probe_id"] == neg["probe_id"] == "east"


@pytest.mark.parametrize("charge,velocity", [(3, [0, 0, 5]), (0, [1, 2, 3]), (3, [0, 0, 0])])
def test_defined_zero_forces(charge, velocity):
    packet = model()
    packet["sources"].pop(0)
    packet["force_observations"][0].update(charge_C=charge, velocity_m_s=velocity)
    assert run(packet)["force_observations"][0]["force_N"] == [0, 0, 0]


def test_singular_force_keeps_other_reference_available():
    packet = model()
    packet["probes"].append({"id": "axis", "position_m": [0, 0, 5]})
    packet["probes"].reverse()
    packet["force_observations"][0].update(probe_id="axis", charge_C=0)
    report = run(packet)
    bad, good = report["force_observations"]
    assert report["status"] == "partial"
    assert bad["status"] == "domain_error" and bad["force_N"] is None
    assert good["status"] == "ok" and good["probe_id"] == "east"


def test_force_rescales_before_conversion_and_preserves_unaffected_requests():
    packet = model()
    packet["sources"] = [dict(id="bias", type="uniform_magnetic_field", B_T=[0, 0, sys.float_info.max])]
    pos, neg = packet["force_observations"]
    pos.update(charge_C=.125, velocity_m_s=[2, 0, 0])
    neg.update(charge_C=1, velocity_m_s=[2, 0, 0])
    report = run(packet)
    a, b = report["force_observations"]
    assert report["status"] == "partial"
    assert a["force_N"] == [0, -sys.float_info.max / 4, 0]
    assert b["reason"] == "unrepresentable_force" and b["force_N"] is None


@pytest.mark.parametrize("change", [
    lambda p: p.update(model_version=1), lambda p: p.pop("force_observations"),
    lambda p: p.update(force_observations=[]),
    lambda p: p["force_observations"][0].update(id="negative"),
    lambda p: p["force_observations"][0].update(probe_id="missing"),
    lambda p: p["force_observations"][0].update(charge_C=True),
    lambda p: p["force_observations"][0].update(velocity_m_s=[0, c, 0]),
    lambda p: p["force_observations"][0].update(velocity_m_s=[.8*c, .8*c, 0]),
])
def test_invalid_requests_are_rejected(change):
    packet = model()
    change(packet)
    with pytest.raises(ValueError):
        run(packet)


@pytest.mark.parametrize("velocity,accepted", [
    ([math.nextafter(c, 0.), 5., 0.], True),
    ([0., c, 0.], False),
    ([math.nextafter(c, 0.), 6., 0.], False),
])
def test_speed_boundary_before_square_root_rounding(velocity, accepted):
    packet = model()
    packet["force_observations"][0]["velocity_m_s"] = velocity
    if accepted:
        assert run(packet)["status"] == "ok"
    else:
        with pytest.raises(ValueError, match="speed"):
            run(packet)
