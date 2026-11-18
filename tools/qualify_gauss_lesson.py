"""Eight actual production Gauss-law scenes; author automation, not teacher acceptance."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import traceback

import numpy as np
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.gauss_lesson import GaussState
from emfeeld.gauss_view import GaussLesson,save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def qualify(output):
    output=Path(output);protect_saved_evidence(output,new_directory=True)
    output.mkdir(parents=True,exist_ok=False)
    (output/'started.json').write_text('{"execution_complete": false}\n')
    view=None;records=[]
    try:
        initial=GaussState();raw=json.dumps(initial.to_dict(),indent=2).encode()
        view=GaussLesson(initial,off_screen=True,resolution=10)
        view.plot.show(auto_close=False,interactive=False)
        coarse_error=None
        for name in ['center','offcentre','exterior','boundary','sphere','sphere_refined','dipole','rotated_cutaway']:
            if name=='offcentre':
                w=view.sliders[0];w.GetRepresentation().SetValue(.6);w.InvokeEvent(vtkCommand.EndInteractionEvent)
                view.set_coordinate(1,.2)
                assert view.state.charges[0].position_m==(.6,.2,0)
            elif name=='exterior':view.set_coordinate(0,2)
            elif name=='boundary':view.set_coordinate(1,0);view.set_coordinate(0,1)
            elif name=='sphere':
                view.set_coordinate(0,.7);view.set_coordinate(1,.1);view.toggle_shape()
                coarse_error=abs(view.report['sampling_error_N_m2_per_C'])
            elif name=='sphere_refined':
                view.refine();assert abs(view.report['sampling_error_N_m2_per_C'])<coarse_error
            elif name=='dipole':view.toggle_pair()
            elif name=='rotated_cutaway':
                view.toggle_shape();view.set_yaw(40);view.set_tilt(25);view.toggle_cutaway()
                view.plot.camera.azimuth+=35
            if name=='boundary':
                assert view.report['status']=='undefined_boundary' and view.fields is None
            else:
                assert view.report['status']=='available'
                np.testing.assert_allclose(view.normal_field,np.sum(view.fields*view.normals,axis=1))
                if name in ('exterior','dipole','rotated_cutaway'):
                    assert view.report['exact_total_N_m2_per_C']==0
                    assert np.any(view.normal_field<0) and np.any(view.normal_field>0)
            for w in view.sliders:
                assert w.GetEnabled() and view.plot.renderers[1].HasViewProp(w.GetRepresentation())
            report=save_snapshot(initial,output/name,lesson=view,source_bytes=raw)
            records.append({'case':name,'status':'PASS','physics':report['physics'],
                            'png':f'{name}/view.png','png_sha256':report['screenshot']['sha256']})
        result={'status':'PASS','cases':records,'automated_real_widgets':True,
                'independent_review':'not_evaluated','human_windows_acceptance':'not_evaluated',
                'teacher_usefulness':'not_evaluated'}
        (output/'outcome.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    except Exception:
        (output/'outcome.json').write_text(json.dumps({'status':'FAIL','completed_cases':records,
            'traceback':traceback.format_exc()},indent=2)+'\n');raise
    finally:
        if view is not None:view.plot.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    print(json.dumps(qualify(parser.parse_args().output),indent=2))


if __name__=='__main__':main()
