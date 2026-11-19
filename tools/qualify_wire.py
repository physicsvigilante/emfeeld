"""Native PyVista 3D right-hand-rule and Ampere loop evidence on actual source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback
import hashlib

import numpy as np

from emfeeld.wire_magnetism import WireState,magnetic_field,teaching_case
from emfeeld.wire_view import WireLesson,save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def key(view,k):
    i=view.plot.iren.interactor
    i.SetKeySym(k)
    i.InvokeEvent('KeyPressEvent')


def qualify(output):
    output=Path(output)
    protect_saved_evidence(output,new_directory=True)
    output.mkdir(parents=True,exist_ok=False)
    (output/'started.json').write_text('{"completed":false}\n')
    raw=(Path(__file__).resolve().parents[1]/'examples/lessons/straight_current_wire.json').read_bytes()
    original=WireState()
    view=None
    records=[]
    try:
        view=WireLesson(original,off_screen=True,window_size=(1200,760))
        view.plot.show(auto_close=False,interactive=False)
        positive_loop_arrow=None
        for code,label in [('1','base'),('2','double_radius'),
                           ('3','reversed_current'),('4','zero_current')]:
            key(view,code)
            assert view.case_label==code and not view.show_values
            if code=='2':
                hidden=save_snapshot(original,output/'radius_prediction',lesson=view,source_bytes=raw)
                assert hidden['display']['show_values'] is False
            key(view,'v')
            result=save_snapshot(original,output/label,lesson=view,source_bytes=raw)
            marker=view.positive_loop_arrow_direction
            assert result['display']['loop_direction_is_positive_circulation_not_B']
            if positive_loop_arrow is None:
                positive_loop_arrow=(marker.copy(),view.positive_loop_arrow_mesh.points.copy())
            else:
                assert np.array_equal(marker,positive_loop_arrow[0])
                assert np.allclose(view.positive_loop_arrow_mesh.points,
                                   positive_loop_arrow[1],atol=1e-14)
            if code=='4':
                assert not np.any(view.prepared.arrow_display_vectors)
            assert result['current_state']==teaching_case(original,code).to_dict()
            assert result['physics']['expected_mu0_I_T_m']==view.prepared.report['expected_mu0_I_T_m']
            assert result['display']['show_values']
            records.append({'label':label,'png':label+'/view.png','sha256':hashlib.sha256((output/label/'view.png').read_bytes()).hexdigest()})
        # New user-selected physical state: actual VTK end-event, not a direct
        # Python method call. Source/current provenance must stay distinct.
        key(view,'0')
        slider=view.slider
        rep=slider.GetRepresentation()
        assert rep.GetMinimumValue()==.5 and rep.GetMaximumValue()==2.
        rep.SetValue(1.6)
        slider.InvokeEvent('EndInteractionEvent')
        assert view.state.loop_radius_m==original.loop_radius_m*1.6
        assert abs(rep.GetValue()-1.6) < 2e-14
        result=save_snapshot(original,output/'native_slider',lesson=view,source_bytes=raw)
        assert result['display']['original_and_current_states_distinct']
        records.append({'label':'native_slider','png':'native_slider/view.png','sha256':hashlib.sha256((output/'native_slider/view.png').read_bytes()).hexdigest()})
        # A rotated current axis is an independently chosen physical input,
        # distinct from merely orbiting the camera.
        other=WireState(origin_m=(.2,-.1,.5),axis_direction=(1,2,3),
                        current_A=-8,loop_radius_m=.31,samples_per_loop=72)
        view.plot.close()
        view=WireLesson(other,off_screen=True,window_size=(920,620))
        view.plot.show(auto_close=False,interactive=False)
        assert np.allclose(view.prepared.magnetic_field_T,
                           magnetic_field(other,view.prepared.loop_positions_m))
        rotated_raw=(json.dumps(other.to_dict(),sort_keys=True)+'\n').encode()
        result=save_snapshot(other,output/'rotated_axis',lesson=view,source_bytes=rotated_raw)
        assert result['physics']['sampled_ampere_circulation_T_m']<0
        records.append({'label':'rotated_axis','png':'rotated_axis/view.png','sha256':hashlib.sha256((output/'rotated_axis/view.png').read_bytes()).hexdigest()})
        report={'status':'PASS','cases':records,'real_pyvista':True,
                'teacher_trial':'not_evaluated','no_general_biot_savart_solver':True}
        (output/'outcome.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        print(json.dumps({'status':'PASS','case_count':len(records)}))
        return report
    except Exception:
        (output/'outcome.json').write_text(json.dumps({
            'status':'FAIL','cases':records,'traceback':traceback.format_exc()},indent=2)+'\n')
        raise
    finally:
        if view is not None:view.plot.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    qualify(p.parse_args().output)
