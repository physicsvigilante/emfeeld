"""Real production PyVista meshes/widgets/screenshots, not surrogate rendering."""
from dataclasses import replace
import hashlib
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.gauss_lesson import GaussState,GaussianCube,GaussianSphere,HeldCharge
from emfeeld.gauss_view import GaussLesson,save_snapshot


@pytest.fixture
def view():
    v=GaussLesson(GaussState(),off_screen=True,resolution=6)
    v.plot.show(auto_close=False,interactive=False)
    try:yield v
    finally:v.plot.close()


def test_real_widgets_preserve_authored_state_and_move_charge(view):
    assert view.state==view.initial
    for widget in view.sliders:
        assert widget.GetEnabled()
        assert not widget.GetRepresentation().GetShowSliderLabel()
        assert view.plot.renderers[1].HasViewProp(widget.GetRepresentation())
    slider=view.sliders[0];slider.GetRepresentation().SetValue(.65)
    slider.InvokeEvent(vtkCommand.EndInteractionEvent)
    assert view.state.charges[0].position_m==(.65,0,0)
    assert view.report['exact_total_N_m2_per_C']==pytest.approx(1e-9/epsilon_0)
    assert np.ptp(view.report['face_flux_N_m2_per_C'])>1
    assert view.plot.renderers[1].HasViewProp(slider.GetRepresentation())


def test_boundary_crossing_clears_stale_flux_and_fields(view):
    view.set_coordinate(0,1)
    assert view.report['status']=='undefined_boundary'
    assert view.report['exact_total_N_m2_per_C'] is None
    assert view.fields is None and view.normal_field is None and not view.arrow_meshes
    view.set_coordinate(0,2)
    assert view.report['status']=='available' and view.report['exact_total_N_m2_per_C']==0
    assert min(view.report['face_flux_N_m2_per_C'])<0<max(view.report['face_flux_N_m2_per_C'])


def test_actual_face_orientation_samples_and_arrow_geometry(view):
    points=view.full_mesh.points.reshape(-1,4,3)
    cross=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])
    cross/=np.linalg.norm(cross,axis=1)[:,None]
    np.testing.assert_allclose(cross,view.normals,atol=1e-14)
    np.testing.assert_allclose(view.normal_field,np.sum(view.fields*view.normals,axis=1))
    for kind,index,mesh in view.arrow_meshes:
        v=view.normals[index] if kind=='normal' else view.fields[index]
        v=v/np.linalg.norm(v)
        along=(mesh.points-(view.probes[index]-view.origin)/view.unit)@v
        assert min(along)>-1e-6 and max(along)==pytest.approx(.18,abs=2e-6)


def test_sphere_samples_on_true_surface_and_refinement(view):
    view.set_coordinate(0,.7);view.toggle_shape()
    assert isinstance(view.state.surface,GaussianSphere)
    np.testing.assert_allclose(np.linalg.norm(view.probes,axis=1),1,atol=2e-15)
    old_error=abs(view.report['sampling_error_N_m2_per_C'])
    view.refine()
    assert view.order==48 and view.report['unrenormalized']
    assert abs(view.report['sampling_error_N_m2_per_C'])<old_error


def test_cutaway_camera_and_rotation_do_not_open_mathematical_surface(view):
    view.set_coordinate(0,.4);view.set_yaw(35);view.set_tilt(20)
    before=view.state;flux=view.report.copy()
    view.plot.camera.azimuth+=25;camera=np.array(list(view.plot.camera_position),dtype=float)
    view.toggle_cutaway()
    assert view.state==before and view.report==flux
    np.testing.assert_allclose(list(view.plot.camera_position),camera)
    assert view.visible_mesh.n_cells<view.full_mesh.n_cells
    assert view.display_state()['mathematical_surface_closed'] is True


def test_actual_snapshot_uses_changed_state_and_camera(view,tmp_path):
    raw=json.dumps(view.initial.to_dict(),indent=4).encode()
    view.set_coordinate(0,.5);view.toggle_values();view.toggle_cutaway()
    out=tmp_path/'capture';report=save_snapshot(view.initial,out,lesson=view,source_bytes=raw)
    assert json.loads((out/'lesson.json').read_text())==view.state.to_dict()
    assert (out/'authored-input.json').read_bytes()==raw
    assert report['original_input_equals_current_state'] is False
    assert report['display']['values_visible'] is False and report['display']['cutaway'] is True
    assert report['screenshot']['sha256']==hashlib.sha256((out/'view.png').read_bytes()).hexdigest()
    with np.load(out/'surface_samples.npz') as saved:
        np.testing.assert_array_equal(saved['E_dot_n_N_C'],view.normal_field)
    assert report['independent_review']=='not_evaluated'


def test_pair_translation_and_size_are_static_configurations(view):
    view.toggle_pair()
    assert len(view.state.charges)==2 and view.report['exact_total_N_m2_per_C']==0
    assert np.max(np.abs(view.fields))>0
    view.next_charge();view.reverse_charge()
    assert view.active==1 and view.state.charges[1].charge_C>0
    charges=view.state.charges
    view.toggle_move_surface();view.set_coordinate(1,.2);view.set_size(1.3)
    assert view.state.charges==charges and view.state.surface.center_m==(0,.2,0)
    assert view.state.surface.side_m==2.6
    view.reset();assert view.state==view.initial


def test_invalid_control_is_transactional(view):
    before=view.state
    for method,arg in [(view.set_size,True),(view.set_size,0),(view.set_yaw,float('nan')),
                       (view.set_tilt,91)]:
        with pytest.raises(ValueError):method(arg)
        assert view.state==before
    with pytest.raises(ValueError):view.set_coordinate(0,1e7)
    assert view.state==before
