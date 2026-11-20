"""Genuine PyVista/VTK rectangular-loop torque interactions and source evidence."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from emfeeld.rectangular_loop_torque import RectangularLoopState, teaching_case
from emfeeld.rectangular_loop_view import TorqueLesson, save_snapshot, main


def key(view, k):
    iren=view.plot.iren.interactor
    iren.SetKeySym(k)
    iren.InvokeEvent("KeyPressEvent")


def slider(widget,value):
    widget.GetRepresentation().SetValue(value)
    widget.InvokeEvent("EndInteractionEvent")
    return widget.GetRepresentation().GetValue()


def test_real_keys_parallel_perpendicular_antiparallel_current_zero_field():
    state=RectangularLoopState(current_A=4,field_strength_T=.3)
    view=TorqueLesson(state,off_screen=True,window_size=(960,640))
    try:
        view.plot.show(auto_close=False,interactive=False)
        for digit in ("1","2","3"):
            key(view,digit)
            assert view.state==teaching_case(state,digit)
            assert view.case_label==digit and not view.show_values
            if digit in ("1","3"):
                assert view.torque_arrow_actor is None
            else:
                assert view.torque_arrow_actor is not None
            key(view,"v")
            assert view.show_values
        key(view,"4")
        assert view.state.current_A==-4
        assert np.dot(view.current_glyph,view.prepared.edge_vectors_m[0])<0
        assert np.dot(view.moment_glyph,view.normal_glyph)<0
        key(view,"5")
        assert view.current_arrow_actor is None
        assert view.moment_arrow_actor is None
        assert view.torque_arrow_actor is None
        assert view.field_arrow_actor is not None
        key(view,"6")
        assert view.field_arrow_actor is None
        assert view.torque_arrow_actor is None
        assert view.moment_arrow_actor is not None
        key(view,"0")
        assert view.state==state and view.show_values and view.show_forces
    finally:
        view.plot.close()


def test_current_and_B_reversals_signed_physics_and_normal_fixed():
    s=RectangularLoopState(tilt_deg=90,current_A=3,field_strength_T=.2)
    view=TorqueLesson(s,off_screen=True,window_size=(980,650))
    try:
        view.plot.show(auto_close=False,interactive=False)
        initial_normal=view.normal_glyph.copy()
        torque=view.torque_glyph.copy()
        field=view.field_glyph.copy()
        moment=view.moment_glyph.copy()
        current=view.current_glyph.copy()
        key(view,"n")
        assert np.array_equal(view.normal_glyph,initial_normal)
        assert view.current_glyph==pytest.approx(-current)
        assert view.moment_glyph==pytest.approx(-moment)
        assert view.torque_glyph==pytest.approx(-torque)
        assert np.array_equal(view.field_glyph,field)
        key(view,"n")
        key(view,"b")
        assert view.state.field_strength_T==pytest.approx(-.2)
        assert view.field_glyph==pytest.approx(-field)
        assert view.moment_glyph==pytest.approx(moment)
        assert view.torque_glyph==pytest.approx(-torque)
        assert np.array_equal(view.normal_glyph,initial_normal)
        assert slider(view.field_slider,1.5)==pytest.approx(1.5)
        assert view.state.field_strength_T==pytest.approx(-.3)
        assert view.field_glyph==pytest.approx(-field)
    finally:
        view.plot.close()


def test_native_sliders_and_display_only_cache(monkeypatch):
    s=RectangularLoopState(tilt_deg=45,current_A=8,field_strength_T=.2)
    view=TorqueLesson(s,off_screen=True,window_size=(1000,660))
    try:
        view.plot.show(auto_close=False,interactive=False)
        before=view.preparation_count
        assert slider(view.angle_slider,90)==pytest.approx(90)
        assert view.state.tilt_deg==pytest.approx(90)
        assert view.preparation_count==before+1
        assert slider(view.field_slider,.5)==pytest.approx(.5)
        assert view.state.field_strength_T==pytest.approx(.1)
        data=view.prepared
        count=view.preparation_count
        import emfeeld.rectangular_loop_view as module
        monkeypatch.setattr(module,"prepare",lambda *_args,**_kw:(
            _ for _ in ()).throw(AssertionError("display may not recalculate physics")))
        key(view,"v")
        key(view,"f")
        assert not view.show_values and not view.show_forces
        view.plot.subplot(0,0)
        old=view.plot.camera_position
        view.plot.camera.azimuth+=18
        view.redraw()
        assert view.plot.camera_position!=old
        assert view.prepared is data and view.preparation_count==count
        key(view,"v")
        assert view.show_values
    finally:
        view.plot.close()


def test_native_refused_angle_is_atomic_and_slider_restores():
    view=TorqueLesson(RectangularLoopState(),off_screen=True,window_size=(880,590))
    try:
        view.plot.show(auto_close=False,interactive=False)
        original=view.prepared
        count=view.preparation_count
        with pytest.raises(ValueError):
            view.set_angle(181)
        assert original is view.prepared and view.preparation_count==count
        assert slider(view.angle_slider,180)==pytest.approx(180)
        assert view.torque_arrow_actor is None
    finally:
        view.plot.close()


def _visible_slider_rails(image):
    # Horizontal control rails must be visible in the RIGHT information panel.
    # Checks actual rendered pixels, not only a VTK widget enabled state.
    rgb=np.asarray(image.convert("RGB"))
    h,w=rgb.shape[:2]
    roi=rgb[int(.55*h):int(.96*h),int(.68*w):int(.97*w)]
    dark=np.max(roi,axis=2)<215
    rows=[i for i,row in enumerate(dark) if row.sum()>.36*dark.shape[1]]
    bands=[]
    for y in rows:
        if not bands or y>bands[-1][-1]+2:
            bands.append([y])
        else:
            bands[-1].append(y)
    return len(bands)>=2 and bands[-1][0]-bands[0][-1]>15


@pytest.mark.parametrize("case",("1","2","3","4","5","6"))
def test_real_screenshots_source_identity_physics_and_slider_visibility(tmp_path,case):
    initial=RectangularLoopState(centre_m=(.17,-.3,.21),
          field_direction=(1,2,3),current_A=4,width_m=.45,height_m=.33,
          field_strength_T=.35,tilt_deg=55)
    view=TorqueLesson(initial,off_screen=True,window_size=(1060,720))
    try:
        view.plot.show(auto_close=False,interactive=False)
        key(view,case)
        assert view.state==teaching_case(initial,case)
        raw=(json.dumps(initial.to_dict(),indent=2,sort_keys=True)+"\n").encode()
        report=save_snapshot(initial,tmp_path/"scene",lesson=view,source_bytes=raw)
        dest=tmp_path/"scene"
        from PIL import Image
        with Image.open(dest/"view.png") as im:
            assert im.size==(1060,720)
            assert np.asarray(im).std()>10
            assert _visible_slider_rails(im)
        assert report["current_state"]==view.state.to_dict()
        assert report["original_input_sha256"]==hashlib.sha256(raw).hexdigest()
        assert report["renderer"]=="PyVista real screenshot"
        s=np.load(dest/"physical_samples.npz")
        assert s["external_field_B_T"]==pytest.approx(view.prepared.field_B_T)
        assert s["physical_torque_N_m"]==pytest.approx(view.prepared.torque_N_m)
        assert s["segment_forces_N"]==pytest.approx(view.prepared.segment_forces_N)
        for path,digest in json.loads((dest/"integrity.json").read_text())["files"].items():
            assert hashlib.sha256((dest/path).read_bytes()).hexdigest()==digest
        with pytest.raises((FileExistsError,ValueError)):
            save_snapshot(initial,dest,lesson=view,source_bytes=raw)
    finally:
        view.plot.close()


def test_live_and_headless_source_bytes_must_match_before_writing(tmp_path):
    plus=RectangularLoopState(current_A=5)
    minus=replace(plus,current_A=-5)
    wrong=json.dumps(minus.to_dict()).encode()
    invalid=[wrong,b"invalid JSON",wrong[:-1]+b', "current_A": 4}',
             wrong.replace(b'"current_A": -5.0',b'"current_A": NaN')]
    for i,raw in enumerate(invalid):
        where=tmp_path/f"invalid_{i}"
        with pytest.raises(ValueError):
            save_snapshot(plus,where,source_bytes=raw)
        assert not where.exists()
    view=TorqueLesson(plus,off_screen=True,window_size=(880,600))
    try:
        with pytest.raises(ValueError):
            save_snapshot(minus,tmp_path/"wrong_live",lesson=view,
                          source_bytes=wrong)
        assert not (tmp_path/"wrong_live").exists()
    finally:
        view.plot.close()


def test_headless_cli_snapshot_uses_original_and_current_state(tmp_path):
    path=Path(__file__).parents[1]/"examples/lessons/rectangular_loop_uniform_field.json"
    assert main([str(path),"--case","4","--headless",str(tmp_path/"headless")])==0
    report=json.loads((tmp_path/"headless"/"report.json").read_text())
    assert report["authored_state"]["current_A"]==3
    assert report["current_state"]["current_A"]==-3
    assert report["current_state"]["tilt_deg"]==90
    assert report["physics"]["orientation_potential_J"]==0
    assert not (tmp_path/"headless"/"view.png").exists()
