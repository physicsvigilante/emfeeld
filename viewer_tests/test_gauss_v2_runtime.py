"""Real PyVista events and meshes for the renderer-neutral Gauss pilot."""
from dataclasses import replace
import json

import numpy as np
import pyvista as pv
import pytest
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.gauss_lesson import GaussState, GaussianCube, GaussianSphere, HeldCharge, measure
from emfeeld.gauss_presentation import FACE_NAMES, build_surface
from emfeeld.gauss_view import GaussLesson, save_snapshot


def key(view, value):
    native = view.plot.iren.interactor
    native.SetKeySym(value)
    native.InvokeEvent('KeyPressEvent')


@pytest.fixture
def view():
    lesson = GaussLesson(GaussState(), off_screen=True, resolution=6)
    lesson.plot.show(auto_close=False, interactive=False)
    try: yield lesson
    finally: lesson.plot.close()


def test_display_only_real_events_never_evaluate_physics(view, monkeypatch):
    import emfeeld.gauss_presentation as module
    before, state, count = view.presentation, view.state, view._presentation_cache.build_count
    def forbidden(*a, **k): raise AssertionError('display action evaluated physics')
    monkeypatch.setattr(module, 'measure', forbidden)
    monkeypatch.setattr(module._HeldCoulombField, 'field', forbidden)
    for name in ('f', 'v', 'v', 'c', 'c', 'a', 'm', 'm'):
        key(view, name)
        assert view.presentation is before and view.state == state
    view.plot.camera.azimuth += 20
    view.plot.window_size = (840, 560)
    view.plot.ren_win.Render()
    view.redraw()
    assert view._presentation_cache.build_count == count


def test_real_slider_refresh_boundary_clear_and_recover(view):
    old = view.presentation
    w = view.sliders[0]
    for value in (.6, 1., 2., 0.):
        count = view._presentation_cache.build_count
        w.GetRepresentation().SetValue(value)
        w.InvokeEvent(vtkCommand.EndInteractionEvent)
        assert view._presentation_cache.build_count == count+1
        assert view.presentation is not old
        assert view.report == measure(view.state)
        if value == 1.:
            assert view.fields is None and not view.arrow_meshes
        else: assert view.fields is not None
        old = view.presentation


def test_selected_faces_correspond_to_rotated_full_surface(view):
    view.set_yaw(35); view.set_tilt(20)
    view.toggle_move_surface(); view.set_coordinate(1, .3)
    before, report = view.presentation, view.report.copy()
    for name in FACE_NAMES:
        view.select_face(name)
        index = FACE_NAMES.index(name)
        assert view.presentation is before and view.report == report
        assert view.selected_face_mesh.n_cells == view.resolution**2
        world = view.selected_face_mesh.points*view.unit+view.origin
        local = (world-np.asarray(view.state.surface.center_m)) @ np.asarray(view.state.surface.rotation)
        local /= view.state.scale_m
        axis, sign = index//2, 1 if index%2 == 0 else -1
        np.testing.assert_allclose(local[:, axis], sign, atol=1e-14)
        assert view.selected_face_flux == report['face_flux_N_m2_per_C'][index]
        assert view.full_mesh.n_cells == 6*view.resolution**2
    key(view, 'v')
    assert view.selected_face_flux is None and 'hidden; V reveals' in view._annotation_actors['teaching'][0].GetInput()
    key(view, 's')
    assert view.selected_face is None and view.selected_face_mesh is None
    with pytest.raises(ValueError): view.select_face('+x')


def test_preset_keys_predict_reveal_edit_reset_and_snapshot(view, tmp_path):
    original = view.initial.to_dict()
    for shortcut, expected in zip(('1','2','3','4'), ('center','offcenter','outside','zero_net')):
        key(view, shortcut)
        assert view.teaching_case == expected and not view.show_values
        assert 'Exact total' not in view._annotation_actors['readout'][0].GetInput()
        key(view, 'v')
        assert view.show_values and view.report == measure(view.state)
        if shortcut in ('3','4'):
            assert view.report['exact_total_N_m2_per_C'] == 0
            assert np.any(view.fields != 0)
    view.next_charge()  # Active charge 1 must not break a one-charge preset.
    key(view, '2')
    assert view.active == 0 and len(view.state.charges) == 1
    key(view, 'v'); key(view, 'f')
    out = tmp_path/'new-snapshot'
    raw = json.dumps(original, indent=4).encode()
    count = view._presentation_cache.build_count
    report = save_snapshot(view.initial, out, lesson=view, source_bytes=raw)
    assert view._presentation_cache.build_count == count
    assert report['display']['teaching_case'] == 'offcenter'
    assert report['display']['selected_cube_local_face'] == '+x'
    assert report['display']['teaching_case_provenance'] == 'synthetic_not_exam_original'
    assert (out/'authored-input.json').read_bytes() == raw
    assert report['original_input_equals_current_state'] is False
    view.set_coordinate(0, .7)
    assert view.teaching_case is None
    key(view, '0')
    assert view.state.to_dict() == original and view.selected_face is None


@pytest.mark.parametrize('resolution', [4,6,12,40])
def test_declared_sphere_display_mesh_difference_not_flux_change(resolution):
    """Original V1 used normalized float32 VTK sphere points. No pixel-parity claim."""
    old = pv.Sphere(radius=1., theta_resolution=3*resolution, phi_resolution=2*resolution)
    points = np.asarray(old.points, dtype=float)
    points /= np.linalg.norm(points, axis=1)[:, None]
    old.points = points
    normals = np.asarray(old.cell_centers().points, dtype=float)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    state = GaussState(surface=GaussianSphere())
    new = build_surface(state, resolution=resolution)
    np.testing.assert_array_equal(old.faces, new.cells.ravel())
    # Representation comparison only; never used to accept/modify physical flux.
    np.testing.assert_allclose(new.points_m, points, atol=5e-8, rtol=0)
    np.testing.assert_allclose(new.probes_m, normals, atol=5e-8, rtol=0)


@pytest.mark.parametrize('size', [(1440,960), (840,560)])
def test_new_teaching_text_fits_both_window_sizes(view, size):
    key(view, '2'); key(view, 'v'); key(view, 'f')
    view.plot.window_size = size
    view.plot.ren_win.Render()
    ren = view.plot.renderers[0]
    boxes = {}
    for name in ('title','teaching','instructions'):
        actor = view._annotation_actors[name][0]
        box = [0.,0.,0.,0.]
        actor.GetBoundingBox(ren, box)
        anchor = actor.GetPositionCoordinate().GetComputedViewportValue(ren)
        box = np.asarray(box)+[anchor[0],anchor[0],anchor[1],anchor[1]]
        assert 0 <= box[0] and box[1] <= ren.GetSize()[0], (name, box, ren.GetSize())
        assert 0 <= box[2] and box[3] <= ren.GetSize()[1], (name, box, ren.GetSize())
        boxes[name] = box
    assert boxes['teaching'][3] < boxes['title'][2]
