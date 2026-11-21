"""Interactive PyVista teaching display of a static IDEAL parallel-plate capacitor.

Run: python -m emfeeld.capacitor_view examples/lessons/parallel_plate_capacitor.json
Use --headless NEW_FOLDER without graphics, --snapshot NEW_FOLDER for a PNG.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import platform
from pathlib import Path
import math

import numpy as np

from .capacitor_lesson import CapacitorState, measure, load_lesson, parse_lesson, teaching_case
from .capacitor_presentation import prepare
from .output_safety import protect_saved_evidence


def _json(path, data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False,sort_keys=True)+'\n',encoding='utf-8')


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _window(size):
    if (not isinstance(size,(tuple,list)) or len(size)!=2
            or any(type(v) is not int for v in size)
            or not (840<=size[0]<=3840 and 560<=size[1]<=2160)):
        raise ValueError('window size must be integers 840..3840 by 560..2160')
    return tuple(size)


class CapacitorLesson:
    """PyVista draws prepared data; physical edits replace complete immutable state."""
    def __init__(self, state, *, off_screen=False, window_size=(1280,800)):
        if not isinstance(state,CapacitorState):
            raise ValueError('requires validated capacitor state')
        import pyvista as pv
        self.pv=pv
        self.initial=self.state=state
        self.prepared=prepare(state)
        self.preparation_count=1
        self.show_values=True
        self.preset_label=None
        self.notice=''
        self.plot=pv.Plotter(shape=(1,2),col_weights=(.59,.41),border=False,
                             window_size=_window(window_size),off_screen=off_screen)
        self.plot.subplot(0,0);self.plot.set_background('#ffffff',all_renderers=False)
        self.plot.subplot(0,1);self.plot.set_background('#f2f6fa',all_renderers=False)
        self._building=True
        self._right_actor=None
        self._right_note=None
        self.sliders=[]
        for callback,limits,value,title,y in [
            (self.set_kappa,(1.,10.),state.relative_permittivity,'Dielectric kappa',.27),
            (self.set_gap_factor,(.5,1.5),1.,'Gap / initial',.16),
        ]:
            slider=self.plot.add_slider_widget(
                lambda v,cb=callback:self._slider_event(cb,v),limits,
                value=value,title=title,pointa=(.11,y),pointb=(.88,y),
                title_height=.020,interaction_event='end',color='#173b56',
                slider_width=.019,tube_width=.004)
            slider.GetRepresentation().ShowSliderLabelOff()
            self.sliders.append(slider)
        events={'1':lambda:self.preset('1'),'2':lambda:self.preset('2'),
                '3':lambda:self.preset('3'),'4':lambda:self.preset('4'),
                '0':self.reset,'v':self.toggle_values,
                'i':lambda:self.change_mode('isolated_charge'),
                'b':lambda:self.change_mode('battery_voltage')}
        for key,fn in events.items():
            self.plot.add_key_event(key,lambda cb=fn:self._key_event(cb))
        self._building=False
        self.redraw(reset_camera=True)

    def _slider_event(self,cb,value):
        if self._building:return
        self.notice=''
        try:cb(float(value))
        except ValueError as exc:
            self.notice='Control refused: '+str(exc)
            self.redraw()

    def _key_event(self,cb):
        self.notice=''
        try:cb()
        except ValueError as exc:
            self.notice='Key refused: '+str(exc)
            self.redraw()

    def _apply(self,new,*,preset=None,reveal=None):
        # Transaction: model and prepared data must both succeed before swap.
        prepared=prepare(new)
        if new!=self.state:
            self.preparation_count+=1
        self.state=new
        self.prepared=prepared
        self.preset_label=preset
        if reveal is not None:self.show_values=reveal
        self.redraw()

    def set_kappa(self,value):
        self._apply(replace(self.state,relative_permittivity=value))

    def set_gap_factor(self,factor):
        self._apply(replace(self.state,gap_m=self.initial.gap_m*factor))

    def change_mode(self,mode):
        if self.state.mode==mode:
            self.redraw();return
        m=self.prepared.measurements
        new=CapacitorState(area_m2=self.state.area_m2,gap_m=self.state.gap_m,
            relative_permittivity=self.state.relative_permittivity,mode=mode,
            charge_C=m['free_lower_plate_charge_C'] if mode=='isolated_charge' else None,
            voltage_V=m['potential_lower_minus_upper_V'] if mode=='battery_voltage' else None)
        self._apply(new)

    def preset(self,key):
        self._apply(teaching_case(self.initial,key),preset=key,reveal=False)

    def toggle_values(self):
        self.show_values=not self.show_values
        self.redraw()

    def reset(self):
        self._apply(self.initial,reveal=True)

    def _sync_widgets(self):
        self._building=True
        try:
            for widget,value in zip(self.sliders,(self.state.relative_permittivity,
                                               self.state.gap_m/self.initial.gap_m)):
                widget.GetRepresentation().SetValue(float(value))
        finally:self._building=False

    def redraw(self,*,reset_camera=False):
        """Only reads prepared data; camera/reveal calls do not evaluate physics."""
        pv,p=self.pv,self.plot
        d,m=self.prepared,self.prepared.measurements
        p.subplot(0,0)
        camera=None if reset_camera else p.camera_position
        p.renderer.clear()
        bottom=pv.PolyData(d.lower_plate_xyz,faces=[4,0,1,2,3])
        top=pv.PolyData(d.upper_plate_xyz,faces=[4,0,1,2,3])
        q=m['free_lower_plate_charge_C']
        lower_color='#e46c58' if q>0 else '#527db1' if q<0 else '#8a969f'
        upper_color='#527db1' if q>0 else '#e46c58' if q<0 else '#8a969f'
        p.add_mesh(bottom,color=lower_color,opacity=.90,
                   show_edges=True,edge_color='#344e61',line_width=2,reset_camera=False)
        p.add_mesh(top,color=upper_color,opacity=.90,
                   show_edges=True,edge_color='#344e61',line_width=2,reset_camera=False)
        if d.dielectric_visible:
            material=pv.Cube(bounds=(-.48,.48,-.48,.48,-.46,.46))
            p.add_mesh(material,color='#efcf75',opacity=.19,
                       show_edges=False,reset_camera=False)
        for origin,vector in zip(d.arrow_origins_xyz,d.field_arrows_xyz):
            length=float(np.linalg.norm(vector))
            p.add_mesh(pv.Arrow(start=origin,direction=vector,scale=length,
                                shaft_radius=.020,tip_radius=.058,tip_length=.24),
                       color='#128e85',reset_camera=False)
        p.add_text('IDEAL PARALLEL PLATES',position='upper_left',font_size=13,
                   color='#19374f')
        p.add_text('Red: +free plate  |  Blue: -free plate  |  Gray: neutral\n'
                   'Green: schematic field direction\n'
                   'Gap EXAGGERATED; finite-plate fringing omitted',
                   position='lower_left',font_size=10,color='#304a60')
        p.add_axes()
        if camera is None:
            p.camera_position=[(1.55,-1.80,1.30),(0,0,0),(0,0,1)]
            p.camera.parallel_projection=True
            p.camera.parallel_scale=1.19
        else:p.camera_position=camera
        p.subplot(0,1)
        if self._right_actor is not None:
            p.remove_actor(self._right_actor,reset_camera=False)
        if self._right_note is not None:
            p.remove_actor(self._right_note,reset_camera=False)
            self._right_note=None
        mode='ISOLATED (fixed free Q)' if self.state.mode=='isolated_charge' else 'BATTERY (fixed terminal V)'
        case={'1':'VACUUM / fixed Q','2':'DIELECTRIC / fixed Q',
              '3':'VACUUM / fixed V','4':'DIELECTRIC / fixed V'}.get(self.preset_label,'CUSTOM')
        fmt=lambda x:f'{x:.5g}'
        lines=['CAPACITANCE | JEE 3D V1','',mode,f'Case: {case}',
               f'Area A = {fmt(self.state.area_m2)} m^2',
               f'Gap d = {fmt(self.state.gap_m)} m',
               f'kappa = {fmt(self.state.relative_permittivity)}',
               '', 'PREDICT before revealing (V):']
        if not self.show_values:
            lines+=['How do C, E and stored U change?',
                    'Does the dielectric change free Q or V?',
                    'What remains fixed in this mode?',
                    'Derived answers are hidden.']
        else:
            lines+=['C = '+fmt(m['capacitance_F'])+' F',
                    'Q(lower) = '+fmt(m['free_lower_plate_charge_C'])+' C',
                    'V(lower-upper) = '+fmt(m['potential_lower_minus_upper_V'])+' V',
                    'E_z = '+fmt(m['field_z_between_N_C'])+' N/C',
                    'Stored U = '+fmt(m['stored_field_energy_J'])+' J',
                    'P_z = '+fmt(m['polarization_z_C_m2'])+' C/m^2',
                    'Bound sigma lower = '+fmt(m['bound_surface_density_lower_C_m2'])+' C/m^2']
        lines+=['','1/2: vacuum/dielectric, fixed Q',
                '3/4: vacuum/dielectric, fixed V',
                'V: predict/reveal  I/B: isolated/battery',
                '0: reset; mouse: rotate and zoom',
                'All scenes static; no battery-work solver.',
                'No fringe field or dielectric motion.']
        self._right_actor=p.add_text('\n'.join(lines),position='upper_left',font_size=11,
                   color='#1d405a')
        if self.notice:
            self._right_note=p.add_text(self.notice,position='lower_left',font_size=10,color='#b43c27')
        self._sync_widgets()
        p.subplot(0,0);p.render()

    def display_state(self):
        return {'show_values':self.show_values,'preset':self.preset_label,
                'notice':self.notice,'preparation_count':self.preparation_count,
                'camera_position':list(map(list,self.plot.camera_position)),
                'window_size':list(self.plot.window_size),
                'gap_exaggeration':self.prepared.display_gap_exaggeration,
                'original_and_current_states_distinct':self.state!=self.initial}


def save_snapshot(state,output,*,lesson=None,source_bytes=None):
    """Save actual current model, SI arrays, graphics receipt; never overwrite."""
    protect_saved_evidence(output,new_directory=True)
    original = parse_lesson(source_bytes) if source_bytes is not None else None
    if lesson is not None:state=lesson.state
    d=lesson.prepared if lesson is not None else prepare(state)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    _json(output/'started.json',{'completed':False,'lesson':'capacitor_v1'})
    try:
        _json(output/'lesson.json',state.to_dict())
        if source_bytes is not None:
            (output/'authored-input.json').write_bytes(source_bytes)
        np.savez_compressed(output/'field_samples.npz',
            points_m=d.field_sample_positions_m,vectors_N_C=d.field_samples_N_C)
        report={'physics':dict(d.measurements),'display':lesson.display_state() if lesson else None,
                'model':'ideal_parallel_plate_no_fringing',
                'schematic_gap_factor':d.display_gap_exaggeration,
                'source_sha256':_sha(source_bytes) if source_bytes is not None else None,
                'input_equals_current':original == state if original is not None else None,
                'screenshot':None,'teacher_usefulness':'not_evaluated',
                'original_exam_question':'not_claimed',
                'code_sha256':{name:_sha((Path(__file__).parent/name).read_bytes())
                    for name in ('capacitor_lesson.py','capacitor_presentation.py','capacitor_view.py')}}
        if lesson is not None:
            lesson.plot.render()
            im=lesson.plot.screenshot(str(output/'view.png'),return_img=True)
            if im is None or float(np.std(im))<1.:
                raise RuntimeError('missing or blank native screenshot')
            report['screenshot']={'name':'view.png','sha256':_sha((output/'view.png').read_bytes())}
        _json(output/'report.json',report)
        _json(output/'outcome.json',{'completed':True})
        _json(output/'integrity.json',{'files':{p.name:_sha(p.read_bytes())
            for p in sorted(output.iterdir()) if p.is_file()}})
        return report
    except Exception as exc:
        _json(output/'outcome.json',{'completed':False,'error':type(exc).__name__,
                                    'reason':str(exc)})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--headless',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--case',choices=['1','2','3','4'])
    parser.add_argument('--window-size',nargs=2,type=int,default=(1280,800))
    args=parser.parse_args(argv)
    if args.headless and args.snapshot:
        parser.error('choose --headless OR --snapshot')
    raw=args.input.read_bytes()
    state=load_lesson(args.input)
    if args.headless:
        state=teaching_case(state,args.case) if args.case else state
        save_snapshot(state,args.headless,source_bytes=raw)
        return
    lesson=CapacitorLesson(state,off_screen=bool(args.snapshot),window_size=_window(args.window_size))
    try:
        if args.case:lesson.preset(args.case)
        if args.snapshot:
            lesson.plot.show(auto_close=False,interactive=False)
            save_snapshot(state,args.snapshot,lesson=lesson,source_bytes=raw)
        else:lesson.plot.show()
    finally:lesson.plot.close()


if __name__=='__main__':
    main()
