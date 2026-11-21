"""JEE right-hand-rule/Ampere-circle PyVista lesson of an ideal infinite wire.

Physics is calculated only in wire_magnetism and wire_presentation. The viewer
is a drawing adapter; graphics actors and arrows are explicitly schematic.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .wire_magnetism import WireState, load_lesson, parse_lesson, teaching_case
from .wire_presentation import prepare
from .output_safety import protect_saved_evidence


def _json(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)+'\n',encoding='utf-8')


def _sha(b):return hashlib.sha256(b).hexdigest()


class WireLesson:
    """Static physical state changes prepare once; camera/reveal only draw."""
    def __init__(self, state: WireState, *, off_screen=False, window_size=(1200,760)):
        if not isinstance(state,WireState):raise ValueError('requires validated WireState')
        import pyvista as pv
        self.pv=pv
        self.initial=self.state=state
        self.prepared=prepare(state)
        self.preparation_count=1
        self.show_values=True
        self.case_label=None
        self.notice=''
        self.plot=pv.Plotter(shape=(1,2),col_weights=(.62,.38),border=False,
                             window_size=window_size,off_screen=off_screen)
        self.plot.subplot(0,0);self.plot.set_background('#ffffff',all_renderers=False)
        self.plot.subplot(0,1);self.plot.set_background('#eef4f8',all_renderers=False)
        self._building=True
        self._info_actor=None
        self._warning_actor=None
        self.slider=self.plot.add_slider_widget(
            lambda v:self._event(lambda:self.change_radius(float(v))),(.5,2.0),
            value=1.0,title='Ampere loop radius / initial',
            pointa=(.15,.17),pointb=(.89,.17),title_height=.018,
            interaction_event='end',color='#183f59',slider_width=.020,tube_width=.005)
        self.slider.GetRepresentation().ShowSliderLabelOff()
        keys={'1':lambda:self.preset('1'),'2':lambda:self.preset('2'),
              '3':lambda:self.preset('3'),'4':lambda:self.preset('4'),
              'n':self.reverse_current,'v':self.toggle_values,'0':self.reset}
        for key,callback in keys.items():
            self.plot.add_key_event(key,lambda f=callback:self._event(f))
        self._building=False
        self.redraw(reset_camera=True)

    def _event(self,f):
        if self._building:return
        self.notice=''
        try:f()
        except ValueError as exc:
            self.notice='Control refused: '+str(exc)
            self.redraw()

    def _apply(self,state,*,case=None,reveal=None):
        if state != self.state:
            new_data=prepare(state)  # atomic preparation before replacing state
            self.state=state
            self.prepared=new_data
            self.preparation_count+=1
        self.case_label=case
        if reveal is not None:self.show_values=reveal
        self.redraw()

    def change_radius(self,ratio):
        if not math.isfinite(ratio):raise ValueError('radius ratio must be finite')
        self._apply(replace(self.state,loop_radius_m=self.initial.loop_radius_m*ratio))

    def reverse_current(self):
        self._apply(replace(self.state,current_A=-self.state.current_A))

    def preset(self,key):
        self._apply(teaching_case(self.initial,key),case=key,reveal=False)

    def toggle_values(self):
        self.show_values=not self.show_values
        self.redraw()

    def reset(self):
        self._apply(self.initial,case=None,reveal=True)

    def _sync_slider(self):
        self._building=True
        try:self.slider.GetRepresentation().SetValue(self.state.loop_radius_m/self.initial.loop_radius_m)
        finally:self._building=False

    def redraw(self,*,reset_camera=False):
        pv,p=self.pv,self.plot
        data,physical=self.prepared,self.prepared.report
        p.subplot(0,0)
        camera=None if reset_camera else p.camera_position
        p.renderer.clear()
        wire=data.wire_display_endpoints_xyz
        p.add_mesh(pv.Line(wire[0],wire[1]).tube(radius=.035),color='#263e57',
                   reset_camera=False)
        if self.state.current_A:
            u=np.asarray(self.state.axis_direction)* (1 if self.state.current_A>0 else -1)
            p.add_mesh(pv.Arrow(start=-.75*u,direction=u,scale=1.35,
                                shaft_radius=.028,tip_radius=.083,tip_length=.23),
                       color='#d95b33',reset_camera=False)
        ring=np.asarray(data.loop_display_xyz)
        p.add_mesh(pv.lines_from_points(np.vstack((ring,ring[0])),close=False),
                   color='#2374b9',line_width=4,reset_camera=False)
        # Draw an unambiguous POSITIVE circulation arrow even at I=0: this is
        # the oriented integration path, NOT the field direction. Its direction
        # comes exclusively from the renderer-neutral, SI tangent_unit data.
        # Centre the blue arrow on a polygon edge, separately from the green
        # B arrows; never derive it from a B vector or its sign.
        i=len(ring)//5
        j=(i+1)%len(ring)
        centre=(ring[i]+ring[j])/2
        positive_tangent=np.asarray(data.tangent_unit[i]+data.tangent_unit[j])
        positive_tangent=positive_tangent/np.linalg.norm(positive_tangent)
        arrow_length=.40  # schematic display units, never an SI arc weight
        arrow_start=centre-.5*arrow_length*positive_tangent
        self.positive_loop_arrow_direction=positive_tangent.copy()
        self.positive_loop_arrow_origin=arrow_start.copy()
        self.positive_loop_arrow_mesh=pv.Arrow(
            start=arrow_start,direction=positive_tangent,scale=arrow_length,
            shaft_radius=.050,tip_radius=.135,tip_length=.32)
        self.positive_loop_arrow_actor=p.add_mesh(
            self.positive_loop_arrow_mesh,color='#2374b9',
            name='positive_ampere_circulation_arrow',reset_camera=False)
        # Actual B direction-only arrows are computed in presentation from SI B;
        # their drawn lengths are NOT magnetic strengths or integral weights.
        for origin,vec in zip(data.arrow_display_origins_xyz,data.arrow_display_vectors):
            length=float(np.linalg.norm(vec))
            if length:
                p.add_mesh(pv.Arrow(start=origin,direction=vec,scale=length,
                                    shaft_radius=.047,tip_radius=.100,tip_length=.26),
                           color='#079e86',reset_camera=False)
        p.add_text('MAGNETIC FIELD  |  INFINITE STRAIGHT WIRE',
                   position='upper_left',font_size=12,color='#163f58')
        p.add_text('Blue arrow: FIXED + Ampere circulation  |  Green: B direction\n'
                   'Orange: signed current  |  Wire truncated ONLY for display\n'
                   'Field and loop units are SI; glyph sizes are NOT B magnitude',
                   position='lower_left',font_size=10,color='#324e61')
        p.add_axes()
        if camera is None:
            p.camera_position=[(3.4,-4.2,3.3),(0.,0.,0.),(0.,0.,1.)]
            p.camera.parallel_projection=True
            p.camera.parallel_scale=2.65
        else:p.camera_position=camera
        p.subplot(0,1)
        if self._info_actor is not None:p.remove_actor(self._info_actor,reset_camera=False)
        if self._warning_actor is not None:
            p.remove_actor(self._warning_actor,reset_camera=False)
            self._warning_actor=None
        case={'1':'BASE RADIUS','2':'DOUBLE RADIUS',
              '3':'REVERSED CURRENT','4':'ZERO CURRENT'}.get(self.case_label,'CUSTOM')
        lines=['JEE MAGNETOSTATICS 3D V1','',
               'Single ideal infinite straight wire',
               'Vacuum; steady signed current',
               f'Case: {case}',
               f'I = {self.state.current_A:.5g} A',
               f'Physical radius R = {self.state.loop_radius_m:.5g} m',
               f'Sampled loop positions: {self.state.samples_per_loop}',
               '', 'PREDICT before reveal (V):']
        if self.show_values:
            lines += [f'B magnitude = {physical["field_magnitude_T"]:.6g} T',
                      f'Signed tangential B = {physical["signed_tangent_field_T"]:.6g} T',
                      f'Sampled integral = {physical["sampled_ampere_circulation_T_m"]:.6g} T m',
                      f'Exact mu0 I = {physical["expected_mu0_I_T_m"]:.6g} T m']
        else:
            lines += ['What happens to B if R doubles?',
                      'Does the Ampere circulation change?',
                      'Does reversing I reverse the arrows?',
                      'Numeric answers are hidden.']
        lines += ['', '1: initial radius     2: double radius',
                  '3: reverse I       4: I = 0',
                  'N: reverse live I  V: predict/reveal',
                  '0: reset; mouse: orbit/zoom',
                  'Slider: Ampere loop radius ratio',
                  '', 'No end fields, magnetic force,',
                  'solenoid or material permeability.']
        self._info_actor=p.add_text('\n'.join(lines),position='upper_left',
                                    font_size=11,color='#193f58')
        if self.notice:
            self._warning_actor=p.add_text(self.notice,position='lower_left',
                                            font_size=9,color='#af3b28')
        self._sync_slider()
        p.subplot(0,0);p.render()

    def display_state(self):
        return {'show_values':self.show_values,'case':self.case_label,
                'notice':self.notice,'preparation_count':self.preparation_count,
                'camera_position':list(map(list,self.plot.camera_position)),
                'window_size':list(self.plot.window_size),
                'current_slider_radius_factor':self.slider.GetRepresentation().GetValue(),
                'original_and_current_states_distinct':self.initial!=self.state,
                'schematic_wire_display_endpoints':self.prepared.wire_display_endpoints_xyz.tolist(),
                'positive_loop_arrow_origin_display':self.positive_loop_arrow_origin.tolist(),
                'positive_loop_arrow_direction_display':self.positive_loop_arrow_direction.tolist(),
                'loop_direction_is_positive_circulation_not_B':True,
                'schematic_B_glyph_length':.42}


def save_snapshot(authored: WireState, destination, *, lesson=None, current_state=None, source_bytes=None):
    """Create a *new* snapshot with original/current physical state provenance."""
    if not isinstance(authored,WireState):raise ValueError('requires authored WireState')
    protect_saved_evidence(destination,new_directory=True)
    if source_bytes is not None and parse_lesson(source_bytes) != authored:
        raise ValueError("original input differs from authored wire state")
    if lesson is not None:
        if lesson.initial != authored or (current_state is not None and current_state != lesson.state):
            raise ValueError("live wire lesson conflicts with snapshot state")
        if lesson.prepared.state != lesson.state:
            raise ValueError("prepared wire data differs from current state")
    dest=Path(destination)
    dest.mkdir(parents=True,exist_ok=False)
    _json(dest/'started.json',{'completed':False,'lesson':'wire_magnetism_v1'})
    try:
        state=lesson.state if lesson is not None else (current_state or authored)
        if not isinstance(state,WireState):raise ValueError('requires validated current WireState')
        data=lesson.prepared if lesson is not None else prepare(state)
        original_bytes=source_bytes if source_bytes is not None else json.dumps(authored.to_dict(),allow_nan=False,sort_keys=True).encode()
        (dest/'authored-input.json').write_bytes(original_bytes)
        _json(dest/'lesson.json',state.to_dict())
        np.savez_compressed(dest/'field_samples.npz',
            positions_m=data.loop_positions_m,
            tangent_unit=data.tangent_unit,
            magnetic_field_T=data.magnetic_field_T,
            arc_weights_m=data.arc_weights_m,
            loop_display_xyz=data.loop_display_xyz,
            B_arrow_display_vectors=data.arrow_display_vectors)
        code_files=('wire_magnetism.py','wire_presentation.py','wire_view.py')
        codes={f:_sha((Path(__file__).parent/f).read_bytes()) for f in code_files}
        report={'model':'ideal_infinite_straight_current_wire',
                'original_input_sha256':_sha(original_bytes),
                'source_code_sha256':codes,
                'authored_state':authored.to_dict(),'current_state':state.to_dict(),
                'physics':dict(data.report),
                'display':lesson.display_state() if lesson else {'rendered':False,'schematic':True},
                'renderer':'PyVista real screenshot' if lesson else 'none (headless)'}
        _json(dest/'report.json',report)
        if lesson is not None:
            lesson.plot.render()
            lesson.plot.screenshot(str(dest/'view.png'))
        _json(dest/'outcome.json',{'completed':True,'renderer':report['renderer']})
    except Exception:
        _json(dest/'outcome.json',{'completed':False,'error':'snapshot_failed'})
        raise
    finally:
        hashes={p.name:_sha(p.read_bytes()) for p in dest.iterdir() if p.is_file() and p.name!='integrity.json'}
        _json(dest/'integrity.json',{'files':hashes})
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description='Ideal infinite wire JEE magnetostatics lesson')
    parser.add_argument('input',type=Path)
    parser.add_argument('--case',choices=('1','2','3','4'),default=None)
    output=parser.add_mutually_exclusive_group()
    output.add_argument('--snapshot',type=Path,metavar='NEW_DIR')
    output.add_argument('--headless',type=Path,metavar='NEW_DIR')
    parser.add_argument('--window-size',nargs=2,type=int,default=[1200,760])
    args=parser.parse_args(argv)
    raw=args.input.read_bytes()
    state=load_lesson(args.input)
    current=teaching_case(state,args.case) if args.case else state
    if args.headless:
        save_snapshot(state,args.headless,current_state=current,source_bytes=raw)
        print('Headless magnetic loop report saved to',args.headless)
        return 0
    obj=WireLesson(state,off_screen=bool(args.snapshot),window_size=tuple(args.window_size))
    if args.case:
        obj.preset(args.case)
    try:
        if args.snapshot:
            obj.plot.show(auto_close=False,interactive=False)
            save_snapshot(state,args.snapshot,lesson=obj,source_bytes=raw)
            print('Actual PyVista image and state saved to',args.snapshot)
        else:
            obj.plot.show()
    finally:
        obj.plot.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
