"""R2-01: requested alignment is not exact rounded-coordinate equilibrium."""
from dataclasses import replace
import json

import numpy as np
import pytest
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.dipole_lesson import DipoleState, measure
from emfeeld.dipole_view import DipoleLesson, save_snapshot


def slider(view, index, value):
    widget = view.sliders[index]
    widget.GetRepresentation().SetValue(value)
    widget.InvokeEvent(vtkCommand.EndInteractionEvent)


def key(view, value):
    interactor = view.plot.iren.interactor
    interactor.SetKeyEventInformation(0, 0, value, 0, value)
    interactor.InvokeEvent("KeyPressEvent")


def noncardinal(view):
    slider(view, 2, 75.)
    slider(view, 3, 40.)
    key(view, "b")


@pytest.mark.parametrize("size", [(840, 560), (1440, 960)])
def test_native_generic_field_presets_retain_residue_without_strong_cue(size, tmp_path):
    view = DipoleLesson(DipoleState(), off_screen=True, window_size=size)
    try:
        view.plot.show(auto_close=False, interactive=False)
        noncardinal(view)
        for button, target in [("1", "parallel"), ("3", "antiparallel")]:
            key(view, button)
            raw = measure(view.state)
            assert any(raw["torque_N_m"])  # The represented input has a real residual.
            assert raw["equilibrium"] == "not_equilibrium"
            assert view.report == raw
            assert view.work["status"] == "available"
            assert "torque" not in view.glyph_records
            assert "rotation_cue" not in view.glyph_records
            assert view.rotation_cue_mesh is None and view.plane_mesh is None
            note = view._annotations["preset-note"][0].GetInput()
            assert target in note and "rounded" in note and "residual" in note
            assert "not exact equilibrium" in view._annotations["readout"][0].GetInput()
            report = save_snapshot(view.state, tmp_path / f"preset-{button}", lesson=view)
            assert report["physics"] == raw
            display = report["display"]["preset_alignment"]
            assert display["requested"] == target
            assert display["status"] == "rounded_coordinates"
            assert display["torque_cues_suppressed"] is True
            assert display["residual_torque_N_m"] == raw["torque_N_m"]
            with np.load(tmp_path / f"preset-{button}" / "measurements.npz") as arrays:
                np.testing.assert_array_equal(arrays["torque_N_m"], raw["torque_N_m"])
            # Check actual text extent, not just assigned font sizes.
            for name in ("preset-note", "readout"):
                actor = view._annotations[name][0]
                renderer = view.plot.renderers[int(name == "readout")]
                box = [0., 0., 0., 0.]
                actor.GetBoundingBox(renderer, box)
                x, y = actor.GetPositionCoordinate().GetComputedViewportValue(renderer)
                assert 0 <= box[0] + x <= box[1] + x <= renderer.GetSize()[0]
                assert 0 <= box[2] + y <= box[3] + y <= renderer.GetSize()[1]
    finally:
        view.plot.close()


@pytest.mark.parametrize("sign", [-1, 1])
def test_authored_small_signed_torque_has_no_preset_suppression(sign):
    state = DipoleState(charge_C=1e-30, positive_position_m=(.5, sign*1e-20, 0),
                        negative_position_m=(-.5, 0, 0), external_field_N_C=(1., 0., 0.))
    view = DipoleLesson(state, off_screen=True, window_size=(840, 560))
    try:
        assert view.report == measure(state)
        assert np.sign(view.report["torque_N_m"][2]) == -sign
        assert "torque" in view.glyph_records and "rotation_cue" in view.glyph_records
        assert view.display_state()["preset_alignment"] is None
    finally:
        view.plot.close()


def test_alignment_provenance_survives_view_only_controls_not_new_geometry(tmp_path):
    view = DipoleLesson(DipoleState(), off_screen=True, window_size=(840, 560))
    try:
        view.plot.show(auto_close=False, interactive=False)
        noncardinal(view)
        key(view, "1")
        raw = view.report.copy()
        key(view, "v")
        assert view._annotations["preset-note"][0].GetInput() == ""
        assert view.report == raw
        key(view, "v")
        key(view, "b")
        key(view, "o")  # Origin does not change the preset orientation.
        assert view.display_state()["preset_alignment"]["torque_cues_suppressed"]
        with pytest.raises(ValueError):
            view.set_charge(-1)
        assert view.display_state()["preset_alignment"]["torque_cues_suppressed"]
        original = view.state
        # Identical coordinates authored from scratch have no known preset origin.
        authored = DipoleLesson(original, off_screen=True, window_size=(840, 560))
        try:
            assert authored.report == view.report
            assert "torque" in authored.glyph_records
            assert authored.display_state()["preset_alignment"] is None
        finally:
            authored.plot.close()
        slider(view, 0, 74.)
        assert view.display_state()["preset_alignment"] is None
        assert "torque" in view.glyph_records
        key(view, "1")
        slider(view, 3, 43.)
        assert view.display_state()["preset_alignment"] is None
        assert "torque" in view.glyph_records
        key(view, "0")
        assert view.display_state()["preset_alignment"] is None
    finally:
        view.plot.close()


def test_exact_cardinal_and_zero_cases_are_not_rounded_equilibria():
    view = DipoleLesson(DipoleState(positive_position_m=(.5, 0, 0),
        negative_position_m=(-.5, 0, 0), external_field_N_C=(1., 0, 0)),
        off_screen=True, window_size=(840, 560))
    try:
        for button, word in [("1", "stable_parallel"), ("3", "unstable_antiparallel")]:
            key(view, button)
            assert view.report["equilibrium"] == word
            assert not any(view.report["torque_N_m"])
            assert view.display_state()["preset_alignment"]["status"] == "exact_equilibrium"
            assert view._annotations["preset-note"][0].GetInput() == ""
        view.set_charge(0)
        assert view.report["equilibrium"] == "no_preferred_orientation"
        assert view.display_state()["preset_alignment"] is None
        view.set_field_factor(0)
        assert view.report["angle_deg"] is None
        assert "torque" not in view.glyph_records
    finally:
        view.plot.close()
