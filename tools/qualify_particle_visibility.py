"""Capture native particle visibility at saved states, not fabricated animation.

Run from an installed checkout with the existing view extra and graphics support.
These pixel and identity checks are not human desktop/teaching qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import numpy as np

from emfeeld.scene import load_scene
from emfeeld.viewer import make_plotter

ROOT = Path(__file__).resolve().parents[1]


def capture(scene_path, output):
    scene = load_scene(scene_path)
    trajectories = scene.trajectories()
    original = [t.position_m.copy() for t in trajectories]
    plot = make_plotter(scene, recorded=trajectories, off_screen=True)
    frames = []
    try:
        plot.show(auto_close=False)
        for index in (0, scene.samples//2, scene.samples-1):
            time = float(trajectories[0].time_s[index])
            plot._emfeeld_playback.seek(time)
            filename = f'{scene_path.stem}_{index:05d}.png'
            image = plot.screenshot(str(output/filename))
            np.testing.assert_array_equal(plot.renderer.cube_axes_actor.bounds, scene.bounds_m)
            particles = []
            for i, trajectory in enumerate(trajectories):
                position = trajectory.position_m[index]
                actor = plot.actors[f'particle_{i}']
                np.testing.assert_array_equal(actor.mapper.dataset.points, position[None,:])
                plot.renderer.SetWorldPoint(*position, 1.)
                plot.renderer.WorldToDisplay()
                x, y, _ = plot.renderer.GetDisplayPoint()
                x, y = int(round(x)), image.shape[0]-1-int(round(y))
                patch = image[max(0,y-22):y+23, max(0,x-22):x+23, :3]
                mask = (patch[:,:,0] > 160) & (patch[:,:,1] < 125) & (patch[:,:,2] > 140)
                pixels = int(mask.sum())
                if pixels < 80:
                    raise AssertionError(f'{scene_path.name} particle {i}, sample {index}: only {pixels} marker pixels')
                particles.append({'index':i, 'position_m':position.tolist(),
                                  'projected_center_pixels':[x,y], 'nearby_magenta_pixels':pixels})
            frames.append({'file':filename, 'sample_index':index, 'time_s':time,
                           'particles':particles,
                           'sha256':hashlib.sha256((output/filename).read_bytes()).hexdigest()})
        for trajectory, saved in zip(trajectories,original):
            np.testing.assert_array_equal(trajectory.position_m,saved)
        return {'scene':str(scene_path.relative_to(ROOT)),
                'scene_sha256':hashlib.sha256(scene_path.read_bytes()).hexdigest(),
                'frames':frames, 'status':'passed',
                'scope':'Saved-position equality and local pixel visibility in these authored views only.'}
    finally:
        plot.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    report={'status':'started', 'python':platform.python_version(), 'platform':platform.platform(),
            'versions':{n:importlib.metadata.version(n) for n in ('numpy','scipy','pyvista','vtk')},
            'cases':[], 'visual_review':'separate human/author inspection required'}
    def write():
        (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write()
    for name in ('opposite_spheres_visibility.json','ideal_sun.json'):
        report['cases'].append(capture(ROOT/'examples'/name,args.output));write()
    report['status']='passed';write()
    print(json.dumps({'status':report['status'], 'scenes':len(report['cases']),
                      'frames':sum(len(c['frames']) for c in report['cases'])}))


if __name__=='__main__':
    main()
