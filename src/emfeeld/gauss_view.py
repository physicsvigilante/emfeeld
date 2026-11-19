"""Opt-in, static JEE Gauss-law lesson. No conductor response or particle motion.

python -m emfeeld.gauss_view examples/lessons/gauss_cube.json
--snapshot NEW_DIRECTORY retains the actual displayed state and image.
--headless NEW_DIRECTORY records flux without importing PyVista.
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
from scipy.constants import epsilon_0

from .gauss_lesson import (GaussState, GaussianCube, GaussianSphere, HeldCharge,
    _finite_scalar, load_lesson, parse_lesson, measure)
from .gauss_presentation import (FACE_NAMES, PresentationCache, build_surface,
    SAMPLING_CAUTION_FRACTION, sampling_caution as _sampling_caution)
from .gauss_teaching import CASES, teaching_state
from .output_safety import protect_saved_evidence


MINIMUM_WINDOW_SIZE = (840, 560)


def surface_mesh(state, pv, resolution):
    """Compatibility adapter: construct drawing objects from renderer-neutral SI geometry."""
    geometry = build_surface(state, resolution=resolution)
    mesh = pv.PolyData(geometry.points_m.copy(), geometry.cells.copy())
    return mesh, geometry.probes_m, geometry.outward_normals


class GaussLesson:
    """Real PyVista controller; moves select independent static configurations."""
    def __init__(self, state, *, off_screen=False, resolution=12):
        if not isinstance(state, GaussState):
            raise ValueError('requires a validated GaussState')
        if type(resolution) is not int or not 4 <= resolution <= 40:
            raise ValueError('display resolution must be an integer in [4,40]')
        import pyvista as pv
        self.pv, self.state, self.initial = pv, state, state
        self.origin = np.asarray(state.surface.center_m)
        self.unit = state.scale_m
        self.resolution, self.order = resolution, 24
        self._presentation_cache = PresentationCache()
        self.presentation = None
        self.selected_face = None
        self.teaching_case = None
        self.active, self.move_surface = 0, False
        self.cutaway, self.show_values = False, True
        self.yaw, self.tilt = 0., 0.
        self.base_rotation = np.asarray(state.surface.rotation if isinstance(state.surface, GaussianCube) else np.eye(3))
        self.plot = pv.Plotter(shape=(1,2), col_weights=(.62,.38), border=False,
                               window_size=(1440,960), off_screen=off_screen)
        self.plot.subplot(0,0); self.plot.set_background('white', all_renderers=False)
        self.plot.subplot(0,1); self.plot.set_background('#f2f5f8', all_renderers=False)
        self._building = True
        self.sliders = []
        self._annotation_actors = {}
        self._layout_pixels = None
        self._scalar_bar = None
        specs = [(lambda v: self.set_coordinate(0,v),(-3,3),0,'x / initial scale'),
                 (lambda v: self.set_coordinate(1,v),(-3,3),0,'y / initial scale'),
                 (lambda v: self.set_coordinate(2,v),(-3,3),0,'z / initial scale'),
                 (self.set_size,(.5,2),1,'Size / initial size'),
                 (self.set_yaw,(-180,180),0,'Cube yaw [deg]'),
                 (self.set_tilt,(-90,90),0,'Cube tilt [deg]')]
        self.slider_titles=[spec[3] for spec in specs]
        for i,(callback,limits,value,title) in enumerate(specs):
            self.sliders.append(self.plot.add_slider_widget(callback,limits,value=value,title=title,
                pointa=(.12,.47-i*.08),pointb=(.88,.47-i*.08),title_height=.024,
                fmt='%.3f',interaction_event='end',color='#17394d',
                slider_width=.018,tube_width=.004))
        for widget in self.sliders:
            widget.GetRepresentation().ShowSliderLabelOff()
            widget.GetRepresentation().SetSliderLength(.025)
        for key, callback in {'s':self.toggle_shape,'n':self.reverse_charge,'d':self.toggle_pair,
                'a':self.next_charge,'m':self.toggle_move_surface,'v':self.toggle_values,
                'c':self.toggle_cutaway,'r':self.refine,'0':self.reset,
                'f':self.next_face}.items():
            self.plot.add_key_event(key,callback)
        # Bind the actual keys, not a separate test-only dispatcher.
        for key, case in zip(('1', '2', '3', '4'), CASES):
            self.plot.add_key_event(key, lambda name=case.key: self.select_case(name))
        self._building = False
        self.redraw(reset_camera=True)
        # VTK StartEvent covers native window resizes as well as offscreen renders.
        # This callback changes annotation sizes only; it never recomputes physics.
        self._resize_observer = self.plot.ren_win.AddObserver('StartEvent', self._update_annotation_layout)

    def _apply(self, proposed):
        old, old_case = self.state, self.teaching_case
        self.state = proposed
        self.teaching_case = None  # An edit is no longer the exact preset.
        try:
            self.redraw()
        except Exception:
            self.state, self.teaching_case = old, old_case
            self.redraw()
            raise

    def set_coordinate(self, axis, value):
        if self._building: return
        if type(axis) is not int or axis not in (0,1,2): raise ValueError('invalid coordinate axis')
        value = _finite_scalar(value,'coordinate')
        if abs(value) > 1e6: raise ValueError('display coordinate limit exceeded')
        target = self.state.surface.center_m if self.move_surface else self.state.charges[self.active].position_m
        pos = list(target); pos[axis] = float(self.origin[axis] + self.unit*value)
        if self.move_surface:
            proposed = replace(self.state,surface=replace(self.state.surface,center_m=tuple(pos)))
        else:
            charges = list(self.state.charges)
            charges[self.active] = replace(charges[self.active],position_m=tuple(pos))
            proposed = replace(self.state,charges=tuple(charges))
        self._apply(proposed)

    def set_size(self,value):
        if self._building: return
        value = _finite_scalar(value,'size factor')
        if not .5 <= value <= 2: raise ValueError('size factor must be in [.5,2]')
        s=self.state.surface
        s=replace(s,side_m=2*self.unit*value) if isinstance(s,GaussianCube) else replace(s,radius_m=self.unit*value)
        self._apply(replace(self.state,surface=s))

    def _orient(self,yaw,tilt):
        y,t=math.radians(yaw),math.radians(tilt)
        rz=np.array([[math.cos(y),-math.sin(y),0],[math.sin(y),math.cos(y),0],[0,0,1]])
        ry=np.array([[math.cos(t),0,math.sin(t)],[0,1,0],[-math.sin(t),0,math.cos(t)]])
        return rz @ ry @ self.base_rotation

    def _set_angle(self,name,value,limit):
        if self._building: return
        value=_finite_scalar(value,name)
        if abs(value)>limit: raise ValueError(f'{name} outside display range')
        old=getattr(self,name);setattr(self,name,value)
        try:
            s=self.state.surface
            if isinstance(s,GaussianCube):
                self._apply(replace(self.state,surface=replace(s,rotation=self._orient(self.yaw,self.tilt))))
            else:self.redraw()
        except Exception:
            setattr(self,name,old);self._sync_widgets();raise

    def set_yaw(self,value): self._set_angle('yaw',value,180)
    def set_tilt(self,value): self._set_angle('tilt',value,90)

    def toggle_shape(self):
        s=self.state.surface
        new=(GaussianSphere(s.center_m,s.side_m/2) if isinstance(s,GaussianCube)
             else GaussianCube(s.center_m,2*s.radius_m,self._orient(self.yaw,self.tilt)))
        self._apply(replace(self.state,surface=new))

    def reverse_charge(self):
        charges=list(self.state.charges)
        charges[self.active]=replace(charges[self.active],charge_C=-charges[self.active].charge_C)
        self._apply(replace(self.state,charges=tuple(charges)))

    def toggle_pair(self):
        # An explicit preset action, not a hidden physical charge redistribution.
        c=self.state.charges[0]
        if len(self.state.charges)==1:
            p=np.asarray(self.state.surface.center_m)+np.array([-.55,.2,0])*self.state.scale_m
            charges=(c,HeldCharge(-c.charge_C,tuple(p)))
        else: charges=(c,)
        self.active=0
        self._apply(replace(self.state,charges=charges))

    def next_charge(self): self.active=(self.active+1)%len(self.state.charges);self.redraw()
    def toggle_move_surface(self): self.move_surface=not self.move_surface;self.redraw()
    def toggle_values(self): self.show_values=not self.show_values;self.redraw()
    def toggle_cutaway(self): self.cutaway=not self.cutaway;self.redraw()
    def refine(self): self.order={24:48,48:96,96:192,192:24}[self.order];self.redraw()

    def select_face(self, name):
        if name is not None and name not in FACE_NAMES:
            raise ValueError('unknown cube-local face')
        if name is not None and not isinstance(self.state.surface, GaussianCube):
            raise ValueError('face selection requires a cube')
        self.selected_face = name
        self.redraw()

    def next_face(self):
        if not isinstance(self.state.surface, GaussianCube):
            return
        choices = (None,) + FACE_NAMES
        self.select_face(choices[(choices.index(self.selected_face) + 1) % len(choices)])

    def select_case(self, name):
        proposed = teaching_state(self.initial, name)
        # Prepare before changing controller state, including active index.
        self._presentation_cache.get(proposed, resolution=self.resolution, order=self.order)
        self.state = proposed
        self.active = 0
        self.move_surface = False
        self.yaw = self.tilt = 0.
        self.selected_face = None
        self.teaching_case = name
        self.show_values = False  # Predict first; V reveals computed values.
        self.redraw(reset_camera=True)

    def reset(self):
        self.active=0;self.move_surface=False;self.yaw=self.tilt=0.
        self.selected_face=None;self.teaching_case=None
        self.state=self.initial;self.redraw(reset_camera=True)

    def _sync_widgets(self):
        target=self.state.surface.center_m if self.move_surface else self.state.charges[self.active].position_m
        values=list((np.asarray(target)-self.origin)/self.unit)+[self.state.scale_m/self.unit,self.yaw,self.tilt]
        for i,(widget,value) in enumerate(zip(self.sliders,values)):
            rep=widget.GetRepresentation()
            if i<3:
                span=max(3.,abs(float(value))*1.2)
                rep.SetMinimumValue(-span);rep.SetMaximumValue(span)
            rep.SetValue(float(value))
            rep.SetTitleText(f'{self.slider_titles[i]}: {value:.8g}')

    def _add_annotation(self, name, text, position, *, role='body', color='#17394d'):
        actor = self.plot.add_text(text, name=name, position=position, viewport=True,
                                   font_size=8, color=color, render=False)
        actor.GetTextProperty().SetVerticalJustificationToTop()
        self._annotation_actors[name] = (actor, role)
        return actor

    def _update_annotation_layout(self, *_):
        """Resize only text; no camera, physical state, flux or mesh changes."""
        size = tuple(self.plot.window_size)
        if size == self._layout_pixels:
            return
        factor = min(size[0] / 1440., size[1] / 960.)
        sizes = {'title': max(18, round(28 * factor)),
                 'body': max(12, round(18 * factor)),
                 'help': max(11, round(16 * factor))}
        for actor, role in self._annotation_actors.values():
            actor.GetTextProperty().SetFontSize(sizes[role])
        if self._scalar_bar is not None:
            self._scalar_bar.GetTitleTextProperty().SetFontSize(sizes['body'])
            self._scalar_bar.GetLabelTextProperty().SetFontSize(sizes['help'])
        self._layout_pixels = size
        self.annotation_font_pixels = sizes

    def redraw(self, *, reset_camera=False):
        # Complete data preparation before clearing actors; drawing never evaluates E/flux.
        data = self._presentation_cache.get(self.state, resolution=self.resolution, order=self.order)
        self.presentation = data
        geometry = data.surface
        p,pv=self.plot,self.pv
        self._annotation_actors = {}
        self._layout_pixels = None
        self._scalar_bar = None
        p.subplot(0,0)
        camera=None if reset_camera else p.camera_position
        p.renderer.clear();p.scalar_bars.clear()
        self.report = dict(data.report)
        self.full_mesh = pv.PolyData(geometry.points_m.copy(), geometry.cells.copy())
        self.probes, self.normals = geometry.probes_m, geometry.outward_normals
        self.fields, self.normal_field, self.clim = data.field_N_C, data.normal_field_N_C, data.color_limits_N_C
        if self.normal_field is not None:
            self.full_mesh.cell_data['E dot n [N/C]'] = self.normal_field.copy()
        display=self.full_mesh.copy()
        display.points=(display.points-self.origin)/self.unit
        center=(np.asarray(self.state.surface.center_m)-self.origin)/self.unit
        self.visible_mesh=display.clip(normal=(1,1,1),origin=center) if self.cutaway else display
        if self.normal_field is not None:
            p.add_mesh(self.visible_mesh,scalars='E dot n [N/C]',clim=self.clim,cmap='coolwarm',
                opacity=.48,show_edges=False,scalar_bar_args={'title':'Local E dot n [N/C]',
                'color':'#17394d','position_y':.20,'position_x':.15,'width':.70,'height':.05,
                'title_font_size':18,'label_font_size':16,'unconstrained_font_size':True})
            self._scalar_bar = p.scalar_bars['Local E dot n [N/C]']
        else:p.add_mesh(self.visible_mesh,color='lightgray',opacity=.4)
        # A world-axis bounding box is NOT the Gaussian surface. Draw only
        # the real rotated cube edges; a sphere has no auxiliary cube around it.
        self.outline_mesh = None
        if isinstance(self.state.surface, GaussianCube):
            self.outline_mesh = pv.PolyData((geometry.outline_points_m-self.origin)/self.unit,
                lines=np.c_[np.full(12,2),geometry.outline_edges].ravel())
            p.add_mesh(self.outline_mesh,color='#647383',line_width=1)
        else:
            self.selected_face = None
        self.selected_face_mesh = None
        self.selected_face_flux = None
        if self.selected_face is not None:
            face = FACE_NAMES.index(self.selected_face)
            cells = geometry.cells[geometry.face_indices == face]
            self.selected_face_mesh = pv.PolyData((geometry.points_m-self.origin)/self.unit, cells.copy()).clean()
            # Only a boundary outline: do not replace E dot n colors or the closed surface.
            # Cube quads have duplicate vertices; clean before extracting the perimeter.
            edge = self.selected_face_mesh.clean().extract_feature_edges(boundary_edges=True,
                feature_edges=False, manifold_edges=False, non_manifold_edges=False)
            p.add_mesh(edge, color='#b16b00', line_width=4)
            if self.report['status'] == 'available' and self.show_values:
                self.selected_face_flux = self.report['face_flux_N_m2_per_C'][face]
        self.arrow_meshes=[]
        if self.fields is not None:
            indices=np.linspace(0,len(self.probes)-1,12,dtype=int)
            for kind,color,vectors in [('normal','#333333',self.normals),('field','#1b8759',self.fields)]:
                for index in indices:
                    v=vectors[index];length=float(np.linalg.norm(v))
                    if not length:continue
                    arrow=pv.Arrow(start=(self.probes[index]-self.origin)/self.unit,
                        direction=v/length,scale=.18*self.state.scale_m/self.unit)
                    self.arrow_meshes.append((kind,index,arrow))
                    p.add_mesh(arrow,color=color)
        for i,c in enumerate(self.state.charges):
            pos=(np.asarray(c.position_m)-self.origin)/self.unit
            p.add_mesh(pv.Sphere(radius=.045*self.state.scale_m/self.unit,center=pos),
                color='#dd4433' if c.charge_C>0 else '#3165bf' if c.charge_C<0 else 'gray')
            p.add_point_labels(np.asarray([pos]),[f'q{i+1}: {c.charge_C*1e9:+g} nC'],
                font_size=13,point_size=0,always_visible=True)
        shape='CUBE' if isinstance(self.state.surface,GaussianCube) else 'SPHERE'
        self._add_annotation('title', f'GAUSS LAW - {shape}\nImaginary closed surface; not a conductor',
                             (.02,.98), role='title')
        self._add_annotation('instructions',
                   'Black arrows: outward n. Green: E direction (fixed lengths).\n'
                   'Colors: local E dot n, NOT integrated face flux.\n'
                   'Cutaway is visual only; the mathematical surface is CLOSED.\n'
                   'S: shape; N: sign; D: pair; A: charge; M: surface\n'
                   'C: cutaway; V: reveal; R: refine; F: face; 1-4: cases; 0: reset',
                   (.02,.15), role='help')
        case = next((case for case in CASES if case.key == self.teaching_case), None)
        teaching = '1-4: synthetic teaching cases (replace charges)'
        if case is not None:
            teaching = case.title + ' [synthetic]\n' + case.question_for(self.state.surface)
        if self.selected_face is not None:
            value = ('hidden; V reveals' if not self.show_values else
                     'undefined at boundary' if self.selected_face_flux is None else
                     f'{self.selected_face_flux:+.7g} N m^2/C')
            teaching += f'\nSelected {self.selected_face} (cube-local): {value}'
        self._add_annotation('teaching', teaching, (.02,.86), role='help')
        p.add_axes(xlabel='x',ylabel='y',zlabel='z',viewport=(.01,.30,.17,.46))
        if camera is None:
            p.camera_position=[tuple(center+np.array([4.8,-7.2,4.2])),tuple(center),(0,0,1)]
        else:p.camera_position=camera
        p.subplot(0,1)
        r=self.report
        lines=['CLOSED-SURFACE FLUX',f'Shape: {shape}; size scale = {self.state.scale_m:g} m',
               'Center [m]: (' + ', '.join(f'{v:.4g}' for v in self.state.surface.center_m) + ')',
               f'Controls move: {"surface" if self.move_surface else "charge q"+str(self.active+1)}',
               'Moves select static configurations.','']
        if r['status']!='available':
            lines+=['UNDEFINED: charge on / unresolved','against the surface. No half-charge rule.']
        elif not self.show_values:
            lines+=['PREDICT: what charge is enclosed?','Press V to reveal flux.']
        else:
            lines += [f'Enclosed charge = {r["enclosed_charge_C"]*1e9:+.6g} nC',
                      f'Exact total = {r["exact_total_N_m2_per_C"]:+.8g} N m^2/C']
            if 'face_names' in r:
                lines+=['Cube-local face flux [N m^2/C]:']
                lines += [f'  {name}: {value:+.7g}' for name,value in zip(r['face_names'],r['face_flux_N_m2_per_C'])]
                lines += [f'Sum = {r["sum_faces_N_m2_per_C"]:+.8g}']
            else:
                lines += [f'Sampled total = {r["sampled_total_N_m2_per_C"]:+.8g}',
                    f'Error (sample - exact) = {r["sampling_error_N_m2_per_C"]:+.3g}',
                    f'Quadrature: {self.order} x {2*self.order}; R refines',
                    'Samples are unadjusted, not certified.']
        self._add_annotation('readout', '\n'.join(lines), (.025,.98))
        self.sampling_caution = None if data.caution is None else dict(data.caution)
        caution_visible = (self.show_values and self.sampling_caution is not None
                           and self.sampling_caution['large_discrepancy'])
        self.caution_actor = self._add_annotation('sampling-caution',
            'SAMPLING CAUTION\nLarge sample/exact mismatch.\n'
            'Use the exact Gauss-law total.\nR refines; error may persist.' if caution_visible else '',
            (.04,.62), color='#803000')
        prop = self.caution_actor.GetTextProperty()
        prop.SetBackgroundColor(1., .91, .72)
        prop.SetBackgroundOpacity(1.)
        self.caution_actor.SetVisibility(bool(caution_visible))
        self._update_annotation_layout()
        self._sync_widgets()
        p.subplot(0,0);p.render()

    def display_state(self):
        return {'active_charge':self.active,'move_surface':self.move_surface,
                'cutaway':self.cutaway,'mathematical_surface_closed':True,
                'selected_cube_local_face':self.selected_face,
                'selected_face_flux_N_m2_per_C':self.selected_face_flux,
                'teaching_case':self.teaching_case,
                'teaching_case_provenance':None if self.teaching_case is None else 'synthetic_not_exam_original',
                'presentation_build_count':self._presentation_cache.build_count,
                'values_visible':self.show_values,'quadrature_order':self.order,
                'resolution':self.resolution,'yaw_degrees':self.yaw,'tilt_degrees':self.tilt,
                'origin_m':self.origin.tolist(),'unit_m':self.unit,
                'window_size_pixels':list(self.plot.window_size),
                'minimum_supported_window_size_pixels':list(MINIMUM_WINDOW_SIZE),
                'annotation_font_pixels':dict(self.annotation_font_pixels),
                'sampling_caution':self.sampling_caution,
                'sampling_caution_visible':bool(self.caution_actor.GetVisibility()),
                'camera':[list(v) for v in self.plot.renderers[0].camera_position],
                'slider_values':[w.GetRepresentation().GetValue() for w in self.sliders],
                'slider_titles':[w.GetRepresentation().GetTitleText() for w in self.sliders],
                'E_dot_n_color_limits_N_C':self.clim,
                'glyphs':'fixed display length; directions only, not calibrated flux'}


def _json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def save_snapshot(state,output,*,lesson=None,source_bytes=None,order=24):
    protect_saved_evidence(output,new_directory=True)
    if lesson is not None:
        state=lesson.state;order=lesson.order
        physics=dict(lesson._presentation_cache.get(state, resolution=lesson.resolution, order=order).report)
    else:
        physics=measure(state,order=order)
    if source_bytes is not None and not isinstance(source_bytes,bytes):
        raise ValueError("source_bytes must be original bytes")
    authored=None if source_bytes is None else parse_lesson(source_bytes)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    _json(output/'started.json',{'execution_complete':False,'lesson':'gauss_v1'})
    sha=lambda b:hashlib.sha256(b).hexdigest()
    try:
        _json(output/'lesson.json',state.to_dict())
        if source_bytes is not None:(output/'authored-input.json').write_bytes(source_bytes)
        report={'physics':physics,'lesson_sha256':sha((output/'lesson.json').read_bytes()),
                'authored_input_sha256':None if source_bytes is None else sha(source_bytes),
                'original_input_equals_current_state':None if authored is None else authored==state,
                'constants':{'epsilon_0_F_m':epsilon_0},
                'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
                'implementation_sha256':{p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))},
                'display':None,'screenshot':None,'independent_review':'not_evaluated',
                'human_windows_acceptance':'not_evaluated','teacher_usefulness':'not_evaluated'}
        if lesson is not None:
            lesson.redraw()
            arrays={'positions_m':lesson.probes,'outward_normals':lesson.normals}
            if lesson.fields is not None:arrays.update(E_N_C=lesson.fields,E_dot_n_N_C=lesson.normal_field)
            np.savez_compressed(output/'surface_samples.npz',**arrays)
            report['display']=lesson.display_state()
            report['environment'].update(pyvista=lesson.pv.__version__,vtk=lesson.pv.vtk_version_info._asdict())
            image=lesson.plot.screenshot(str(output/'view.png'),return_img=True)
            if image is None or float(image.std())<1:raise RuntimeError('blank screenshot')
            report['screenshot']={'file':'view.png','sha256':sha((output/'view.png').read_bytes())}
        _json(output/'report.json',report)
        _json(output/'outcome.json',{'execution_complete':True,'flux_available':physics['status']=='available'})
        _json(output/'integrity.json',{'files':{p.name:sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}})
        return report
    except Exception as exc:
        _json(output/'outcome.json',{'execution_complete':False,'failure_type':type(exc).__name__,'message':str(exc)})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lesson_file',type=Path)
    parser.add_argument('--case',choices=[c.key for c in CASES],
                        help='select an explicit synthetic teaching configuration')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--snapshot',type=Path);group.add_argument('--headless',type=Path)
    group.add_argument('--validate-only',action='store_true')
    args=parser.parse_args(argv);output=args.snapshot or args.headless
    try:
        if output is not None:protect_saved_evidence(output,new_directory=True)
        raw=args.lesson_file.read_bytes();state=parse_lesson(raw)
        initial=state
        if args.case: state=teaching_state(initial,args.case)
        if args.validate_only:
            print(json.dumps({'valid':True,'flux_status':measure(state)['status']}));return 0
        if args.headless:save_snapshot(state,output,source_bytes=raw);return 0
        lesson=GaussLesson(initial,off_screen=bool(args.snapshot))
        if args.case: lesson.select_case(args.case)
        try:
            if args.snapshot:
                lesson.plot.show(auto_close=False,interactive=False)
                save_snapshot(state,output,lesson=lesson,source_bytes=raw)
            else:lesson.plot.show()
        finally:lesson.plot.close()
        return 0
    except (ValueError,OSError) as exc:
        print(f'gauss-lesson: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
