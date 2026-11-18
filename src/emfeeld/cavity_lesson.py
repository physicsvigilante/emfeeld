"""Opt-in 3D JEE conductor-cavity lesson, separate from the scene/source engine.

python -m emfeeld.cavity_lesson examples/lessons/conductor_cavity.json
Use --snapshot NEW_DIRECTORY for a retained offscreen rendering and exact state,
or --headless NEW_DIRECTORY for numerical/display samples without graphics.
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

from .conductor_cavity import (ConductorCavity, K, MAX_OFFSET, load_lesson,
                               spherical_quadrature, trace_cavity_lines, seed_directions)
from .output_safety import protect_saved_evidence


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False)+'\n',
                          encoding='utf-8')


def save_snapshot(model, output, *, lesson=None, source_bytes=None, count=32):
    """Fresh output only. Capture the CURRENT controller model, not its initial file.

    A screenshot is an illustrative display; neither teacher acceptance nor an
    independent physical correctness verdict follows from successful rendering.
    """
    protect_saved_evidence(output, new_directory=True)
    if lesson is not None:
        model = lesson.model
        count = lesson.line_count
    if not isinstance(model, ConductorCavity):
        raise ValueError('snapshot requires a validated conductor-cavity model')
    seed_directions(count)  # fail bad display settings before writes
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _json(output/'started.json', {'execution_complete': False, 'lesson': 'conductor_cavity_v1'})
    _json(output/'lesson.json', model.to_dict())
    if source_bytes is not None:
        (output/'authored-input.json').write_bytes(source_bytes)
    try:
        lines = trace_cavity_lines(model, count=count)
        arrays = {f'line_{i:03d}': row['points_m'] for i,row in enumerate(lines)}
        np.savez_compressed(output/'field_lines.npz', **arrays)
        report = {
            'lesson_version': 1, 'physics': model.summary(),
            'lesson_sha256': _sha((output/'lesson.json').read_bytes()),
            'authored_input_sha256': _sha(source_bytes) if source_bytes is not None else None,
            'original_input_equals_current_state': None,
            'constants': {'coulomb_constant_N_m2_C2': K},
            'python': platform.python_version(), 'numpy': np.__version__,
            'implementation_sha256': {p.name: _sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))},
            'surface_quadrature': [spherical_quadrature(model, n) for n in (32,64)],
            'field_lines': {'count': len(lines), 'requested_seed_count': count,
                            'termination': [r['termination'] for r in lines],
                            'sampling_not_flux': True, 'particle_dynamics': False,
                            'source_and_wall_gaps_are_display_only': True},
            'display': lesson.display_state() if lesson is not None else None,
            'screenshot': None, 'human_visual_acceptance': 'not_evaluated',
            'independent_physics_review': 'not_evaluated', 'teacher_usefulness': 'not_evaluated',
        }
        if source_bytes is not None:
            report['original_input_equals_current_state'] = json.loads(source_bytes)==model.to_dict()
        if lesson is not None:
            lesson.plot.render()
            image=lesson.plot.screenshot(str(output/'view.png'), return_img=True)
            if image is None or image.std() < 1:
                raise RuntimeError('blank or missing lesson screenshot')
            report['screenshot']={'file':'view.png','sha256':_sha((output/'view.png').read_bytes())}
        _json(output/'report.json',report)
        _json(output/'outcome.json',{'execution_complete':True,
            'display_tracing_complete':all(r['termination']=='inner_surface_approached' for r in lines)})
        _json(output/'integrity.json', {'files': {p.relative_to(output).as_posix():_sha(p.read_bytes())
            for p in sorted(output.rglob('*')) if p.is_file()}})
        return report
    except Exception as exc:
        _json(output/'outcome.json', {'execution_complete': False,
               'failure_type': type(exc).__name__, 'message': str(exc)})
        raise


class CavityLesson:
    """Real PyVista scene plus independent, transactional equilibrium controls."""

    def __init__(self, model, *, off_screen=False, line_count=32, resolution=48):
        if not isinstance(model, ConductorCavity):
            raise ValueError('lesson requires a validated model')
        seed_directions(line_count)
        if type(resolution) is not int or not 16 <= resolution <= 128:
            raise ValueError('surface resolution must be an integer in [16,128]')
        import pyvista as pv  # optional, never imported for headless physics
        self.pv=pv
        self.model=model
        self.line_count=line_count
        self.resolution=resolution
        self.cutaway=True
        self.show_lines=True
        self.isolated_Q=model.conductor_charge_C
        a=np.asarray(model.charge_position_m)/model.inner_radius_m
        self.offset=float(np.hypot.reduce(a))
        self.theta=math.degrees(math.acos(float(a[2]/self.offset))) if self.offset else 90.0
        self.phi=math.degrees(math.atan2(float(a[1]),float(a[0]))) if self.offset else 0.0
        self.plot=pv.Plotter(shape=(1,2), col_weights=(0.72,0.28),
                            border=False, window_size=(1400,900),off_screen=off_screen)
        self.plot.subplot(0,0);self.plot.set_background('white',all_renderers=False)
        self.plot.subplot(0,1);self.plot.set_background('#f1f5f8',all_renderers=False)
        self._building=True
        self.sliders=[]
        specs=[(self.set_offset,(0,MAX_OFFSET),self.offset,'Charge offset a/R',.27),
               (self.set_theta,(0,180),self.theta,'Direction: polar angle [deg]',.19),
               (self.set_phi,(-180,180),self.phi,'Direction: azimuth [deg]',.11),
               (self.set_Q_nC,(-self._Q_range(),self._Q_range()),self.isolated_Q*1e9,
                'Isolated Q [nC] (inactive if grounded)',.03)]
        for callback,rng,value,title,y in specs:
            self.sliders.append(self.plot.add_slider_widget(callback,rng,value=value,title=title,
                pointa=(.76,y),pointb=(.96,y),title_height=.017,fmt='%.2f',
                interaction_event='end',color='#17394d',slider_width=.025,tube_width=.005))
        self.plot.add_key_event('g',self.toggle_grounded)
        self.plot.add_key_event('c',self.toggle_cutaway)
        self.plot.add_key_event('n',self.reverse_charge)
        self.plot.add_key_event('l',self.toggle_lines)
        self._building=False
        self.redraw(reset_camera=True)

    def _Q_range(self):
        return min(1e6,max(2.0,abs(self.model.charge_C)*2e9,abs(self.isolated_Q)*1e9))

    def _position(self,offset=None,theta=None,phi=None):
        t=math.radians(self.theta if theta is None else theta)
        p=math.radians(self.phi if phi is None else phi)
        f=self.offset if offset is None else offset
        v=f*np.array([math.sin(t)*math.cos(p),math.sin(t)*math.sin(p),math.cos(t)])
        # The admission boundary is inclusive. Avoid an extra rounding ULP above it.
        if f <= MAX_OFFSET and np.hypot.reduce(v)>MAX_OFFSET:
            v *= np.nextafter(MAX_OFFSET,0.0)/float(np.hypot.reduce(v))
        return tuple(float(x*self.model.inner_radius_m) for x in v)

    def _update(self, **changes):
        proposed=replace(self.model,**changes)  # validate before replacing live state
        self.model=proposed
        if not self._building:self.redraw()

    def set_offset(self,value):
        # PyVista invokes callbacks once while installing each widget.
        # Opening the viewer must preserve the exact authored equilibrium.
        if self._building:
            return
        value=float(value)
        if not math.isfinite(value) or not 0<=value<=MAX_OFFSET:raise ValueError('offset outside V1 display range')
        self._update(charge_position_m=self._position(offset=value));self.offset=value
        self.sliders[0].GetRepresentation().SetValue(value)

    def set_theta(self,value):
        # PyVista invokes callbacks once while installing each widget.
        # Opening the viewer must preserve the exact authored equilibrium.
        if self._building:
            return
        value=float(value)
        if not math.isfinite(value) or not 0<=value<=180:raise ValueError('polar angle outside [0,180]')
        self._update(charge_position_m=self._position(theta=value));self.theta=value
        self.sliders[1].GetRepresentation().SetValue(value)

    def set_phi(self,value):
        # PyVista invokes callbacks once while installing each widget.
        # Opening the viewer must preserve the exact authored equilibrium.
        if self._building:
            return
        value=float(value)
        if not math.isfinite(value) or not -180<=value<=180:raise ValueError('azimuth outside [-180,180]')
        self._update(charge_position_m=self._position(phi=value));self.phi=value
        self.sliders[2].GetRepresentation().SetValue(value)

    def set_Q_nC(self,value):
        # PyVista invokes callbacks once while installing each widget.
        # Opening the viewer must preserve the exact authored equilibrium.
        if self._building:
            return
        q=float(value)*1e-9
        # Validate even while grounded; this is the stored isolated-mode setting.
        replace(self.model,mode='isolated',conductor_charge_C=q)
        self.isolated_Q=q
        if self.model.mode=='isolated':self._update(conductor_charge_C=q)
        rep=self.sliders[3].GetRepresentation()
        limit=self._Q_range()
        rep.SetMinimumValue(-limit);rep.SetMaximumValue(limit)
        rep.SetValue(q*1e9)

    def toggle_grounded(self):
        if self.model.mode=='isolated':self._update(mode='grounded',conductor_charge_C=0.0)
        else:self._update(mode='isolated',conductor_charge_C=self.isolated_Q)

    def toggle_cutaway(self):
        self.cutaway=not self.cutaway;self.redraw()

    def reverse_charge(self):
        self._update(charge_C=-self.model.charge_C)

    def toggle_lines(self):
        self.show_lines=not self.show_lines;self.redraw()

    def display_state(self):
        return {'cutaway':self.cutaway,'cutaway_is_not_physical_hole':True,
                'field_lines_visible':self.show_lines,'surface_resolution':self.resolution,
                'line_count':self.line_count,'isolated_Q_setting_C':self.isolated_Q,
                'slider_values': [w.GetRepresentation().GetValue() for w in self.sliders],
                'slider_order': ['offset_a_over_R','polar_deg','azimuth_deg','isolated_Q_nC'],
                'coordinates':'x/R,y/R,z/R',
                'camera': [list(row) for row in self.plot.renderers[0].camera_position],
                'surface_color':'actual nC/m^2; symmetric automatic color range, read the legend',
                'actual_point_charge_marker':'schematic size; image charges are not drawn',
                'controls_change_static_equilibria_not_time':True}

    def _surface(self,radius):
        mesh=self.pv.Sphere(radius=radius,theta_resolution=2*self.resolution,
                             phi_resolution=self.resolution)
        if self.cutaway:mesh=mesh.clip(normal=(0,1,0),origin=(0,0,0),invert=False)
        p=np.asarray(mesh.points,dtype=float)
        p=radius*p/np.linalg.norm(p,axis=1)[:,None]
        mesh.points=p
        return mesh

    def redraw(self, *, reset_camera=False):
        p=self.plot;m=self.model;pv=self.pv
        p.subplot(0,0)
        camera=p.camera_position if not reset_camera else None
        # Clear only the 3D renderer. Plotter.clear() also removes the right
        # panel's slider representations, even when callback objects still exist.
        p.renderer.clear()
        p.scalar_bars.clear()
        R=m.inner_radius_m;b=m.outer_radius_m/R
        inner=self._surface(1);outer=self._surface(b)
        name='Surface charge [nC/m^2]'
        inner[name]=m.inner_density(inner.points)*1e9
        outer[name]=np.full(outer.n_points,m.outer_density_C_m2*1e9)
        self.inner_mesh=inner;self.outer_mesh=outer
        peak=max(float(np.max(np.abs(inner[name]))),abs(m.outer_density_C_m2)*1e9,1e-12)
        kwargs=dict(scalars=name,clim=(-peak,peak),cmap='coolwarm',smooth_shading=False,
                    scalar_bar_args={'title':name,'vertical':False,'position_x':.10,
                         'position_y':.04,'width':.80,'height':.07,'color':'#17394d',
                         'title_font_size':15,'label_font_size':12})
        p.add_mesh(inner,name='inner_surface',opacity=.96,**kwargs)
        p.add_mesh(outer,name='outer_surface',opacity=.32,show_scalar_bar=False,**kwargs)
        if self.cutaway:
            rim=pv.Disc(center=(0,0,0),inner=1,outer=b,normal=(0,1,0),c_res=2*self.resolution)
            p.add_mesh(rim,name='metal_cut_face',color='#a7b6c2',opacity=.9)
        a=np.asarray(m.charge_position_m)/R
        if m.charge_C:
            marker=pv.Sphere(radius=min(.035,(1-np.linalg.norm(a))*.2),center=a)
            p.add_mesh(marker,color='#e74b3c' if m.charge_C>0 else '#2854c5',name='real_charge')
            p.add_point_labels(np.array([a]),['q (real)'],font_size=16,point_size=0,
                               always_visible=True,shape_opacity=.7)
        self.lines=trace_cavity_lines(m,count=self.line_count) if self.show_lines else []
        self.exterior_paths=[]
        for i,line in enumerate(self.lines):
            pts=line['points_m']/R
            poly=pv.lines_from_points(pts)
            p.add_mesh(poly,color='#d99b17',line_width=2,name=f'cavity_line_{i}')
            j=len(pts)//2
            direction=pts[min(j+1,len(pts)-1)]-pts[max(0,j-1)]
            arrow=pv.Arrow(start=pts[j],direction=direction,scale=.12,tip_radius=.18)
            p.add_mesh(arrow,color='#b67b08',name=f'cavity_arrow_{i}')
        if self.show_lines and m.outer_charge_C:
            for i,n in enumerate(seed_directions(16)):
                pts=np.array([n*b*1.01,n*b*1.85])
                if m.outer_charge_C<0:pts=pts[::-1].copy()
                self.exterior_paths.append(pts.copy())
                p.add_mesh(pv.lines_from_points(pts),color='#6d7682',line_width=1.5,name=f'outer_line_{i}')
                p.add_mesh(pv.Arrow(start=pts.mean(axis=0),direction=pts[1]-pts[0],scale=.12,tip_radius=.18),
                           color='#6d7682',name=f'outer_arrow_{i}')
        p.add_text('JEE CONDUCTOR CAVITY\nAnalytic electrostatics, sampled 3D display',
                   name='title',font_size=14,color='#17394d')
        p.add_text('Cutaway is only a view: the conductor is still CLOSED.\n'
                   'Curves show E direction, not particle motion or calibrated flux.',
                   position='lower_left',font_size=10,color='#17394d',name='caution')
        p.add_axes(xlabel='x/R',ylabel='y/R',zlabel='z/R')
        if reset_camera:
            p.camera_position=[(3.6*b,-5*b,2.8*b),(0,0,0),(0,0,1)]
        else:p.camera_position=camera
        p.subplot(0,1)
        s=m.summary();quad=spherical_quadrature(m,64)
        actual_offset=float(np.linalg.norm(np.asarray(m.charge_position_m)/R))
        text=(f'IDEAL SPHERICAL CONDUCTOR\n\n'
              f'Mode: {m.mode.upper()}\n'
              f'R = {R:g} m; B = {m.outer_radius_m:g} m\n'
              f'q = {m.charge_C*1e9:+.4g} nC\n'
              f'Offset a/R = {actual_offset:.3f}\n\n'
              f'Inner surface: {s["inner_total_C"]*1e9:+.4g} nC\n'
              f'Outer surface: {s["outer_total_C"]*1e9:+.4g} nC\n'
              f'Net conductor: {s["conductor_total_C"]*1e9:+.4g} nC\n'
              f'Metal: E = 0 N/C\n'
              f'Metal: V = {s["conductor_potential_V"]:.5g} V\n\n'
              f'GAUSS LAW IN THE METAL\n'
              f'q + Q_inner = 0\n'
              f'Isolated: Q_outer = Q + q\n'
              f'Grounded: V = 0; Q_outer = 0\n\n'
              f'Cavity field is NOT generally zero.\n'
              f'No external charges. q is held fixed.\n'
              f'Each adjustment is a new equilibrium.\n\n'
              f'Sampled inner integral: {quad["total_C"]*1e9:+.6g} nC\n'
              f'Unrescaled error: {quad["error_C"]*1e9:.2g} nC\n\n'
              f'G  Ground / isolate\nN  Reverse q\n'
              f'C  Cutaway / full shell\nL  Hide / show E lines\n'
              f'Drag left view to rotate; wheel to zoom.\n'
              f'No physical image charge is drawn.')
        p.add_text(text,position='upper_left',font_size=10,color='#17394d',name='lesson_text')
        p.subplot(0,0)
        p.render()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lesson_file',type=Path)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--snapshot',type=Path,help='new offscreen screenshot/evidence directory')
    group.add_argument('--headless',type=Path,help='new numerical sample/evidence directory, no graphics')
    group.add_argument('--validate-only',action='store_true')
    parser.add_argument('--lines',type=int,default=32)
    args=parser.parse_args(argv)
    output=args.snapshot or args.headless
    # Refuse evidence pollution before renderer creation or a long calculation.
    try:
        if output is not None:protect_saved_evidence(output,new_directory=True)
        model=load_lesson(args.lesson_file)
        raw=args.lesson_file.read_bytes()
        seed_directions(args.lines)
        if args.validate_only:
            print(json.dumps({'valid':True,'meaning':'bounded lesson schema, not independent scientific review'}))
            return 0
        if args.headless:
            save_snapshot(model,output,source_bytes=raw,count=args.lines)
            return 0
        lesson=CavityLesson(model,off_screen=bool(args.snapshot),line_count=args.lines)
        try:
            if args.snapshot:
                lesson.plot.show(auto_close=False,interactive=False)
                save_snapshot(model,output,lesson=lesson,source_bytes=raw)
            else:lesson.plot.show()
        finally:lesson.plot.close()
        return 0
    except (ValueError,OSError) as exc:
        print(f'conductor-cavity: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
