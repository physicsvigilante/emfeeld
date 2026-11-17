"""Analytical, same-author acceptance checks for the uniform-field demonstration.

References are computed without importing engine field laws or integrator.
"""
from copy import deepcopy
import math
from pathlib import Path

from emfeeld.observations import load_packet, run_packet

PACKET = Path(__file__).resolve().parents[1] / "examples/physics_demonstrations/uniform_electric.json"


def analytic_reference(packet):
    scene = packet["scene"]
    source = scene["sources"][0]
    body = scene["particles"][0]
    electric = source["field_N_C"]
    origin = source["origin_m"]
    start = body["position_m"]
    velocity = body["velocity_m_s"]
    mass, charge = body["mass_kg"], body["charge_C"]
    acceleration = [charge * e / mass for e in electric]

    def state(t):
        position = [x + u * t + 0.5 * a * t * t
                    for x, u, a in zip(start, velocity, acceleration)]
        speed = [u + a * t for u, a in zip(velocity, acceleration)]
        kinetic = 0.5 * mass * sum(v*v for v in speed)
        potential = -charge * sum(e*(x-o) for e, x, o in zip(electric, position, origin))
        return {"position": position, "velocity": speed,
                "kinetic_energy": kinetic, "potential_energy": potential,
                "total_energy": kinetic + potential}

    return state


def assert_agrees(packet):
    report = run_packet(packet)
    assert report["status"] == "ok"
    assert report["counts"]["requests"] == len(packet["observations"])
    rows = {row["id"]: row for row in report["results"]}
    assert len(rows) == len(packet["observations"])
    assert all(row["status"] == "ok" for row in rows.values())
    assert rows["field_initial"]["unit"] == "N/C"
    assert rows["potential_initial"]["unit"] == "V"
    assert rows["field_initial"]["value"] == [3, 0, 0]
    assert math.isclose(rows["potential_initial"]["value"], -0.6, abs_tol=1e-12)
    reference = analytic_reference(packet)
    units = {"position": "m", "velocity": "m/s", "kinetic_energy": "J",
             "potential_energy": "J", "total_energy": "J"}
    energies = []
    for index in (0, 20, 40):
        t = index * packet["scene"]["duration_s"] / (packet["scene"]["samples"] - 1)
        expected = reference(t)
        for quantity, unit in units.items():
            row = rows[f"{quantity}_{index}"]
            assert row["sample_index"] == index
            assert math.isclose(row["time_s"], t, rel_tol=0, abs_tol=1e-14)
            assert row["unit"] == unit
            actual = row["value"]
            target = expected[quantity]
            if isinstance(target, list):
                assert len(actual) == len(target)
                assert all(math.isclose(a, b, rel_tol=0, abs_tol=2e-8)
                           for a, b in zip(actual, target))
            else:
                assert math.isclose(actual, target, rel_tol=0, abs_tol=5e-10)
        energies.append(rows[f"total_energy_{index}"]["value"])
    assert max(energies) - min(energies) <= 5e-10
    assert report["trajectory_runs"]["0"]["status"] == "ok"


def test_uniform_electric_field_analytic_prediction():
    assert_agrees(load_packet(PACKET))


def test_wrong_charge_reference_does_not_pass():
    packet = deepcopy(load_packet(PACKET))
    # Run remains physically valid, but the original analytic prediction
    # must detect a perturbed charge; never 'fix' by relaxing the threshold.
    reference = analytic_reference(load_packet(PACKET))(4)["position"][0]
    packet["scene"]["particles"][0]["charge_C"] *= 2
    changed = run_packet(packet)
    row = next(row for row in changed["results"] if row["id"] == "position_40")
    assert row["status"] == "ok"
    assert abs(row["value"][0] - reference) > 1e-3

def test_exact_published_packet_replay(tmp_path):
    """Freeze original packet bytes and exercise the established replay evidence path."""
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "physics_demo_replay", root / "tools/replay_packets.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    manifest_path = root / "verification/physics_demonstration_v1.json"
    manifest = load_packet(manifest_path)
    assert len(manifest["cases"]) == 1
    case = manifest["cases"][0]
    assert replay.digest(PACKET.read_bytes()) == case["sha256"]
    output = tmp_path / "sealed_replay"
    result = replay.replay(manifest_path, output, root=root)
    assert result["passed"], result["cases"]
    assert len(result["cases"][0]["checks"]) == len(case["checks"]) == 64
    assert (output / "uniform_electric_v1/input.json").read_bytes() == PACKET.read_bytes()
    assert (output / "uniform_electric_v1/result.json").is_file()
    assert (output / "summary.json").is_file()
