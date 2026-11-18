"""Real production PyVista controls, geometry, camera and evidence."""
from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.dipole_lesson import DipoleState, measure
from emfeeld.dipole_view import DipoleLesson, save_snapshot


@pytest.fixture
def view():
    v=DipoleLesson(DipoleState(),off_screen=True,window_size=(840,560))
    v.plot.show(auto_close=False,interactive=False)
    try:yield v
    finally:v.plot.close()


def box(actor,renderer):
    values=[0.,0.,0.,0.]
    actor.GetBoundingBox(renderer,values)
    origin=actor.GetPositionCoordinate().GetComputedViewportValue(renderer)
    return np.array(values)+[origin[0],origin[0],origin[1],origin[1]]


def test_real_arrow_tips_and_force_application_points(view):
    assert view.state==view.initial
    for name,mesh in view.glyph_meshes.items():
        spec=view.glyph_records[name]
        anchor=np.array(spec["anchor_display"]);direction=np.array(spec["direction"])
        rel=np.asarray(mesh.points)-anchor
        projection=rel@direction
        assert projection.max()==pytest.approx(spec["display_length"],rel=2e-6)
        assert projection.min()>=-2e-7
        assert np.max(np.linalg.norm(rel-projection[:,None]*direction,axis=1))<.15
    for name,position in [("positive_force",view.state.positive_position_m),
                           ("negative_force",view.state.negative_position_m)]:
        expected=(np.array(position)-view.display_origin)/view.display_scale
        np.testing.assert_allclose(view.glyph_records[name]["anchor_display"],expected,atol=1e-15)
    tau=np.array(view.report["torque_N_m"])
    assert abs(np.dot(tau,view.report["dipole_moment_C_m"]))<1e-30
    assert abs(np.dot(tau,view.state.external_field_N_C))<1e-22


def test_actual_slider_and_keyboard_events_bind_state_and_hide_answers(view):
    slider=view.sliders[0]
    slider.GetRepresentation().SetValue(76.)
    slider.InvokeEvent(vtkCommand.EndInteractionEvent)
    assert view.state!=view.initial and view.report==measure(view.state)
    view.plot.iren.interactor.SetKeyEventInformation(0,0,"v",0,"v")
    view.plot.iren.interactor.InvokeEvent("KeyPressEvent")
    assert view.show_values is False
    assert set(view.glyph_meshes)=={"external_field"}
    assert "PREDICT" in view._annotations["readout"][0].GetInput()
    assert "Torque [N m]" not in view._annotations["readout"][0].GetInput()
    view.toggle_values()
    view.set_field_factor(0)
    assert view.report["angle_deg"] is None
    assert "torque" not in view.glyph_meshes
    assert "positive_force" not in view.glyph_meshes
    assert "external_field" not in view.glyph_meshes


@pytest.mark.parametrize("size",[(840,560),(1440,960)])
def test_native_resize_keeps_physics_camera_and_readable_panels(view,size):
    state=view.state;report=view.report.copy()
    camera=np.array(view.plot.renderers[0].camera_position)
    view.plot.ren_win.SetSize(*size);view.plot.ren_win.Render()
    assert view.state==state and view.report==report
    np.testing.assert_array_equal(view.plot.renderers[0].camera_position,camera)
    for name,(actor,_) in view._annotations.items():
        ren=view.plot.renderers[1 if name in ("readout","control-note") else 0]
        if not actor.GetInput():continue
        b=box(actor,ren)
        assert b[0]>=0 and b[1]<=ren.GetSize()[0],(name,b,ren.GetSize())
        assert b[2]>=0 and b[3]<=ren.GetSize()[1],(name,b,ren.GetSize())
    assert box(view._annotations["readout"][0],view.plot.renderers[1])[2]>.46*size[1]


def test_translation_origin_and_camera_are_not_physical_rotation(view):
    original=view.report.copy();state=view.state
    view.plot.renderers[0].camera.Azimuth(41)
    view.plot.render()
    assert view.state==state and view.report==original
    view.translate_pair();view.move_origin()
    for key in ["torque_N_m","positive_force_N","negative_force_N","external_orientation_energy_J"]:
        np.testing.assert_allclose(view.report[key],original[key],rtol=1e-14,atol=1e-23)


def test_actual_current_snapshot_preserves_input_reference_arrays_and_camera(view,tmp_path):
    raw=json.dumps(view.initial.to_dict(),indent=4).encode()
    view.set_dipole_azimuth(-31.)
    out=tmp_path/"changed"
    report=save_snapshot(view.initial,out,lesson=view,source_bytes=raw)
    assert report["physics"]==measure(view.state)
    assert report["original_input_equals_current_state"] is False
    assert (out/"authored-input.json").read_bytes()==raw
    assert report["display"]["window_size_pixels"]==[840,560]
    assert report["screenshot"]["sha256"]==hashlib.sha256((out/"view.png").read_bytes()).hexdigest()
    assert json.loads((out/"lesson.json").read_text())==view.state.to_dict()
    with np.load(out/"measurements.npz") as a:
        np.testing.assert_array_equal(a["positive_position_m"],view.state.positive_position_m)
        np.testing.assert_array_equal(a["torque_N_m"],view.report["torque_N_m"])
    before=(out/"report.json").read_bytes()
    with pytest.raises(ValueError):save_snapshot(view.state,out/"child",lesson=view)
    assert (out/"report.json").read_bytes()==before


def test_invalid_update_does_not_replace_state(view):
    before=view.state
    with pytest.raises(ValueError):view.set_charge(-1e-9)
    assert view.state==before
    with pytest.raises(ValueError):view.set_dipole_polar(True)
    assert view.state==before


def test_slider_representations_survive_physical_redraw(view):
    view.set_dipole_polar(71.)
    props=view.plot.renderers[1].GetViewProps()
    for slider in view.sliders:
        rep=slider.GetRepresentation()
        assert rep.GetVisibility()
        assert props.IsItemPresent(rep), "slider callback exists but its representation is absent"


def test_repeated_redraw_and_snapshot_keep_actual_fonts_inside_viewport(view,tmp_path):
    for index in range(3):
        view.set_dipole_polar(70+index)
        view.redraw()
    report=save_snapshot(view.state,tmp_path/"post-redraw",lesson=view)
    for name,(actor,role) in view._annotations.items():
        font=actor.GetTextProperty().GetFontSize()
        assert font==view.fonts[role]
        assert report["display"]["annotation_font_pixels"][name]==font
        ren=view.plot.renderers[1 if name in ("readout","control-note") else 0]
        if not actor.GetInput():continue
        b=box(actor,ren)
        assert b[0]>=0 and b[1]<=ren.GetSize()[0],(name,b)
        assert b[2]>=0 and b[3]<=ren.GetSize()[1],(name,b)


def test_charge_cycle_at_upper_bound_is_not_stuck(view):
    view.charge_unit=1e-3
    view.set_charge(1e-3)
    view.cycle_charge()
    assert view.state.charge_C==0
    assert "dipole_moment" not in view.glyph_meshes
    view.cycle_charge()
    assert view.state.charge_C==1e-3


def test_rejected_native_slider_restores_real_state_and_readout(view):
    # A large initial E makes a valid widget value physically out of V1 bounds.
    view.field_unit=1e9
    view.set_field_factor(.5)
    before=view.state
    widget=view.sliders[5]
    widget.GetRepresentation().SetValue(2.)
    widget.InvokeEvent(vtkCommand.EndInteractionEvent)
    assert view.state==before and view.report==measure(before)
    assert widget.GetRepresentation().GetValue()==pytest.approx(.5)
    assert "Control refused" in view._annotations["control-note"][0].GetInput()
