"""Opt-in 3D JEE electric-dipole lesson; static poses, not rotational dynamics.

python -m emfeeld.dipole_view examples/lessons/dipole_uniform.json
--snapshot NEW_DIRECTORY captures the live state; --headless needs no graphics.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from .dipole_lesson import DipoleState, measure, norm, number, vector, orientation_work, parse_lesson
from .output_safety import protect_saved_evidence

MINIMUM_WINDOW_SIZE=(840,560)


def _angles(v):
    v=np.asarray(v,dtype=float)
    if not norm(v):return (90.,0.)
    return (math.degrees(math.atan2(math.hypot(v[0],v[1]),v[2])),
            math.degrees(math.atan2(v[1],v[0])))


def _sincos(degrees):
    # Cardinal input angles have exact cardinal directions, not a hidden epsilon.
    a=degrees % 360.
    exact={0.:(0.,1.),90.:(1.,0.),180.:(0.,-1.),270.:(-1.,0.)}
    return exact[a] if a in exact else (math.sin(math.radians(a)),math.cos(math.radians(a)))


def _direction(theta,phi):
    st,ct=_sincos(theta);sp,cp=_sincos(phi)
    return np.array([st*cp,st*sp,ct])


def _window(size):
    if (not isinstance(size,(list,tuple)) or len(size)!=2
            or any(type(v) is not int for v in size)
            or not (840 <= size[0] <= 3840 and 560 <= size[1] <= 2160)):
        raise ValueError("window must be integer pixels within 840..3840 by 560..2160")
    return tuple(size)


class DipoleLesson:
    """Actual PyVista controller with immutable physical configurations."""
    def __init__(self,state,*,off_screen=False,window_size=(1440,960)):
        if not isinstance(state,DipoleState):
            raise ValueError("requires a validated DipoleState")
        measure(state)
        window_size=_window(window_size)
        import pyvista as pv
        self.pv=pv
        self.state=self.initial=self.reference=state
        self.unit=state.separation_m
        self.field_unit=norm(state.external_field_N_C) or 1.
        self.charge_unit=state.charge_C or 1e-9
        self.show_values=True
        self.control_notice=""
        self.dipole_angles=_angles(state.separation_vector_m)
        self.field_angles=_angles(state.external_field_N_C)
        self.plot=pv.Plotter(shape=(1,2),col_weights=(.62,.38),border=False,
                            window_size=window_size,off_screen=off_screen)
        self.plot.subplot(0,0);self.plot.set_background("white",all_renderers=False)
        self.plot.subplot(0,1);self.plot.set_background("#f2f5f8",all_renderers=False)
        self._building=True
        self.sliders=[]
        self._annotations={}
        self._layout_pixels=None
        specs=[(self.set_dipole_polar,(0,180),self.dipole_angles[0],"Dipole polar [deg]"),
               (self.set_dipole_azimuth,(-180,180),self.dipole_angles[1],"Dipole azimuth [deg]"),
               (self.set_field_polar,(0,180),self.field_angles[0],"E polar [deg]"),
               (self.set_field_azimuth,(-180,180),self.field_angles[1],"E azimuth [deg]"),
               (self.set_separation_factor,(.5,2),1.,"Separation / initial"),
               (self.set_field_factor,(0,2),norm(state.external_field_N_C)/self.field_unit,"E magnitude / reference")]
        self.slider_titles=[s[3] for s in specs]
        for i,(callback,limits,value,title) in enumerate(specs):
            w=self.plot.add_slider_widget(lambda v,cb=callback:self._slider_event(cb,v),limits,value=value,title=title,
                pointa=(.10,.48-i*.075),pointb=(.90,.48-i*.075),
                title_height=.022,interaction_event="end",color="#17394d",
                slider_width=.018,tube_width=.004)
            w.GetRepresentation().ShowSliderLabelOff()
            self.sliders.append(w)
        keys={"n":self.reverse_dipole,"q":self.cycle_charge,"v":self.toggle_values,
              "b":self.set_work_reference,"t":self.translate_pair,"o":self.move_origin,
              "1":lambda:self.preset("parallel"),"2":lambda:self.preset("perpendicular"),
              "3":lambda:self.preset("antiparallel"),"0":self.reset}
        for key,callback in keys.items():self.plot.add_key_event(key,lambda cb=callback:self._key_event(cb))
        self._building=False
        self.redraw(reset_camera=True)
        self._resize_observer=self.plot.ren_win.AddObserver("StartEvent",self._layout)

    def _slider_event(self,callback,value):
        if self._building:return
        self.control_notice=""
        try:callback(value)
        except ValueError:
            self.control_notice="Control refused: outside lesson limits."
            self.redraw()  # restore actual-state titles and widget values

    def _key_event(self,callback):
        self.control_notice=""
        try:callback()
        except ValueError:
            self.control_notice="Control refused: no valid pose for this key."
            self.redraw()

    def _apply(self,proposed):
        if not isinstance(proposed,DipoleState):raise ValueError("invalid physical state")
        measure(proposed)  # fail precision/refusal before replacing live state
        previous=self.state
        self.state=proposed
        try:self.redraw()
        except Exception:
            self.state=previous
            self.redraw()
            raise

    def _orient_pair(self,theta,phi):
        delta=self.state.separation_m*_direction(theta,phi)
        center=self.state.center_m
        self._apply(replace(self.state,positive_position_m=center+delta/2,
                            negative_position_m=center-delta/2))

    def _set_angle(self,kind,index,value):
        if self._building:return
        value=number(value,"angle")
        lo,hi=(0,180) if index==0 else (-180,180)
        if not lo <= value <= hi:raise ValueError("angle outside control range")
        old=self.dipole_angles if kind=="dipole" else self.field_angles
        angles=list(old);angles[index]=value
        if kind=="dipole":
            self._orient_pair(*angles)
        else:
            proposed=replace(self.state,external_field_N_C=norm(self.state.external_field_N_C)*_direction(*angles))
            self._apply(proposed)
        # At a pole or zero field an azimuth can be an inactive control setting.
        if kind=="dipole":self.dipole_angles=tuple(angles)
        else:self.field_angles=tuple(angles)
        self._sync_widgets()

    def set_dipole_polar(self,v):self._set_angle("dipole",0,v)
    def set_dipole_azimuth(self,v):self._set_angle("dipole",1,v)
    def set_field_polar(self,v):self._set_angle("field",0,v)
    def set_field_azimuth(self,v):self._set_angle("field",1,v)

    def set_separation_factor(self,value):
        if self._building:return
        value=number(value,"separation factor")
        if not .5 <= value <= 2:raise ValueError("separation factor outside [.5,2]")
        delta=self.state.separation_vector_m/self.state.separation_m*(self.unit*value)
        center=self.state.center_m
        self._apply(replace(self.state,positive_position_m=center+delta/2,negative_position_m=center-delta/2))

    def set_field_factor(self,value):
        if self._building:return
        value=number(value,"field factor")
        if not 0 <= value <= 2:raise ValueError("field factor outside [0,2]")
        self._apply(replace(self.state,external_field_N_C=self.field_unit*value*_direction(*self.field_angles)))

    def set_charge(self,value):
        self._apply(replace(self.state,charge_C=number(value,"charge magnitude")))

    def cycle_charge(self):
        options=tuple(dict.fromkeys((0.,self.charge_unit,min(2*self.charge_unit,1e-3))))
        present=next((i for i,q in enumerate(options) if q==self.state.charge_C),-1)
        self.set_charge(options[(present+1)%len(options)])

    def reverse_dipole(self):
        self._apply(replace(self.state,positive_position_m=self.state.negative_position_m,
                            negative_position_m=self.state.positive_position_m))
        self.dipole_angles=_angles(self.state.separation_vector_m);self._sync_widgets()

    def translate_pair(self):
        shift=np.array([.25*self.state.separation_m,0.,0.])
        self._apply(replace(self.state,positive_position_m=np.array(self.state.positive_position_m)+shift,
                            negative_position_m=np.array(self.state.negative_position_m)+shift))

    def move_origin(self):
        self._apply(replace(self.state,torque_origin_m=np.array(self.state.torque_origin_m)+
                            self.state.separation_m*np.array([.5,-.25,.25])))

    def preset(self,kind):
        if kind not in ("parallel","perpendicular","antiparallel"):raise ValueError("invalid preset")
        e=np.asarray(self.state.external_field_N_C)
        if not norm(e):
            raise ValueError("no preferred orientation at zero E; set a nonzero field first")
        u=e/norm(e)
        if kind=="antiparallel":u=-u
        elif kind=="perpendicular":
            basis=np.eye(3)[int(np.argmin(abs(u)))]
            u=np.cross(u,basis);u/=norm(u)
        center=self.state.center_m;delta=self.state.separation_m*u
        self._apply(replace(self.state,positive_position_m=center+delta/2,negative_position_m=center-delta/2))
        self.dipole_angles=_angles(self.state.separation_vector_m);self._sync_widgets()

    def set_work_reference(self):
        self.reference=self.state;self.redraw()

    def toggle_values(self):
        self.show_values=not self.show_values;self.redraw()

    def reset(self):
        self.state=self.reference=self.initial
        self.dipole_angles=_angles(self.state.separation_vector_m)
        self.field_angles=_angles(self.state.external_field_N_C)
        self.show_values=True
        self.redraw(reset_camera=True)

    def _sync_widgets(self):
        values=[*self.dipole_angles,*self.field_angles,self.state.separation_m/self.unit,
                norm(self.state.external_field_N_C)/self.field_unit]
        for widget,title,value in zip(self.sliders,self.slider_titles,values):
            rep=widget.GetRepresentation();rep.SetValue(value)
            rep.SetTitleText(f"{title}: {value:.5g}")

    def _text(self,name,text,position,role="body",color="#17394d"):
        actor=self.plot.add_text(text,position=position,viewport=True,font_size=16,
                                  color=color,name=name,font="arial",render=False)
        prop=actor.GetTextProperty();prop.SetVerticalJustificationToTop()
        self._annotations[name]=(actor,role)
        self._layout_pixels=None  # new actors must receive the current pixel fonts
        return actor

    def _layout(self,*_):
        size=tuple(self.plot.window_size)
        if size==self._layout_pixels:return
        scale=min(size[0]/1440.,size[1]/960.)
        self.fonts={"title":max(18,round(25*scale)),"body":max(12,round(18*scale)),
                    "help":max(11,round(16*scale))}
        for actor,role in self._annotations.values():
            actor.GetTextProperty().SetFontSize(self.fonts[role])
        self._layout_pixels=size

    def _glyph(self,name,anchor,physical_vector,unit,length,color):
        value=np.asarray(physical_vector,dtype=float)
        magnitude=norm(value)
        if not magnitude:return
        direction=value/magnitude
        mesh=self.pv.Arrow(start=anchor,direction=direction,scale=length,
                           tip_radius=.065,shaft_radius=.021)
        self.plot.add_mesh(mesh,color=color,reset_camera=False)
        self.glyph_meshes[name]=mesh
        self.glyph_records[name]={"anchor_display":list(map(float,anchor)),
            "physical_vector":value.tolist(),"physical_unit":unit,
            "direction":direction.tolist(),"display_length":length,
            "magnitude_scale":"schematic; not a common scale across quantities"}

    def redraw(self,*,reset_camera=False):
        p,pv=self.plot,self.pv
        self._annotations={};self._layout_pixels=None
        p.subplot(0,0)
        camera=None if reset_camera else p.camera_position
        p.renderer.clear()
        self.report=measure(self.state)
        self.work=orientation_work(self.reference,self.state)
        center=self.state.center_m;length=self.state.separation_m
        self.display_origin=center;self.display_scale=length
        plus=(np.array(self.state.positive_position_m)-center)/length
        minus=(np.array(self.state.negative_position_m)-center)/length
        u=self.state.separation_vector_m/length
        self.positions_display=np.stack([plus,minus])
        p.add_mesh(pv.Line(minus,plus),color="#677680",line_width=5,reset_camera=False)
        for pos,color,label in [(plus,"#c93541","+q"),(minus,"#285da6","-q")]:
            if self.state.charge_C==0:color,label="#83909b","0"
            p.add_mesh(pv.Sphere(radius=.075,center=pos,theta_resolution=20,phi_resolution=20),
                       color=color,reset_camera=False)
            p.add_point_labels([pos],[label],point_size=0,font_size=16,
                text_color=color,shape=None,show_points=False,always_visible=True)
        self.glyph_meshes={};self.glyph_records={}
        self._glyph("external_field",(-1.,-.8,-.7),self.state.external_field_N_C,"N/C",.9,"#16946c")
        self.rotation_cue_mesh=None;self.plane_mesh=None
        if self.show_values:
            self._glyph("positive_force",plus,self.report["positive_force_N"],"N",.85,"#df831d")
            self._glyph("negative_force",minus,self.report["negative_force_N"],"N",.85,"#df831d")
            self._glyph("dipole_moment",-1.1*u,self.report["dipole_moment_C_m"],"C m",.55,"#2565a8")
            tau=np.asarray(self.report["torque_N_m"])
            self._glyph("torque",np.zeros(3),tau,"N m",.95,"#8b4b9f")
            if norm(tau):
                n=tau/norm(tau);v=np.cross(n,u)
                corners=.55*np.array([-u-v,u-v,u+v,-u+v])
                self.plane_mesh=pv.PolyData(corners,faces=[4,0,1,2,3])
                p.add_mesh(self.plane_mesh,color="#bf9aca",opacity=.12,reset_camera=False)
                angle=min(math.radians(self.report["angle_deg"]),math.pi/3)
                a=np.linspace(0.,angle,32)
                curve=.35*(np.cos(a)[:,None]*u+np.sin(a)[:,None]*v)
                self.rotation_cue_mesh=pv.lines_from_points(curve)
                p.add_mesh(self.rotation_cue_mesh,color="#8b4b9f",line_width=3,reset_camera=False)
                # Tangent to a positive rotation about tau, not angular velocity.
                self._glyph("rotation_cue",curve[-1],np.cross(n,curve[-1]),"geometric cue",.14,"#8b4b9f")
        origin=(np.asarray(self.state.torque_origin_m)-center)/length
        self.origin_marker_visible=norm(origin)<=2.5
        if self.origin_marker_visible:
            p.add_mesh(pv.Sphere(radius=.035,center=origin),color="#333333",reset_camera=False)
            p.add_point_labels([origin],["O"],point_size=0,font_size=13,shape=None,
                               show_points=False,always_visible=True,text_color="#333333")
        self._text("title","DIPOLE: FORCE, TORQUE AND ENERGY",(.025,.98),"title")
        self._text("legend","Blue: p [C m]   Green: E [N/C]\nOrange: forces [N]   Purple: torque [N m]",(.025,.90),"help")
        self._text("instructions","Mouse: orbit. 1 / 2 / 3: parallel / perpendicular / antiparallel\n"
            "N reverse, Q charge, T translate, O origin\n"
            "V predict, B work reference, 0 reset\n"
            "Arrows: separate schematic scales; rod: rigid constraint\n"
            "Curved cue: torque sense, NOT simulated rotation.",(.025,.14),"help")
        p.add_axes(viewport=(.80,.17,.98,.35))
        if camera is None:
            p.camera_position=[(4.,-5.,3.),(0.,0.,0.),(0.,0.,1.)]
            p.camera.parallel_projection=True;p.camera.parallel_scale=1.7
        else:p.camera_position=camera
        p.subplot(0,1)
        fmt=lambda values:"("+", ".join(f"{x:+.3g}" for x in values)+")"
        lines=["RIGID DIPOLE - STATIC POSE",
               f"q = {self.state.charge_C:.5g} C; d = {length:.5g} m",
               "E [N/C] = "+fmt(self.state.external_field_N_C),
               "Center [m] = "+fmt(self.state.center_m)]
        if not self.show_values:
            lines+=["","PREDICT torque direction and energy.","Press V to reveal forces and values.",
                    "No rotation in time is being simulated."]
        else:
            lines+=["p [C m] = "+fmt(self.report["dipole_moment_C_m"]),
                    "F+ [N] = "+fmt(self.report["positive_force_N"]),
                    "F- [N] = "+fmt(self.report["negative_force_N"]),
                    "Net external force = (0, 0, 0) N",
                    "Torque [N m] = "+fmt(self.report["torque_N_m"]),
                    f'Uext = {self.report["external_orientation_energy_J"]:+.7g} J',
                    "Angle = "+("unavailable (p or E is zero)" if self.report["angle_deg"] is None
                                 else f'{self.report["angle_deg"]:.7g} deg'),
                    self.report["equilibrium"].replace("_"," "),
                    (f'Wext from ref = {self.work["external_work_J"]:+.6g} J'
                       if self.work["status"]=="available" else "Rotation work unavailable: q, d or E changed"),
                    "Field work = -Wext; B sets reference.",
                    "Uext excludes constant mutual energy.",
                    ("No preferred orientation when p or E = 0."
                     if self.report["equilibrium"]=="no_preferred_orientation"
                     else "Parallel stable / antiparallel unstable.")]
        lines+=["O [m] = "+fmt(self.state.torque_origin_m)]
        self._text("readout","\n".join(lines),(.025,.98))
        self._text("control-note",self.control_notice,(.025,.535),"help",color="#9b4126")
        self._layout();self._sync_widgets()
        p.subplot(0,0);p.render()

    def display_state(self):
        return {"values_visible":self.show_values,
                "control_notice":self.control_notice,
                "window_size_pixels":list(self.plot.window_size),
                "minimum_supported_window_size_pixels":list(MINIMUM_WINDOW_SIZE),
                "annotation_font_pixels":{name:int(actor.GetTextProperty().GetFontSize())
                    for name,(actor,_) in self._annotations.items()},
                "layout_font_targets":dict(self.fonts),
                "camera":[list(x) for x in self.plot.renderers[0].camera_position],
                "slider_values":[w.GetRepresentation().GetValue() for w in self.sliders],
                "slider_titles":[w.GetRepresentation().GetTitleText() for w in self.sliders],
                "display_origin_m":self.display_origin.tolist(),"display_scale_m":self.display_scale,
                "display_coordinates":"(world position - display_origin_m) / display_scale_m",
                "origin_marker_visible":self.origin_marker_visible,
                "glyphs":self.glyph_records,"rotation_cue_is_motion":False,
                "charge_control_reference_C":self.charge_unit,"field_control_reference_N_C":self.field_unit}


def _json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def save_snapshot(state,output,*,lesson=None,source_bytes=None,reference=None):
    """Capture current immutable physical state; original input bytes stay separate."""
    protect_saved_evidence(output,new_directory=True)
    if lesson is not None:state=lesson.state;reference=lesson.reference
    physics=measure(state)
    work=None if reference is None else orientation_work(reference,state)
    if source_bytes is not None and not isinstance(source_bytes,bytes):
        raise ValueError("source_bytes must contain the original bytes")
    authored=None if source_bytes is None else parse_lesson(source_bytes)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    try:
        _json(output/"started.json",{"execution_complete":False,"lesson":"electric_dipole_v1"})
        _json(output/"lesson.json",state.to_dict())
        if source_bytes is not None:(output/"authored-input.json").write_bytes(source_bytes)
        if reference is not None:_json(output/"work-reference.json",reference.to_dict())
        np.savez_compressed(output/"measurements.npz",
            positive_position_m=state.positive_position_m,negative_position_m=state.negative_position_m,
            external_field_N_C=state.external_field_N_C,dipole_moment_C_m=physics["dipole_moment_C_m"],
            positive_force_N=physics["positive_force_N"],negative_force_N=physics["negative_force_N"],
            torque_N_m=physics["torque_N_m"],external_orientation_energy_J=physics["external_orientation_energy_J"])
        report={"physics":physics,"orientation_work":work,
                "lesson_sha256":sha((output/"lesson.json").read_bytes()),
                "authored_input_sha256":None if source_bytes is None else sha(source_bytes),
                "original_input_equals_current_state":None if authored is None else authored==state,
                "work_reference_sha256":None if reference is None else sha((output/"work-reference.json").read_bytes()),
                "environment":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__},
                "implementation_sha256":{p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))},
                "display":None,"screenshot":None,"independent_review":"not_evaluated",
                "human_windows_acceptance":"not_evaluated","teacher_usefulness":"not_evaluated"}
        if lesson is not None:
            lesson.redraw()
            lesson.plot.render()
            if lesson.state!=state or lesson.reference!=reference:
                raise RuntimeError("physical state changed during capture")
            report["environment"].update(pyvista=lesson.pv.__version__,vtk=lesson.pv.vtk_version_info._asdict())
            image=lesson.plot.screenshot(str(output/"view.png"),return_img=True)
            if image is None or float(image.std())<1:raise RuntimeError("blank screenshot")
            if lesson.state!=state or lesson.reference!=reference:
                raise RuntimeError("physical state changed during screenshot")
            report["display"]=lesson.display_state()
            report["screenshot"]={"file":"view.png","sha256":sha((output/"view.png").read_bytes())}
        _json(output/"report.json",report)
        _json(output/"outcome.json",{"execution_complete":True,"measurements_available":True,
                                     "angle_available":physics["angle_available"],"time_dynamics":False})
        _json(output/"integrity.json",{"files":{p.name:sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}})
        return report
    except Exception as exc:
        _json(output/"outcome.json",{"execution_complete":False,"failure_type":type(exc).__name__,"message":str(exc)})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson_file",type=Path)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot",type=Path);mode.add_argument("--headless",type=Path)
    mode.add_argument("--validate-only",action="store_true")
    parser.add_argument("--window-size",nargs=2,type=int,default=(1440,960),metavar=("WIDTH","HEIGHT"))
    args=parser.parse_args(argv);output=args.snapshot or args.headless
    try:
        if output is not None:protect_saved_evidence(output,new_directory=True)
        raw=args.lesson_file.read_bytes();state=parse_lesson(raw)
        if args.validate_only:print(json.dumps({"valid":True,"physics":measure(state)}));return 0
        if args.headless:save_snapshot(state,output,source_bytes=raw);return 0
        lesson=DipoleLesson(state,off_screen=bool(args.snapshot),window_size=tuple(args.window_size))
        try:
            if args.snapshot:
                lesson.plot.show(auto_close=False,interactive=False)
                save_snapshot(state,output,lesson=lesson,source_bytes=raw)
            else:lesson.plot.show()
        finally:lesson.plot.close()
        return 0
    except (ValueError,OSError) as exc:
        print(f"dipole-lesson: {exc}",file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
