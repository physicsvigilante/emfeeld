import hashlib
import json
import math
from pathlib import Path
import sys

import pytest
from scipy.constants import mu_0

from emfeeld.cli import main
from emfeeld.magnetic_probes import evaluate


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/magnetic/two_wires.json"


def model():
    return json.loads(EXAMPLE.read_bytes())


def run(packet):
    return evaluate(json.dumps(packet).encode())


def bias(ident, vector):
    return {"type": "uniform_magnetic_field", "id": ident, "B_T": vector}


def test_example_cli_contributions_and_fresh_file(tmp_path, capsys):
    dest = tmp_path / "new" / "result.json"
    assert main(["magnetic-field", str(EXAMPLE), "--output", str(dest)]) == 1
    text = capsys.readouterr().out
    assert dest.read_text() == text
    report = json.loads(text)
    assert report["input_sha256"] == hashlib.sha256(EXAMPLE.read_bytes()).hexdigest()
    assert report["status"] == "partial"
    mid, outside, singular = report["probes"]
    ref = mu_0 * 5 / (2 * math.pi)
    assert [c["source_id"] for c in mid["contributions"]] == ["left", "right"]
    for c, y in zip(mid["contributions"], [ref, -ref]):
        assert c["B_T"] == pytest.approx([0, y, 0], rel=2e-15, abs=0)
    assert mid["total_B_T"] == [0, 0, 0]
    assert outside["total_B_T"] == pytest.approx([0, .75 * ref, 0], rel=2e-15, abs=0)
    assert singular["total_B_T"] is None
    assert singular["contributions"][0] == dict(source_id="left", status="domain_error",
        B_T=None, reason="on_or_unresolved_near_wire_axis")
    assert singular["contributions"][1]["B_T"] == pytest.approx([0, -.5 * ref, 0], abs=0)
    assert main(["magnetic-field", str(EXAMPLE), "--output", str(dest)]) == 2
    assert dest.read_text() == text


def test_reversal_bias_and_zero_current_wire():
    packet = model()
    packet["sources"][1]["current_A"] *= -1
    packet["sources"].append(bias("bias", [0, 0, 2e-6]))
    mid, _, singular = run(packet)["probes"]
    assert mid["total_B_T"] == pytest.approx([0, mu_0 * 5 / math.pi, 2e-6], abs=0)
    assert singular["total_B_T"] is None
    packet["sources"][0]["current_A"] = 0
    result = run(packet)
    assert result["status"] == "ok"
    assert result["probes"][2]["contributions"][0]["B_T"] == [0, 0, 0]


def test_translated_tilted_wire_with_uniform_field():
    packet = model()
    wire = dict(packet["sources"][0], origin_m=[7, -3, 11], axis_direction=[0, 3, 4], current_A=-7)
    packet["sources"] = [bias("uniform", [1e-6, -2e-6, 3e-6]), wire]
    packet["probes"] = [dict(id="p", position_m=[9, 0, 15])]
    # The point is two metres along +x from a point on the line.
    scale = -7 * mu_0 / (4 * math.pi)
    assert run(packet)["probes"][0]["total_B_T"] == pytest.approx(
        [1e-6, -2e-6 + .8 * scale, 3e-6 - .6 * scale], rel=3e-15, abs=0)


@pytest.mark.parametrize("offset", [4e-162, 1e-163, 1e-300])
def test_resolved_tiny_wire_offset(offset):
    packet = model()
    packet["sources"] = [dict(packet["sources"][0], origin_m=[0, 0, 0])]
    packet["probes"] = [dict(id="near", position_m=[offset, 0, 0])]
    expected = (5 * mu_0 / (2 * math.pi)) / offset
    assert run(packet)["probes"][0]["total_B_T"] == pytest.approx([0, expected, 0], rel=2e-15, abs=0)


def test_cli_success_and_all_probes_undefined(tmp_path, capsys):
    packet = model()
    path = tmp_path / "model.json"
    for index, status, code in ((0, "ok", 0), (2, "failed", 1)):
        path.write_text(json.dumps(dict(packet, probes=[packet["probes"][index]])))
        assert main(["magnetic-field", str(path)]) == code
        assert json.loads(capsys.readouterr().out)["status"] == status


def test_tiny_wire_axis_component_survives_cancellation_of_large_fields():
    packet = model()
    for wire, sign in zip(packet["sources"], [1, -1]):
        wire.update(origin_m=[0, 0, 0], axis_direction=[sign, 1e-315, 0], current_A=1e-6)
    packet["probes"] = [dict(id="close", position_m=[0, 0, 1e-320])]
    result = run(packet)["probes"][0]
    # Both fields have +x components; the opposite y components cancel.
    expected_x = (1e-315 / 1e-320) * (mu_0 * 1e-6 / math.pi)
    assert result["total_B_T"] == pytest.approx([expected_x, 0, 0], rel=3e-15, abs=0)


def test_tiny_determinant_survives_rescaling_to_tesla():
    packet = model()
    for wire, sign in zip(packet["sources"], [1, -1]):
        wire.update(origin_m=[0, 0, 0], axis_direction=[sign, 0, 1e-180], current_A=1)
    packet["probes"] = [dict(id="p", position_m=[0, 1e-308, 1e-154])]
    # |u x d|² rounds to (1e-154)² at the precision of this check.
    expected_x = -(mu_0 / math.pi) * (1e-308 / 1e-154 / 1e-154) * 1e-180
    assert run(packet)["probes"][0]["total_B_T"] == pytest.approx([expected_x, 0, 0], rel=3e-15, abs=0)


def test_component_sum_recovers_cancellation_and_reports_true_overflow():
    packet = model()
    m = sys.float_info.max
    packet["sources"] = [bias("a", [m, 0, 1]), bias("b", [m, 2, 1]), bias("c", [-m, 0, -2])]
    for sources in (packet["sources"][:], list(reversed(packet["sources"]))):
        packet["sources"] = sources
        assert run(packet)["probes"][0]["total_B_T"] == [m, 2, 0]
    packet["sources"] = [bias("a", [m, 0, 0]), bias("b", [m, 0, 0])]
    report = run(packet)
    assert report["status"] == "failed"
    assert all(p["total_B_T"] is None and p["reason"] == "unrepresentable_total_field"
               for p in report["probes"])


@pytest.mark.parametrize("change", [
    lambda p: p.update(model_version=True), lambda p: p.update(kind="gravity"),
    lambda p: p.update(sources=[]), lambda p: p.update(probes=[]),
    lambda p: p["sources"][0].update(id="right"), lambda p: p["probes"][0].update(id="outside"),
    lambda p: p["sources"][0].update(type="circular_loop"), lambda p: p["sources"][0].update(foo=1),
    lambda p: p["sources"][0].update(axis_direction=[0, 0, 0]),
    lambda p: p["sources"][0].update(current_A="5"), lambda p: p["probes"][0].update(position_m=[0, True, 0]),
    lambda p: p["probes"][0].update(position_m=[0, 1e6, 0]),
])
def test_invalid_model_refused(change):
    packet = model()
    change(packet)
    with pytest.raises(ValueError):
        run(packet)


@pytest.mark.parametrize("token", ["1e-9999", "1e-99999999999999999999", "1e999",
                                   "NaN", "Infinity", '5,"current_A":4'])
def test_invalid_numeric_tokens_and_duplicate_keys(token):
    raw = EXAMPLE.read_text().replace('"current_A": 5', '"current_A": ' + token)
    with pytest.raises(ValueError):
        evaluate(raw.encode())


def test_extreme_exponent_cli_refusal_and_exact_zero(tmp_path, capsys):
    src = tmp_path / "model.json"
    for significand, code in (("1", 2), ("0", 0)):
        src.write_text(EXAMPLE.read_text().replace('"current_A": 5',
            f'"current_A": {significand}e-99999999999999999999'))
        assert main(["magnetic-field", str(src)]) == code
        result = capsys.readouterr()
        if code == 2:
            assert not result.out and "not representable" in result.err
        else:
            assert json.loads(result.out)["status"] == "ok"


def test_invalid_input_and_protected_outputs(tmp_path):
    src = tmp_path / "model.json"
    src.write_bytes(EXAMPLE.read_bytes())
    assert main(["magnetic-field", str(src), "--output", str(src)]) == 2
    assert src.read_bytes() == EXAMPLE.read_bytes()
    (tmp_path / "integrity.json").write_text("{}")
    dest = tmp_path / "new" / "result.json"
    assert main(["magnetic-field", str(src), "--output", str(dest)]) == 2
    assert not dest.parent.exists()
    src.write_text("{}")
    assert main(["magnetic-field", str(src)]) == 2
