"""Original source-bound 3D circular-loop scenes with native event validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import traceback

import numpy as np
from scipy.constants import mu_0

from emfeeld.circular_loop_magnetism import CircularLoopState, load_lesson, teaching_case
from emfeeld.circular_loop_view import CircularLoopLesson, save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def _key(view, key):
    interactor = view.plot.iren.interactor
    interactor.SetKeySym(key)
    interactor.InvokeEvent("KeyPressEvent")


def qualify(target):
    root = Path(target)
    protect_saved_evidence(root, new_directory=True)
    root.mkdir(parents=True, exist_ok=False)
    (root/"started.json").write_text('{"completed":false}\n', encoding="utf-8")
    source = Path(__file__).resolve().parents[1]/"examples/lessons/circular_current_loop.json"
    raw = source.read_bytes()
    initial = load_lesson(source)
    records = []
    view = None

    def capture(label, authored=initial, source_bytes=raw):
        report = save_snapshot(authored, root/label, lesson=view, source_bytes=source_bytes)
        png = root/label/"view.png"
        assert png.is_file() and png.stat().st_size > 3000
        for file_name, expected in json.loads(
                (root/label/"integrity.json").read_text())["files"].items():
            assert hashlib.sha256((root/label/file_name).read_bytes()).hexdigest() == expected
        assert report["physics"]["current_A"] == view.state.current_A
        assert report["current_state"] == view.state.to_dict()
        independent = mu_0 * view.state.current_A * view.state.radius_m**2 / (
            2 * math.hypot(view.state.radius_m, view.state.probe_z_m)**3)
        assert math.isclose(report["physics"]["probe_signed_B_T"], independent,
                            rel_tol=1e-13, abs_tol=0)
        records.append({"label": label, "png": label+"/view.png",
                        "sha256": hashlib.sha256(png.read_bytes()).hexdigest()})
        return report

    try:
        view = CircularLoopLesson(initial, off_screen=True, window_size=(1200, 760))
        view.plot.show(auto_close=False, interactive=False)
        for key, label in (("1", "centre_positive"), ("2", "centre_reverse"),
                           ("3", "centre_double_radius")):
            _key(view, key)
            assert view.state == teaching_case(initial, key)
            assert view.state.probe_z_m == 0
            assert not view.show_values
            capture(label+"_prediction")
            _key(view, "v")
            assert view.show_values
            capture(label)
        # Genuine key events: zero current removes both current and B arrows,
        # while the +normal arrow remains present, unchanged in orientation.
        _key(view, "0")
        normal = view.positive_normal_arrow_direction.copy()
        _key(view, "k")
        assert view.current_arrow_actor is None and view.field_arrow_actor is None
        assert np.array_equal(normal, view.positive_normal_arrow_direction)
        capture("zero_current")
        _key(view, "0")
        # Genuine VTK end-interaction events, not direct helper calls.
        radius_slider = view.radius_slider
        z_slider = view.z_slider
        radius_slider.GetRepresentation().SetValue(1.6)
        radius_slider.InvokeEvent("EndInteractionEvent")
        z_slider.GetRepresentation().SetValue(-1.2)
        z_slider.InvokeEvent("EndInteractionEvent")
        assert math.isclose(view.state.radius_m, initial.radius_m*1.6, rel_tol=1e-14)
        assert math.isclose(view.state.probe_z_m, -initial.radius_m*1.2, rel_tol=1e-14)
        receipt = capture("native_sliders_offset_probe")
        assert receipt["display"]["original_and_current_states_distinct"]
        assert receipt["display"]["probe_B_arrow_present"]

        # Rotated physical geometry is distinct from orbiting the camera.
        view.plot.close()
        rotated = CircularLoopState(centre_m=(.3, -.2, .15),
                                    normal_direction=(1, 2, 3),
                                    current_A=-8, radius_m=.31,
                                    probe_z_m=.23, samples_per_loop=72)
        rotated_raw = (json.dumps(rotated.to_dict(), sort_keys=True) + "\n").encode()
        view = CircularLoopLesson(rotated, off_screen=True, window_size=(1100, 720))
        view.plot.show(auto_close=False, interactive=False)
        assert np.dot(view.prepared.field_probe_T, rotated.normal_direction) < 0
        capture("rotated_axis_reverse", authored=rotated, source_bytes=rotated_raw)
        outcome = {"status": "PASS", "real_pyvista": True, "cases": records,
                   "scope": "single ideal circular loop, axis field only",
                   "human_classroom_efficacy": "not_evaluated"}
        (root/"outcome.json").write_text(json.dumps(outcome, indent=2, sort_keys=True)+"\n")
        print(json.dumps({"status": "PASS", "case_count": len(records)}))
        return outcome
    except Exception:
        (root/"outcome.json").write_text(json.dumps({
            "status": "FAIL", "cases": records,
            "traceback": traceback.format_exc()}, indent=2)+"\n")
        raise
    finally:
        if view is not None:
            view.plot.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    qualify(p.parse_args().output)
