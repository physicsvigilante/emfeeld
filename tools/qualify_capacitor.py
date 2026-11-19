"""Real PyVista/equilibrium lesson qualification; no second capacitor solver."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

import numpy as np

from emfeeld.capacitor_lesson import CapacitorState,measure,teaching_case
from emfeeld.capacitor_view import CapacitorLesson,save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def key(view,k):
    native=view.plot.iren.interactor
    native.SetKeySym(k)
    native.InvokeEvent('KeyPressEvent')


def qualify(output):
    output=Path(output)
    protect_saved_evidence(output,new_directory=True)
    output.mkdir(parents=True,exist_ok=False)
    (output/'started.json').write_text('{"completed":false}\n')
    raw=(Path(__file__).resolve().parents[1]/'examples/lessons/parallel_plate_capacitor.json').read_bytes()
    initial=CapacitorState()
    view=None
    records=[]
    try:
        view=CapacitorLesson(initial,off_screen=True)
        view.plot.show(auto_close=False,interactive=False)
        for keycode,label in [('1','vacuum_isolated'),('2','dielectric_isolated'),
                              ('3','vacuum_battery'),('4','dielectric_battery')]:
            key(view,keycode)
            assert not view.show_values
            # Snapshot can report true values even when screen hides them.
            if keycode=='2':
                hidden=save_snapshot(initial,output/'dielectric_predict',lesson=view,source_bytes=raw)
                assert hidden['display']['show_values'] is False
            key(view,'v')
            r=save_snapshot(initial,output/label,lesson=view,source_bytes=raw)
            assert r['physics']==measure(teaching_case(initial,keycode))
            assert r['display']['show_values']
            records.append({'label':label,'state':view.state.to_dict(),
                            'physics':r['physics'],'screenshot':label+'/view.png',
                            'exact_current_receipt':r['screenshot']['sha256']})
        # Deliberate negative-polarity control. Red must follow +Q, not lower face.
        neg=CapacitorState(charge_C=-1e-9,relative_permittivity=4.)
        view._apply(neg)
        r=save_snapshot(initial,output/'negative_polarity',lesson=view,source_bytes=raw)
        assert r['physics']['field_z_between_N_C'] < 0
        records.append({'label':'negative_polarity','screenshot':'negative_polarity/view.png'})
        # Zero field => no arrows. No fake polarized material charge for k=1.
        view._apply(CapacitorState(charge_C=0.,relative_permittivity=1.))
        assert view.prepared.field_arrows_xyz.shape==(0,3)
        save_snapshot(initial,output/'zero_charge',lesson=view,source_bytes=raw)
        # Display-only reveal and camera movement do not prepare a new state.
        prepared=view.prepared;count=view.preparation_count
        key(view,'v');view.plot.camera.azimuth+=12;view.redraw()
        assert view.prepared is prepared and view.preparation_count==count
        # Actual user-adjusted dielectric changes only a static equilibrium.
        view.reset(); view.set_kappa(3.5);view.set_gap_factor(1.2)
        r=save_snapshot(initial,output/'adjusted',lesson=view,source_bytes=raw)
        assert r['physics']==measure(view.state)
        records.append({'label':'adjusted','screenshot':'adjusted/view.png'})
        # Reviewer F2: a genuine end-interaction event must reach the model's
        # full admitted kappa=10 limit, without widget clamping at 8.
        view.reset()
        widget=view.sliders[0]
        rep=widget.GetRepresentation()
        assert rep.GetMinimumValue()==1. and rep.GetMaximumValue()==10.
        rep.SetValue(10.)
        widget.InvokeEvent('EndInteractionEvent')
        assert view.state.relative_permittivity==10.
        assert rep.GetValue()==10.
        r=save_snapshot(initial,output/'kappa10_native_slider',lesson=view,source_bytes=raw)
        assert r['physics']==measure(view.state)
        assert r['display']['original_and_current_states_distinct']
        records.append({'label':'kappa10_native_slider',
                        'screenshot':'kappa10_native_slider/view.png',
                        'exact_current_receipt':r['screenshot']['sha256']})
        view.reset()
        assert view.state==initial and rep.GetValue()==initial.relative_permittivity
        report={'status':'PASS','cases':records,'real_pyvista':True,
                'static_equilibria_not_time_evolution':True,
                'fringing_ignored':True,'human_teacher_acceptance':'not_evaluated'}
        (output/'outcome.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'status':'PASS','cases':len(records),'real_pyvista':True}))
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
