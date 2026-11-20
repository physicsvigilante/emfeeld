"""Actual VTK input events, signed 3D glyphs, and source-bound screenshots."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.constants import mu_0

from emfeeld.circular_loop_magnetism import CircularLoopState, axis_field, teaching_case
from emfeeld.circular_loop_view import CircularLoopLesson, save_snapshot, main


def _key(view, key):
    interactor = view.plot.iren.interactor
    interactor.SetKeySym(key)
    interactor.InvokeEvent("KeyPressEvent")


def _slider(widget, ratio):
    widget.GetRepresentation().SetValue(ratio)
    widget.InvokeEvent("EndInteractionEvent")
    return widget.GetRepresentation().GetValue()


def test_native_current_direction_reversal_zero_and_normal_fixed():
    initial = CircularLoopState(radius_m=.3, current_A=9, probe_z_m=.18,
                                normal_direction=(1, 2, 3))
    view = CircularLoopLesson(initial, off_screen=True, window_size=(960, 640))
    try:
        view.plot.show(auto_close=False, interactive=False)
        positive = view.current_arrow_direction.copy()
        normal = view.positive_normal_arrow_direction.copy()
        assert view.current_arrow_actor is not None
        assert view.field_arrow_actor is not None
        assert np.dot(positive, view.prepared.positive_current_tangent[0]) > 0
        assert np.dot(view.field_arrow_direction, normal) > 0
        _key(view, "n")
        assert view.state.current_A == -9
        assert np.array_equal(view.current_arrow_direction, -positive)
        assert np.dot(view.field_arrow_direction, normal) < 0
        assert np.array_equal(view.positive_normal_arrow_direction, normal)
        assert view.current_arrow_actor is not None
        _key(view, "k")
        assert view.state.current_A == 0
        assert view.current_arrow_actor is None
        assert view.field_arrow_actor is None
        assert view.probe_field_arrow_actor is None
        assert not np.any(view.prepared.field_probe_T)
        assert np.array_equal(view.positive_normal_arrow_direction, normal)
        _key(view, "p")
        assert view.state.current_A == 9
        assert view.current_arrow_actor is not None
        _key(view, "0")
        assert view.state == initial and view.show_values
    finally:
        view.plot.close()


def test_native_sliders_and_reveal_reuse_prepared(monkeypatch):
    initial = CircularLoopState(radius_m=.4, probe_z_m=.2, current_A=4)
    view = CircularLoopLesson(initial, off_screen=True, window_size=(1000, 680))
    try:
        view.plot.show(auto_close=False, interactive=False)
        assert view.z_slider.GetRepresentation().GetValue() == pytest.approx(.5)
        assert _slider(view.radius_slider, 1.5) == pytest.approx(1.5)
        assert view.state.radius_m == pytest.approx(.6)
        assert _slider(view.z_slider, -1.0) == pytest.approx(-1.0)
        assert view.state.probe_z_m == pytest.approx(-.4)
        assert view.prepared.report["probe_signed_B_T"] == pytest.approx(
            mu_0 * 4 * .6**2 / (2*(.6**2 + .4**2)**1.5))
        previous = view.prepared
        count = view.preparation_count
        import emfeeld.circular_loop_view as module
        monkeypatch.setattr(module, "prepare", lambda _: (_ for _ in ()).throw(
            AssertionError("display-only actions may not prepare physics")))
        _key(view, "v")
        assert not view.show_values
        view.plot.subplot(0, 0)
        view.plot.camera.azimuth += 22
        view.redraw()
        _key(view, "v")
        assert view.show_values
        assert view.prepared is previous and view.preparation_count == count
    finally:
        view.plot.close()


def test_native_three_comparison_presets_hide_then_reveal():
    original = CircularLoopState(current_A=5, radius_m=.25, probe_z_m=.3)
    view = CircularLoopLesson(original, off_screen=True, window_size=(960, 640))
    try:
        view.plot.show(auto_close=False, interactive=False)
        for key in ("1", "2", "3"):
            _key(view, key)
            assert view.state == teaching_case(original, key)
            assert view.state.probe_z_m == 0
            assert not view.show_values
            assert view.case_label == key
            _key(view, "v")
            assert view.show_values
        assert view.radius_slider.GetRepresentation().GetValue() == pytest.approx(2)
        assert view.display_state()["rendered_loop_radius_initial_R_units"] == pytest.approx(2)
        assert np.linalg.norm(view.prepared.loop_display_xyz, axis=1) == pytest.approx(
            np.full(original.samples_per_loop, 2.0))
        _key(view, "0")
        assert view.state == original
        assert view.radius_slider.GetRepresentation().GetValue() == pytest.approx(1)
        assert view.z_slider.GetRepresentation().GetValue() == pytest.approx(1.2)
    finally:
        view.plot.close()


def test_invalid_native_slider_input_is_atomic():
    original = CircularLoopState(radius_m=80, current_A=2)
    view = CircularLoopLesson(original, off_screen=True, window_size=(840, 620))
    try:
        view.plot.show(auto_close=False, interactive=False)
        before = view.prepared
        assert _slider(view.radius_slider, 2) == pytest.approx(1)
        assert view.state == original
        assert view.prepared is before
        assert "Control refused" in view.notice
        assert _slider(view.z_slider, 2) == pytest.approx(0)
        assert view.state == original
        assert view.prepared is before
    finally:
        view.plot.close()


@pytest.mark.parametrize("sign", (-1, 0, 1))
def test_real_screenshot_native_physics_and_integrity(tmp_path, sign):
    original = CircularLoopState(normal_direction=(1, 2, 3), centre_m=(.2, -.1, .15),
                                 current_A=7*sign, radius_m=.32, probe_z_m=-.18)
    view = CircularLoopLesson(original, off_screen=True, window_size=(940, 620))
    try:
        view.plot.show(auto_close=False, interactive=False)
        raw = (json.dumps(original.to_dict(), indent=2) + "\n").encode()
        report = save_snapshot(original, tmp_path/"scene", lesson=view,
                               source_bytes=raw)
        dest = tmp_path/"scene"
        from PIL import Image
        img = np.asarray(Image.open(dest/"view.png"))
        assert img.shape[:2] == (620, 940) and img.std() > 12
        # A native EndInteraction test alone can pass with *invisible* sliders.
        # Both must actually render in the lower-right information pane.
        h, w = img.shape[:2]
        controls = img[int(.60*h):int(.95*h), int(.64*w):int(.97*w), :3]
        assert np.count_nonzero(controls.mean(axis=2) < 150) > 250
        assert report["renderer"] == "PyVista real screenshot"
        assert report["physics"]["current_A"] == sign*7
        assert report["original_input_sha256"] == hashlib.sha256(raw).hexdigest()
        arrays = np.load(dest/"axis_samples.npz")
        assert np.array_equal(arrays["field_probe_T"], axis_field(original))
        assert np.array_equal(arrays["field_centre_T"], axis_field(original, 0))
        assert np.allclose(np.cross(view.prepared.positive_current_tangent[0],
                                    view.prepared.loop_display_xyz[0]),
                           -np.asarray(original.normal_direction), atol=2e-15)
        if sign == 0:
            assert not np.any(arrays["field_arrow_display_xyz"])
        else:
            assert np.sign(np.dot(arrays["field_probe_T"], original.normal_direction)) == sign
        for name, expected in json.loads((dest/"integrity.json").read_text())["files"].items():
            assert hashlib.sha256((dest/name).read_bytes()).hexdigest() == expected
        with pytest.raises((FileExistsError, ValueError)):
            save_snapshot(original, dest, lesson=view)
    finally:
        view.plot.close()


def test_headless_snapshot_from_case_without_pyvista(tmp_path):
    path = Path(__file__).parents[1]/"examples/lessons/circular_current_loop.json"
    assert main([str(path), "--case", "2", "--headless", str(tmp_path/"headless")]) == 0
    report = json.loads((tmp_path/"headless"/"report.json").read_text())
    assert report["authored_state"]["current_A"] == 5
    assert report["current_state"]["current_A"] == -5
    assert report["current_state"]["probe_z_m"] == 0.0
    assert report["physics"]["centre_signed_B_T"] < 0
    assert not (tmp_path/"headless"/"view.png").exists()
