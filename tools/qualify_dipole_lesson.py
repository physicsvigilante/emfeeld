"""Retain ten actual dipole scenes; automation is not teacher acceptance."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from emfeeld.dipole_lesson import DipoleState
from emfeeld.dipole_view import DipoleLesson, save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    protect_saved_evidence(args.output,new_directory=True)
    args.output.mkdir(parents=True,exist_ok=False)
    base=DipoleState()
    raw=(json.dumps(base.to_dict(),indent=4)+"\n").encode()
    axis=replace(base,positive_position_m=(.5,0,0),negative_position_m=(-.5,0,0),
                 external_field_N_C=(3,0,0))
    cases=[
        ("illustration35_default",base,(1440,960),None),
        ("illustration35_small",base,(840,560),None),
        ("parallel",axis,(840,560),None),
        ("perpendicular",replace(axis,positive_position_m=(0,.5,0),negative_position_m=(0,-.5,0)),(840,560),None),
        ("antiparallel",replace(axis,positive_position_m=(-.5,0,0),negative_position_m=(.5,0,0)),(840,560),None),
        ("zero_field",replace(base,external_field_N_C=(0,0,0)),(840,560),None),
        ("zero_charge",replace(base,charge_C=0),(840,560),None),
        ("changed_reference",base,(840,560),"change"),
        ("prediction",base,(840,560),"predict"),
        ("translated_origin",base,(840,560),"translate"),
    ]
    report=[]
    for name,state,size,action in cases:
        v=DipoleLesson(state,off_screen=True,window_size=size)
        try:
            v.plot.show(auto_close=False,interactive=False)
            if action=="change":v.set_dipole_polar(100.);v.set_dipole_azimuth(-35.)
            if action=="predict":v.toggle_values()
            if action=="translate":v.translate_pair();v.move_origin()
            saved=save_snapshot(v.state,args.output/name,lesson=v,source_bytes=raw)
            report.append({"name":name,"screenshot":saved["screenshot"],
                           "physics_status":saved["physics"]["status"],
                           "angle_available":saved["physics"]["angle_available"]})
        finally:v.plot.close()
    (args.output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    (args.output/"integrity.json").write_text(json.dumps({"files":{
        p.relative_to(args.output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.rglob("*")) if p.is_file()}},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"scenes":len(report),"execution_complete":True,"teacher_acceptance":"not_evaluated"}))


if __name__=="__main__":main()
