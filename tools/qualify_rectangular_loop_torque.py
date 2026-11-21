"""Source-bound genuine PyVista scene qualification for one rectangular loop.

Checks native VTK key and slider events and independently evaluates elementary
uniform-field torque/energy identities; never substitutes old screenshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import traceback

import numpy as np

from emfeeld.output_safety import protect_saved_evidence
from emfeeld.rectangular_loop_torque import (
    RectangularLoopState, load_lesson, teaching_case,
)
from emfeeld.rectangular_loop_view import TorqueLesson, save_snapshot


def _key(view, key):
    iren=view.plot.iren.interactor
    iren.SetKeySym(key)
    iren.InvokeEvent("KeyPressEvent")


def _slider(widget, value):
    widget.GetRepresentation().SetValue(value)
    widget.InvokeEvent("EndInteractionEvent")


def _visible_rails(png):
    from PIL import Image
    with Image.open(png) as im:
        image=np.asarray(im.convert("RGB"))
    h,w=image.shape[:2]
    assert (h,w)==(760,1200) or (h,w)==(720,1100)
    assert image.std()>10
    region=image[int(.55*h):int(.97*h),int(.68*w):int(.97*w)]
    dark=np.max(region,axis=2)<215
    y=[i for i,row in enumerate(dark) if row.sum()>.36*dark.shape[1]]
    bands=[]
    for i in y:
        if not bands or i>bands[-1][-1]+2:
            bands.append([i])
        else:
            bands[-1].append(i)
    return len(bands)>=2 and bands[-1][0]-bands[0][-1]>15


def qualify(root):
    root=Path(root)
    protect_saved_evidence(root,new_directory=True)
    root.mkdir(parents=True,exist_ok=False)
    (root/"started.json").write_text('{"completed":false}\n',encoding="utf-8")
    original_path=Path(__file__).resolve().parents[1]/"examples/lessons/rectangular_loop_uniform_field.json"
    raw=original_path.read_bytes()
    initial=load_lesson(original_path)
    view=None
    captures=[]

    def capture(label, authored=initial, source=raw):
        report=save_snapshot(authored,root/label,lesson=view,source_bytes=source)
        dest=root/label
        png=dest/"view.png"
        assert png.is_file() and png.stat().st_size>3500
        assert _visible_rails(png), "both genuine slider rails must remain visible"
        hashes=json.loads((dest/"integrity.json").read_text())["files"]
        for name,digest in hashes.items():
            assert hashlib.sha256((dest/name).read_bytes()).hexdigest()==digest
        assert report["authored_state"]==authored.to_dict()
        assert report["current_state"]==view.state.to_dict()
        # Own scalar reference: expected exact static magnetic moment / B
        amp=view.state.current_A*view.state.width_m*view.state.height_m*view.state.field_strength_T
        angle=math.radians(view.state.tilt_deg)
        assert math.isclose(report["physics"]["orientation_potential_J"],
                            -amp*math.cos(angle), rel_tol=3e-12, abs_tol=2e-14)
        assert math.isclose(report["physics"]["torque_magnitude_N_m"],
                            abs(amp*math.sin(angle)),rel_tol=3e-12,abs_tol=2e-14)
        assert np.linalg.norm(view.prepared.segment_forces_N.sum(axis=0))<2e-12
        assert np.allclose(
            report["physics"]["segment_torque_xyz_N_m"],
            report["physics"]["torque_xyz_N_m"],rtol=2e-12,atol=2e-13)
        captures.append({"label":label,"png":label+"/view.png",
             "sha256":hashlib.sha256(png.read_bytes()).hexdigest(),
             "current_A":view.state.current_A,
             "external_B_strength_T":view.state.field_strength_T,
             "tilt_deg":view.state.tilt_deg})
        return report

    try:
        view=TorqueLesson(initial,off_screen=True,window_size=(1200,760))
        view.plot.show(auto_close=False,interactive=False)
        for key,label in (("1","aligned"),("2","perpendicular"),
                          ("3","antialigned"),("4","reversed_I"),
                          ("5","zero_I"),("6","zero_B")):
            _key(view,key)
            assert view.state==teaching_case(initial,key)
            assert not view.show_values
            if key=="2":
                capture("perpendicular_prediction")
            _key(view,"v")
            assert view.show_values
            result=capture(label)
            if key in ("1","3","5","6"):
                assert result["physics"]["torque_magnitude_N_m"]==0
            if key=="5":
                assert result["display"]["current_arrow_present"] is False
                assert result["display"]["field_arrow_present"] is True
            if key=="6":
                assert result["display"]["field_arrow_present"] is False
                assert result["display"]["moment_arrow_present"] is True

        _key(view,"0")
        _slider(view.angle_slider,65.)
        _slider(view.field_slider,1.4)
        assert view.state.tilt_deg==65
        assert math.isclose(view.state.field_strength_T,.28,rel_tol=1e-14)
        capture("native_both_sliders")
        _key(view,"b")
        assert view.state.field_strength_T<0
        _slider(view.field_slider,1.7)
        assert math.isclose(view.state.field_strength_T,-.34,rel_tol=1e-14)
        capture("reversed_B_slider_retains_sign")
        _key(view,"f")
        assert not view.show_forces
        capture("hidden_force_glyphs")

        tilted=RectangularLoopState(
            centre_m=(.3,-.1,.6),field_direction=(1.,2.,3.),
            current_A=-4,field_strength_T=.35,width_m=.51,
            height_m=.26,tilt_deg=73.)
        view.plot.close()
        view=TorqueLesson(tilted,off_screen=True,window_size=(1100,720))
        view.plot.show(auto_close=False,interactive=False)
        captured_raw=(json.dumps(tilted.to_dict(),sort_keys=True)+"\n").encode()
        capture("rotated_external_B",authored=tilted,source=captured_raw)
        result={"status":"PASS","real_pyvista":True,
                "scenes":captures,"scene_count":len(captures),
                "scope":"one rigid one-turn loop in prescribed uniform external B",
                "human_classroom_effectiveness":"not_evaluated"}
        (root/"outcome.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print(json.dumps({"status":"PASS","scene_count":len(captures)}))
        return result
    except Exception:
        (root/"outcome.json").write_text(json.dumps({
            "status":"FAIL","scenes":captures,
            "traceback":traceback.format_exc()},indent=2)+"\n")
        raise
    finally:
        if view is not None:
            view.plot.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    qualify(parser.parse_args().output)
