"""Real optional PyVista and VTK events; no mocks or surrogate renderer."""
import importlib.util
from pathlib import Path
from dataclasses import replace
import json

import numpy as np
import pytest
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.conductor_cavity import ConductorCavity
from emfeeld.cavity_lesson import CavityLesson,save_snapshot


def test_real_six_case_lesson(tmp_path):
    path=Path(__file__).resolve().parents[1]/'tools/qualify_cavity_lesson.py'
    spec=importlib.util.spec_from_file_location('qualify_cavity',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.qualify(tmp_path/'lesson')
    assert len(result['cases'])==6
    assert all(c['status']=='PASS' for c in result['cases'])
    assert result['manual_windows_interaction']=='not_evaluated'


def test_camera_cutaway_and_current_state_snapshot(tmp_path):
    source=ConductorCavity();view=CavityLesson(source,off_screen=True,line_count=8,resolution=24)
    try:
        view.plot.show(interactive=False,auto_close=False)
        assert view.model==source
        view.plot.subplot(0,0);view.plot.camera.azimuth+=40
        before=np.array(list(view.plot.camera_position),dtype=float)
        probe=source.field([0,.2,.1])
        view.toggle_cutaway()
        np.testing.assert_allclose(list(view.plot.renderers[0].camera_position),before)
        np.testing.assert_array_equal(probe,view.model.field([0,.2,.1]))
        view.sliders[0].GetRepresentation().SetValue(.8)
        view.sliders[0].InvokeEvent(vtkCommand.EndInteractionEvent)
        assert np.linalg.norm(view.model.charge_position_m)==pytest.approx(.8)
        view.toggle_grounded()
        report=save_snapshot(source,tmp_path/'capture',lesson=view,source_bytes=json.dumps(source.to_dict()).encode())
        saved=json.loads((tmp_path/'capture/lesson.json').read_text())
        assert saved==view.model.to_dict() and saved!=source.to_dict()
        assert report['original_input_equals_current_state'] is False
        assert not view.exterior_paths
        assert report['display']['cutaway'] is False
    finally:view.plot.close()


def test_zero_charge_and_invalid_controller_setting():
    m=ConductorCavity(charge_C=0)
    view=CavityLesson(m,off_screen=True,line_count=4,resolution=16)
    try:
        assert view.lines==[] and view.exterior_paths==[]
        with pytest.raises(ValueError):view.set_offset(1)
        assert view.model==m
        view.set_Q_nC(1)
        assert view.lines==[] and view.exterior_paths
        view.toggle_grounded()
        assert view.exterior_paths==[]
    finally:view.plot.close()
