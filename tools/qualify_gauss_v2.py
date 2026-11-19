"""Capture real Gauss V2 controls and synthetic conceptual cases (author evidence)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np
from emfeeld.gauss_lesson import GaussState, measure
from emfeeld.gauss_view import GaussLesson, save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def key(view, value):
    native = view.plot.iren.interactor
    native.SetKeySym(value)
    native.InvokeEvent('KeyPressEvent')


def qualify(output):
    output = Path(output)
    protect_saved_evidence(output, new_directory=True)
    output.mkdir(parents=True, exist_ok=False)
    records, view = [], None
    (output/'started.json').write_text('{"execution_complete": false}\n')
    try:
        initial = GaussState()
        raw = json.dumps(initial.to_dict(), indent=2).encode()
        view = GaussLesson(initial, off_screen=True, resolution=10)
        view.plot.show(auto_close=False, interactive=False)
        for shortcut, name in zip(('1','2','3','4'), ('center','offcenter','outside','zero_net')):
            key(view, shortcut)
            assert not view.show_values
            if name == 'offcenter':
                predicted = save_snapshot(initial, output/'offcenter_predict', lesson=view, source_bytes=raw)
                records.append({'case':'offcenter_predict', 'screenshot':'offcenter_predict/view.png',
                                'display':predicted['display']})
            key(view, 'v'); key(view, 'f')
            assert view.selected_face == '+x'
            count = view._presentation_cache.build_count
            before = view.presentation
            view.plot.camera.azimuth += 15
            key(view, 'c'); key(view, 'c')
            assert view.presentation is before and view._presentation_cache.build_count == count
            if name in ('outside','zero_net'):
                assert view.report['exact_total_N_m2_per_C'] == 0
                assert np.min(view.normal_field) < 0 < np.max(view.normal_field)
            report = save_snapshot(initial, output/name, lesson=view, source_bytes=raw)
            assert report['physics'] == measure(view.state)
            records.append({'case':name, 'screenshot':name+'/view.png',
                            'physics':report['physics'], 'display':report['display']})
        key(view,'2');key(view,'v');key(view,'f');view.set_yaw(35);view.set_tilt(20)
        view.plot.window_size=(840,560)
        save_snapshot(initial,output/'rotated_face_small',lesson=view,source_bytes=raw)
        view.set_coordinate(0,1.)  # local face refusal verified separately; reset for exact boundary
        view.reset();view.set_coordinate(0,1.)
        assert view.fields is None and view.report['status']=='undefined_boundary'
        save_snapshot(initial,output/'boundary',lesson=view,source_bytes=raw)
        view.set_coordinate(0,2.)
        assert view.fields is not None and view.report['exact_total_N_m2_per_C']==0
        save_snapshot(initial,output/'recovered_outside',lesson=view,source_bytes=raw)
        result={'status':'PASS','execution_complete':True,'cases':records,
                'real_pyvista_events':True,'synthetic_questions_not_original_exam_solutions':True,
                'independent_review':'not_evaluated','teacher_usefulness':'not_evaluated'}
        (output/'outcome.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return result
    except Exception:
        (output/'outcome.json').write_text(json.dumps({'status':'FAIL','cases':records,
            'traceback':traceback.format_exc()},indent=2)+'\n')
        raise
    finally:
        if view is not None: view.plot.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    qualify(parser.parse_args().output)
