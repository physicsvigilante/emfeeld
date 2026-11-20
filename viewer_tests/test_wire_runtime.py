"""Actual PyVista/VTK native events, screenshot evidence and 3D lesson state."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.constants import mu_0

from emfeeld.wire_magnetism import WireState, magnetic_field
from emfeeld.wire_view import WireLesson, save_snapshot, main


def _key(view, key):
    iren=view.plot.iren.interactor
    iren.SetKeySym(key)
    iren.InvokeEvent('KeyPressEvent')


def _slider(view, factor):
    w=view.slider
    w.GetRepresentation().SetValue(factor)
    w.InvokeEvent('EndInteractionEvent')
    return w.GetRepresentation().GetValue()


def test_native_vtk_right_hand_sign_reverse_zero_and_reset():
    initial=WireState(current_A=9,loop_radius_m=.4)
    obj=WireLesson(initial,off_screen=True,window_size=(920,620))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        assert obj.state==initial
        assert obj.preparation_count==1
        assert obj.prepared.report['signed_tangent_field_T']>0
        assert np.all(np.einsum('ij,ij->i',obj.prepared.magnetic_field_T,obj.prepared.tangent_unit)>0)
        _key(obj,'n')
        assert obj.state.current_A==-9
        assert obj.prepared.report['signed_tangent_field_T']<0
        assert np.all(np.einsum('ij,ij->i',obj.prepared.magnetic_field_T,obj.prepared.tangent_unit)<0)
        _key(obj,'4')
        assert obj.state.current_A==0
        assert not np.any(obj.prepared.arrow_display_vectors)
        assert not np.any(obj.prepared.magnetic_field_T)
        _key(obj,'0')
        assert obj.state==initial
        assert obj.case_label is None
        assert obj.show_values
    finally:obj.plot.close()


def test_native_real_slider_endinteraction_then_camera_reveal_cached(monkeypatch):
    initial=WireState(current_A=5,loop_radius_m=.35)
    obj=WireLesson(initial,off_screen=True,window_size=(1040,700))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        assert _slider(obj,1.5)==pytest.approx(1.5)
        assert obj.state.loop_radius_m==pytest.approx(.525)
        assert obj.preparation_count==2
        saved=obj.prepared
        assert saved.report['field_magnitude_T']==pytest.approx(mu_0*5/(2*np.pi*.525))
        import emfeeld.wire_view as mod
        monkeypatch.setattr(mod,'prepare',lambda s:(_ for _ in ()).throw(AssertionError('display must not prepare physics')))
        old=obj.preparation_count
        _key(obj,'v')
        assert not obj.show_values
        obj.plot.camera.azimuth+=20
        obj.redraw()
        _key(obj,'v')
        assert obj.show_values
        assert obj.prepared is saved and obj.preparation_count==old
    finally:obj.plot.close()


def test_native_keys_case_radius_slider_sync_and_predict():
    s=WireState(loop_radius_m=.2,current_A=12)
    obj=WireLesson(s,off_screen=True,window_size=(840,560))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        _key(obj,'2')
        assert obj.state.loop_radius_m==pytest.approx(.4)
        assert obj.slider.GetRepresentation().GetValue()==pytest.approx(2)
        assert obj.case_label=='2' and not obj.show_values
        _key(obj,'v')
        assert obj.show_values
        _key(obj,'3')
        assert obj.state.loop_radius_m==pytest.approx(.2)
        assert obj.state.current_A==-s.current_A
        assert obj.slider.GetRepresentation().GetValue()==pytest.approx(1)
        assert obj.case_label=='3' and not obj.show_values
        _key(obj,'0')
        assert obj.state==s and obj.show_values
        assert obj.slider.GetRepresentation().GetValue()==pytest.approx(1)
    finally:obj.plot.close()


def test_native_invalid_ratio_refuses_and_restores_knob():
    s=WireState(loop_radius_m=80,current_A=2)
    obj=WireLesson(s,off_screen=True,window_size=(840,560))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        before=obj.prepared;count=obj.preparation_count
        assert _slider(obj,1.5)==pytest.approx(1.)
        assert obj.state==s and obj.prepared is before and obj.preparation_count==count
        assert 'Control refused:' in obj.notice
        assert _slider(obj,.8)==pytest.approx(.8)
        assert obj.state.loop_radius_m==pytest.approx(64)
        assert obj.preparation_count==count+1
    finally:obj.plot.close()


@pytest.mark.parametrize('sign',(-1,0,1))
def test_native_live_capture_current_report_samples_and_hashes(tmp_path,sign):
    initial=WireState(axis_direction=(1,1,2),origin_m=(.2,0,0),current_A=sign*7,loop_radius_m=.35)
    obj=WireLesson(initial,off_screen=True,window_size=(980,640))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        if sign:_key(obj,'2')
        raw=(json.dumps(initial.to_dict(),indent=2)+'\n').encode()
        result=save_snapshot(initial,tmp_path/'state',lesson=obj,source_bytes=raw)
        dest=tmp_path/'state'
        assert (dest/'view.png').exists()
        from PIL import Image
        im=np.asarray(Image.open(dest/'view.png'))
        assert im.shape[0:2]==(640,980) and im.std()>12
        j=json.loads((dest/'integrity.json').read_text())['files']
        for name,expect in j.items():
            assert hashlib.sha256((dest/name).read_bytes()).hexdigest()==expect
        samples=np.load(dest/'field_samples.npz')
        assert np.array_equal(samples['magnetic_field_T'],obj.prepared.magnetic_field_T)
        assert np.array_equal(samples['positions_m'],obj.prepared.loop_positions_m)
        assert np.array_equal(samples['B_arrow_display_vectors'],obj.prepared.arrow_display_vectors)
        assert np.array_equal(samples['magnetic_field_T'],magnetic_field(obj.state,samples['positions_m']))
        assert result['physics']['current_A']==sign*7
        assert (result['authored_state']!=result['current_state']) == bool(sign)
        assert result['source_code_sha256']['wire_magnetism.py']
        assert result['renderer']=='PyVista real screenshot'
        with pytest.raises((FileExistsError,ValueError)):
            save_snapshot(initial,dest,lesson=obj,source_bytes=raw)
    finally:obj.plot.close()


def test_headless_case_report_without_native_graphics(tmp_path):
    source=Path(__file__).parents[1]/'examples/lessons/straight_current_wire.json'
    assert main([str(source),'--case','3','--headless',str(tmp_path/'headless')])==0
    j=json.loads((tmp_path/'headless/report.json').read_text())
    assert j['physics']['current_A']==-5
    assert j['current_state']['current_A']==-5
    assert j['authored_state']['current_A']==5
    assert j['renderer'].startswith('none')
    assert not (tmp_path/'headless/view.png').exists()


def test_native_positive_ampere_arrow_persists_through_negative_and_zero(tmp_path):
    initial=WireState(origin_m=(.2,-.1,.5),axis_direction=(1,2,3),
                      current_A=7,loop_radius_m=.29,samples_per_loop=72)
    obj=WireLesson(initial,off_screen=True,window_size=(1040,680))
    try:
        obj.plot.show(auto_close=False,interactive=False)
        base_data=obj.prepared
        base_arrow=obj.positive_loop_arrow_mesh.points.copy()
        base_direction=obj.positive_loop_arrow_direction.copy()
        blue=tuple(obj.positive_loop_arrow_actor.GetProperty().GetColor())
        assert len(base_arrow)>20 and base_direction.shape==(3,)
        assert np.linalg.norm(base_direction)==pytest.approx(1)
        i=initial.samples_per_loop//5
        j=(i+1)%initial.samples_per_loop
        tangents=base_data.tangent_unit
        expected=(tangents[i]+tangents[j])/np.linalg.norm(tangents[i]+tangents[j])
        assert np.allclose(base_direction,expected,atol=1e-15)
        assert np.dot(base_direction,base_data.tangent_unit[i])>.999
        assert blue[2]>blue[0]  # distinctly blue, not green B or orange current
        assert 'positive_ampere_circulation_arrow' in obj.plot.renderer.actors
        for key,expected_current,label in [('n',-7,'negative'),('4',0,'zero'),('0',7,'reset')]:
            _key(obj,key)
            assert obj.state.current_A==expected_current
            assert 'positive_ampere_circulation_arrow' in obj.plot.renderer.actors
            assert np.array_equal(obj.positive_loop_arrow_direction,base_direction)
            assert np.allclose(obj.positive_loop_arrow_mesh.points,base_arrow,atol=1e-14)
            assert tuple(obj.positive_loop_arrow_actor.GetProperty().GetColor())==blue
            if expected_current == 0:
                assert np.count_nonzero(obj.prepared.arrow_display_vectors)==0
            else:
                sign=np.sign(np.einsum('ij,ij->i',obj.prepared.magnetic_field_T,
                                       obj.prepared.tangent_unit))
                assert np.all(sign==np.sign(expected_current))
            raw=(json.dumps(initial.to_dict(),indent=2)+'\n').encode()
            receipt=save_snapshot(initial,tmp_path/label,lesson=obj,source_bytes=raw)
            assert receipt['display']['loop_direction_is_positive_circulation_not_B']
            assert np.allclose(receipt['display']['positive_loop_arrow_direction_display'],
                               expected)
            assert (tmp_path/label/'view.png').is_file()
    finally:
        obj.plot.close()
