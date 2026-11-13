"""Real off-screen PyVista qualification; not Windows or mouse-interaction evidence.

Run from an installed source checkout:
    python tools/qualify_viewer.py --output output/viewer-qualification
No mock plotter, field modifications, or display-dependent forces are used.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import traceback

import numpy as np
import pyvista as pv
from vtkmodules.vtkCommonCore import vtkCommand

from emfeeld import (InfiniteLine, InfinitePlane, Scene, SolidSphere,
                     SphericalShell, Superposition, UniformField, load_scene)
from emfeeld.viewer import make_plotter, sample_values

ROOT = Path(__file__).resolve().parents[1]


def meshes(plot):
    """Inspect real mapper datasets, not a test double."""
    return [actor.mapper.dataset for actor in plot.renderer.actors.values()
            if isinstance(actor, pv.Actor) and hasattr(actor.mapper, 'dataset')]


def signature(mesh):
    return {
        'type': type(mesh).__name__, 'points': mesh.n_points, 'cells': mesh.n_cells,
        'bounds': list(mesh.bounds),
        'coordinates_sha256': hashlib.sha256(mesh.points.tobytes()).hexdigest(),
    }


def cases():
    result = [(p.stem, load_scene(p)) for p in sorted((ROOT / 'examples').glob('*.json'))]
    sources = (
        SolidSphere('electric', 1e-9, center=(-1, 0, 0), radius=0.4),
        SolidSphere('electric', -1e-9, center=(1, 0, 0), radius=0.4),
        SphericalShell('electric', 1e-10, center=(0, 1, 0), radius=0.3),
        UniformField('electric', (0, 0, 0.25)),
    )
    flat = Scene('Grouping equivalence: repeated sphere retained',
                 Superposition((*sources, sources[0])), (), 1.0, 2, (-3, 3, -3, 3, -3, 3))
    nested = replace(flat, model=Superposition((Superposition(sources[:2]),
                     Superposition((Superposition(sources[2:]), sources[0])))))
    tilted = Scene('Oblique prescribed line and plane; undefined samples omitted',
                   Superposition((InfiniteLine('electric', 1e-10, direction=(1, 1, 1)),
                                  InfinitePlane('electric', -1e-11, normal=(1, 3, 7)))),
                   (), 1.0, 2, (-3, 3, -3, 3, -3, 3))
    result.extend([('composition_flat', flat), ('composition_nested', nested),
                   ('tilted_line_plane', tilted)])
    return result


def capture(name, scene, output):
    expected = scene.trajectories()
    plot = make_plotter(scene, off_screen=True)
    try:
        datasets = meshes(plot)
        unit = 'V' if scene.model.kind == 'electric' else 'J/kg'
        if set(plot.scalar_bars) != {f'Potential [{unit}]'}:
            raise AssertionError(f'Unintended scalar legends: {list(plot.scalar_bars)}')
        result = {'status': 'PASS', 'geometry': [signature(m) for m in datasets], 'frames': []}
        markers = []
        for trajectory in expected:
            candidates = [m for m in datasets if m.n_points == 1 and
                          np.array_equal(m.points, trajectory.position_m[:1])]
            if len(candidates) != 1:
                raise AssertionError(f'Expected one real marker dataset, found {len(candidates)}')
            markers.append(candidates[0])
        if expected and len(plot.widgets.slider_widgets) != 1:
            raise AssertionError('Moving scene needs one real VTK slider')
        plot.show(auto_close=False, interactive=False)
        result['render_window'] = plot.render_window.GetClassName()
        result['render_capabilities'] = plot.render_window.ReportCapabilities()
        for fraction in ((0.0, 0.5, 1.0) if expected else (0.0,)):
            sample = int(round(fraction * (scene.samples - 1)))
            if expected:
                widget = plot.widgets.slider_widgets[0]
                widget.GetRepresentation().SetValue(fraction * scene.duration_s)
                # PyVista's default interaction_event='end'. This is a real VTK
                # event, but it does NOT simulate or qualify a desktop mouse drag.
                widget.InvokeEvent(vtkCommand.EndInteractionEvent)
                for marker, trajectory in zip(markers, expected):
                    np.testing.assert_array_equal(marker.points,
                                                   trajectory.position_m[sample:sample + 1])
            plot.render()
            filename = f'{name}_{int(fraction * 100):03d}.png'
            image = plot.screenshot(str(output / filename), return_img=True)
            if image.shape[:2] != (850, 1200) or image.std() <= 1:
                raise AssertionError('Screenshot has unexpected dimensions or is blank')
            result['frames'].append({
                'file': filename, 'sample': sample,
                'time_s': sample * scene.duration_s / (scene.samples - 1),
                'marker_positions_m': [m.points[0].tolist() for m in markers],
                'png_sha256': hashlib.sha256((output / filename).read_bytes()).hexdigest(),
            })
        if name == 'tilted_line_plane':
            points = np.array([[1., 1., 1.], [7., 0., -1.], [1., -1., 0.]])
            field, potential = sample_values(scene.model, points), sample_values(scene.model, points, potential=True)
            assert np.isnan(field[:2]).all() and np.isfinite(field[2]).all()
            assert np.isnan(potential[0]) and np.isfinite(potential[1:]).all()
            result['undefined_sample_checks'] = 'PASS: holes, not zero or finite artifacts'
        return result
    finally:
        plot.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'viewer-qualification')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report = {
        'commit': commit, 'platform': platform.platform(), 'python': platform.python_version(),
        'versions': {name: importlib.metadata.version(name)
                     for name in ('numpy', 'scipy', 'pyvista', 'vtk', 'pytest')},
        'scope': 'Real off-screen rendering and programmatic VTK slider events. '
                 'No independent review, mouse interaction or Windows qualification.',
        'visual_inspection': 'PENDING: screenshots require separate inspection',
        'status': 'RUNNING', 'cases': {},
    }
    report_path = args.output / 'report.json'
    def save_progress():
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    save_progress()
    for name, scene in cases():
        report['cases'][name] = {'status': 'RUNNING'}
        save_progress()  # Preserve the last case even if native graphics aborts.
        try:
            report['cases'][name] = capture(name, scene, args.output)
        except Exception:
            report['cases'][name] = {'status': 'FAIL', 'traceback': traceback.format_exc()}
        save_progress()
        print(name, report['cases'][name]['status'], flush=True)
    flat, nested = (report['cases'][n] for n in ('composition_flat', 'composition_nested'))
    report['grouping_geometry_equal'] = (flat.get('status') == nested.get('status') == 'PASS'
                                       and flat['geometry'] == nested['geometry'])
    report['status'] = ('PASS' if report['grouping_geometry_equal'] and
                        all(c['status'] == 'PASS' for c in report['cases'].values()) else 'FAIL')
    save_progress()
    print('Runtime result:', report['status'], '| visual inspection: PENDING', flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
