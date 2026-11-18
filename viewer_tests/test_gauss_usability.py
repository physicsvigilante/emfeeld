"""Production rendering and resize checks for Issue48, no surrogate widgets."""
from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.gauss_lesson import GaussState, GaussianSphere, HeldCharge, measure
from emfeeld.gauss_view import GaussLesson, save_snapshot


@pytest.fixture
def view():
    state = GaussState(surface=GaussianSphere(), charges=(HeldCharge(1e-9, (.9999, 0, 0)),))
    v = GaussLesson(state, off_screen=True, resolution=6)
    v.plot.show(auto_close=False, interactive=False)
    try:
        yield v
    finally:
        v.plot.close()


def bounds(actor, renderer):
    box = [0., 0., 0., 0.]
    actor.GetBoundingBox(renderer, box)
    anchor = actor.GetPositionCoordinate().GetComputedViewportValue(renderer)
    return np.array(box) + np.array([anchor[0], anchor[0], anchor[1], anchor[1]])


@pytest.mark.parametrize('size', [(1440, 960), (840, 560)])
def test_native_resize_separates_annotations_and_preserves_physics(view, size):
    old = view.state
    report = view.report.copy()
    field = view.fields.copy()
    camera = np.asarray(view.plot.renderers[0].camera_position)
    # No redraw: exercises the actual render-window observer, not a helper call.
    view.plot.ren_win.SetSize(*size)
    view.plot.ren_win.Render()
    assert view.state == old and view.report == report
    np.testing.assert_array_equal(view.fields, field)
    np.testing.assert_array_equal(view.plot.renderers[0].camera_position, camera)
    assert tuple(view.display_state()['window_size_pixels']) == size
    left, right = view.plot.renderers[0], view.plot.renderers[1]
    rectangles = {}
    for name, (actor, _) in view._annotation_actors.items():
        ren = right if name in ('readout', 'sampling-caution') else left
        box = bounds(actor, ren)
        assert box[0] >= 0 and box[1] <= ren.GetSize()[0], (name, box, ren.GetSize())
        assert box[2] >= 0 and box[3] <= ren.GetSize()[1], (name, box, ren.GetSize())
        rectangles[name] = box
    assert rectangles['readout'][2] > rectangles['sampling-caution'][3]
    assert rectangles['sampling-caution'][2] > .49 * size[1]
    assert rectangles['instructions'][3] < view._scalar_bar.GetPosition()[1] * size[1]
    assert view.plot.renderer.axes_widget.GetViewport()[1] > .15


def test_real_slider_boundary_prediction_and_refinement_never_leave_stale_banner(view):
    assert view.caution_actor.GetVisibility()
    assert '0.9999' in view.sliders[0].GetRepresentation().GetTitleText()
    slider = view.sliders[0]
    slider.GetRepresentation().SetValue(1.0001)
    slider.InvokeEvent(vtkCommand.EndInteractionEvent)
    assert view.report['exact_total_N_m2_per_C'] == 0
    assert view.caution_actor.GetVisibility()
    assert '1.0001' in slider.GetRepresentation().GetTitleText()
    view.refine()
    assert view.caution_actor.GetVisibility()  # refinement is not a guarantee
    view.toggle_values()
    assert not view.caution_actor.GetVisibility()
    assert 'Exact total' not in view._annotation_actors['readout'][0].GetInput()
    view.toggle_values()
    view.set_coordinate(0, 1.)
    assert view.sampling_caution is None and not view.caution_actor.GetVisibility()
    assert view.report['exact_total_N_m2_per_C'] is None and view.fields is None
    view.set_coordinate(0, 0.)
    assert not view.caution_actor.GetVisibility()
    view.toggle_shape()
    assert view.sampling_caution is None and not view.caution_actor.GetVisibility()


def test_current_snapshot_retains_unaltered_results_and_visible_caution(view, tmp_path):
    view.set_coordinate(0, 1.0001)
    view.plot.window_size = (840, 560)
    raw = json.dumps(view.initial.to_dict(), indent=4).encode()
    out = tmp_path / 'changed-state'
    report = save_snapshot(view.initial, out, lesson=view, source_bytes=raw)
    assert report['physics'] == measure(view.state, order=view.order)
    assert report['display']['sampling_caution_visible'] is True
    assert report['display']['sampling_caution']['is_accuracy_certificate'] is False
    assert report['display']['window_size_pixels'] == [840, 560]
    assert report['original_input_equals_current_state'] is False
    assert (out / 'authored-input.json').read_bytes() == raw
    assert report['screenshot']['sha256'] == hashlib.sha256((out / 'view.png').read_bytes()).hexdigest()
    with np.load(out / 'surface_samples.npz') as a:
        np.testing.assert_array_equal(a['E_N_C'], view.fields)
    assert json.loads((out / 'outcome.json').read_text())['flux_available'] is True


def test_cube_readout_fits_above_widgets_at_minimum_window(view):
    view.set_coordinate(0, .5)
    view.toggle_shape()
    view.plot.window_size = (840, 560)
    view.plot.ren_win.Render()
    actor = view._annotation_actors['readout'][0]
    box = bounds(actor, view.plot.renderers[1])
    assert box[1] <= view.plot.renderers[1].GetSize()[0]
    assert box[2] > .49 * 560
