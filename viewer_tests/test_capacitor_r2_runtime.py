"""Reviewer F2/A1: genuine PyVista/VTK event dispatch on the repaired slider."""
import json

import numpy as np
import pytest

from emfeeld.capacitor_lesson import CapacitorState, measure
from emfeeld.capacitor_view import CapacitorLesson, save_snapshot


def _key(view, k):
    i = view.plot.iren.interactor
    i.SetKeySym(k)
    i.InvokeEvent('KeyPressEvent')


def _slider(view, i, value):
    widget = view.sliders[i]
    widget.GetRepresentation().SetValue(value)
    widget.InvokeEvent('EndInteractionEvent')  # real VTK widget callback, not set_kappa()
    return widget.GetRepresentation().GetValue()


def test_real_native_kappa_9_and_10_events_reset_screenshot_and_display_only(tmp_path, monkeypatch):
    initial = CapacitorState(charge_C=-2e-9, relative_permittivity=9)
    view = CapacitorLesson(initial, off_screen=True, window_size=(840, 560))
    try:
        view.plot.show(auto_close=False, interactive=False)
        rep = view.sliders[0].GetRepresentation()
        assert rep.GetMinimumValue() == 1 and rep.GetMaximumValue() == 10
        assert rep.GetValue() == 9
        assert _slider(view, 0, 10) == 10
        assert view.state.relative_permittivity == 10
        assert view.prepared.measurements == measure(view.state)
        assert view.preparation_count == 2
        assert view.preset_label is None
        assert _slider(view, 0, 9) == 9
        assert view.state.relative_permittivity == 9
        assert view.preparation_count == 3
        # Test the exact upper limit again at the saved current state.
        assert _slider(view, 0, 10) == 10
        raw = json.dumps(initial.to_dict(), indent=2).encode()
        receipt = save_snapshot(initial, tmp_path/'native-slider-k10',
                                lesson=view, source_bytes=raw)
        assert receipt['physics'] == measure(view.state)
        assert receipt['display']['original_and_current_states_distinct']
        assert receipt['screenshot']['sha256']
        assert np.std(__import__('PIL.Image',fromlist=['Image']).open(
            tmp_path/'native-slider-k10/view.png')) > 8
        _key(view, '0')
        assert view.state == initial
        assert rep.GetValue() == 9
        assert view.prepared.measurements == measure(initial)
        # Changing the view/reveal must use the same prepared physics.
        prior = view.prepared; count = view.preparation_count
        import emfeeld.capacitor_view as mod
        monkeypatch.setattr(mod, 'prepare', lambda _: (_ for _ in ()).throw(
            AssertionError('display action must not prepare physics')))
        _key(view, 'v')
        assert not view.show_values
        view.plot.camera.azimuth += 11
        view.redraw()
        _key(view, 'v')
        assert view.show_values
        assert view.prepared is prior and view.preparation_count == count
    finally:
        view.plot.close()


def test_native_refused_gap_slider_restores_knob_and_previous_physics():
    # Initial gap is admitted near d/sqrt(A)=0.1. A native slider end-event
    # towards 1.5 is rejected; the visible knob must return to the real value.
    initial = CapacitorState(area_m2=0.01, gap_m=0.0095, charge_C=1e-9)
    view = CapacitorLesson(initial, off_screen=True, window_size=(840, 560))
    try:
        view.plot.show(auto_close=False, interactive=False)
        old = view.prepared; count = view.preparation_count
        assert _slider(view, 1, 1.5) == 1.0
        assert view.state == initial and view.prepared is old
        assert view.preparation_count == count
        assert 'Control refused:' in view.notice
        assert _slider(view, 1, 0.9) == pytest.approx(0.9)
        assert view.preparation_count == count + 1
        assert view.state.gap_m == pytest.approx(initial.gap_m * 0.9)
        assert view.prepared.measurements == measure(view.state)
    finally:
        view.plot.close()
