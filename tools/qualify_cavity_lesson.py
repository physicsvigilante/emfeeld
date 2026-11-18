"""Actual PyVista 3D lessons and widget events, not human Windows acceptance."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import traceback

import numpy as np
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld.conductor_cavity import ConductorCavity
from emfeeld.cavity_lesson import CavityLesson, save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def qualify(output):
    output=Path(output)
    protect_saved_evidence(output,new_directory=True)
    output.mkdir(parents=True,exist_ok=False)
    (output/'started.json').write_text('{"execution_complete":false}\n')
    view=CavityLesson(ConductorCavity(),off_screen=True,line_count=20,resolution=40)
    records=[]
    try:
        view.plot.show(auto_close=False,interactive=False)
        for name in ['offset','center','grounded','negative','isolated_charged','rotated_full']:
            if name=='center':
                slider=view.sliders[0]
                slider.GetRepresentation().SetValue(0)
                slider.InvokeEvent(vtkCommand.EndInteractionEvent)
                assert np.linalg.norm(view.model.charge_position_m)==0
            elif name=='grounded':
                view.set_offset(.65);view.toggle_grounded()
                assert view.model.mode=='grounded' and not view.exterior_paths
            elif name=='negative':
                view.reverse_charge()
                assert view.model.charge_C<0
            elif name=='isolated_charged':
                view.toggle_grounded();view.set_Q_nC(2.0)
                assert view.model.outer_charge_C>0 and view.exterior_paths
            elif name=='rotated_full':
                view.set_theta(45);view.set_phi(35);view.toggle_cutaway()
                view.plot.subplot(0,0);view.plot.camera.azimuth+=60
                assert not view.cutaway and all(abs(x)>0 for x in view.model.charge_position_m)
            for widget in view.sliders:
                assert widget.GetEnabled()
                assert view.plot.renderers[1].HasViewProp(widget.GetRepresentation())
            model=view.model;R=model.inner_radius_m
            assert np.linalg.matrix_rank(view.inner_mesh.points)==3
            np.testing.assert_allclose(np.linalg.norm(view.inner_mesh.points,axis=1),1,atol=2e-12)
            np.testing.assert_allclose(view.inner_mesh['Surface charge [nC/m^2]'],
                                       model.inner_density(view.inner_mesh.points)*1e9,rtol=2e-12)
            np.testing.assert_array_equal(model.field([1.1*R,0,0]),[0,0,0])
            for row in view.lines:
                assert row['termination']=='inner_surface_approached'
                assert (np.linalg.norm(row['points_m'],axis=1)<R).all()
                delta=np.diff(row['points_m'],axis=0)
                e=model.field((row['points_m'][1:]+row['points_m'][:-1])/2)
                assert (np.sum(delta*e,axis=1)>0).all()
            for pts in view.exterior_paths:
                assert (np.linalg.norm(pts,axis=1)>model.outer_radius_m/R).all()
            r=save_snapshot(model,output/name,lesson=view)
            records.append({'case':name,'status':'PASS','png':f'{name}/view.png',
                            'png_sha256':r['screenshot']['sha256'],'physics':r['physics']})
        result={'cases':records,'status':'PASS','automated_widget_event':True,
                'human_visual_acceptance':'not_evaluated','manual_windows_interaction':'not_evaluated'}
        (output/'outcome.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    except Exception:
        (output/'outcome.json').write_text(json.dumps({'status':'FAIL','completed_cases':records,
                                                        'traceback':traceback.format_exc()},indent=2)+'\n')
        raise
    finally:view.plot.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();r=qualify(a.output);print(json.dumps(r,indent=2))


if __name__=='__main__':main()
