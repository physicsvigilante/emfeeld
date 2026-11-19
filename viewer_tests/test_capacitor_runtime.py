"""Actual PyVista interactions and images, not a VTK stand-in."""
import json
from pathlib import Path

import numpy as np
import pytest

from emfeeld.capacitor_lesson import CapacitorState, measure
from emfeeld.capacitor_view import CapacitorLesson, save_snapshot


def key(view,k):
    native=view.plot.iren.interactor
    native.SetKeySym(k)
    native.InvokeEvent('KeyPressEvent')


def make():
    v=CapacitorLesson(CapacitorState(),off_screen=True,window_size=(840,560))
    v.plot.show(auto_close=False,interactive=False)
    return v


def test_real_widgets_and_modes_and_no_physics_on_reveal(monkeypatch):
    v=make()
    try:
        assert len(v.sliders)==2
        assert all(w.GetEnabled() for w in v.sliders)
        initial=v.prepared
        import emfeeld.capacitor_view as mod
        monkeypatch.setattr(mod,'prepare',lambda _: (_ for _ in ()).throw(AssertionError('physics called on display-only')))
        count=v.preparation_count
        key(v,'v'); assert not v.show_values
        key(v,'v');assert v.show_values
        v.plot.camera.azimuth += 17
        v.redraw()
        assert v.prepared is initial and v.preparation_count==count
    finally:v.plot.close()


def test_real_key_cases_and_slider_recalculate():
    v=make()
    try:
        baseline=measure(v.initial)
        for k in '1234':
            key(v,k)
            assert v.preset_label==k
            assert not v.show_values
            key(v,'v')
            assert v.show_values
            r=v.prepared.measurements
            if k=='2':
                assert r['stored_field_energy_J']<baseline['stored_field_energy_J']
            if k=='4':
                assert r['stored_field_energy_J']>baseline['stored_field_energy_J']
        v.set_kappa(5.)
        assert v.preset_label is None
        assert v.state.relative_permittivity==5.
        before=v.preparation_count
        v.set_gap_factor(1.25)
        assert v.preparation_count==before+1
        assert v.state.gap_m ==v.initial.gap_m*1.25
        key(v,'0')
        assert v.state==v.initial and v.show_values
        key(v,'b');assert v.state.mode=='battery_voltage'
        key(v,'i');assert v.state.mode=='isolated_charge'
    finally:v.plot.close()


def test_native_current_state_snapshot_and_no_overwrite(tmp_path):
    v=make()
    try:
        raw=json.dumps(v.initial.to_dict(),indent=2).encode()
        key(v,'4');key(v,'v')
        result=save_snapshot(v.initial,tmp_path/'capture',lesson=v,source_bytes=raw)
        assert result['input_equals_current'] is False
        assert result['physics']==measure(v.state)
        im=__import__('PIL.Image',fromlist=['Image']).open(tmp_path/'capture/view.png')
        assert im.size==(840,560)
        assert np.std(np.asarray(im)) > 10
        assert (tmp_path/'capture/field_samples.npz').exists()
        with pytest.raises(FileExistsError):
            save_snapshot(v.state,tmp_path/'capture',lesson=v)
    finally:v.plot.close()


def test_invalid_slider_state_keeps_physical_and_recovery():
    v=make()
    try:
        old=v.state; p=v.prepared
        with pytest.raises(ValueError):v.set_gap_factor(4.)
        assert v.state==old and v.prepared is p
        v.set_kappa(4.);assert v.state.relative_permittivity==4.
        assert v.prepared is not p
    finally:v.plot.close()
