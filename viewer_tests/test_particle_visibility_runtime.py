"""Native particle visibility: actual rendered pixels and unchanged saved states.

A visible glyph is not its physical radius. Screenshots do not qualify every
camera, occlusion, display device, or human interaction.
"""
from pathlib import Path

import numpy as np
import pytest

from emfeeld.scene import Scene, load_scene
from emfeeld.viewer import make_plotter

ROOT = Path(__file__).resolve().parents[1]


def magenta_region(plot, image, position):
    """Count high-contrast marker pixels near its projected physical position."""
    plot.renderer.SetWorldPoint(*position, 1.0)
    plot.renderer.WorldToDisplay()
    x, y, _ = plot.renderer.GetDisplayPoint()
    x, y = int(round(x)), image.shape[0] - 1 - int(round(y))
    patch = image[max(0,y-22):y+23, max(0,x-22):x+23, :3]
    mask = (patch[:,:,0] > 160) & (patch[:,:,1] < 125) & (patch[:,:,2] > 140)
    return int(mask.sum()), (x, y)


@pytest.mark.parametrize('camera', ['iso', 'xy'])
def test_particle_is_visible_on_its_path_and_potential_slice(camera, monkeypatch):
    scene = load_scene(ROOT/'examples/opposite_spheres_visibility.json')
    trajectories = scene.trajectories()
    snapshots = [{key: getattr(t, key).copy() for key in
                  ('time_s','position_m','velocity_m_s','kinetic_J','potential_J')}
                 for t in trajectories]
    def forbidden(*args, **kwargs):
        pytest.fail('recorded playback must not integrate another trajectory')
    monkeypatch.setattr(Scene, 'trajectories', forbidden)
    plot = make_plotter(scene, recorded=trajectories, off_screen=True)
    try:
        if camera == 'xy': plot.view_xy()
        plot.show(auto_close=False)
        marker = plot.actors['particle_0']
        path = plot.actors['trajectory_0']
        assert marker.mapper.dataset.n_points > 1
        assert marker.mapper.dataset.n_cells > 0
        assert marker.prop.GetRepresentation() == 2
        assert marker.use_bounds is False
        assert not marker.prop.lighting
        assert marker.prop.color.hex_rgb == '#ff00ff'
        assert path.prop.color.hex_rgb == '#000000'
        assert tuple(marker.prop.color) != tuple(path.prop.color)
        assert 'schematic' in plot.actors['particle_key'].input.lower()
        assert 'not charge sign' in plot.actors['particle_key'].input
        assert set(plot.scalar_bars.keys()) == {'Potential [V]'}
        centers = []
        for index in (0, scene.samples//2, scene.samples-1):
            slider = plot._emfeeld_playback.slider
            slider.GetRepresentation().SetValue(float(trajectories[0].time_s[index]))
            slider.InvokeEvent('EndInteractionEvent')
            np.testing.assert_array_equal(marker.position,
                                          trajectories[0].position_m[index])
            np.testing.assert_array_equal(plot.renderer.cube_axes_actor.bounds, scene.bounds_m)
            image = plot.screenshot(return_img=True)
            pixels, center = magenta_region(plot, image, trajectories[0].position_m[index])
            assert pixels >= 80, f'only {pixels} marker pixels in {camera} at sample {index}'
            centers.append(center)
        assert np.linalg.norm(np.subtract(centers[-1], centers[0])) > 15
        for t, saved in zip(trajectories, snapshots):
            for key, value in saved.items(): np.testing.assert_array_equal(getattr(t,key), value)
    finally:
        plot.close()


def test_both_gravity_particles_have_moving_visible_markers(monkeypatch):
    scene = load_scene(ROOT/'examples/ideal_sun.json')
    ts = scene.trajectories()
    original = [t.position_m.copy() for t in ts]
    monkeypatch.setattr(Scene, 'trajectories', lambda *a: pytest.fail('unexpected solve'))
    p = make_plotter(scene, recorded=ts, off_screen=True)
    try:
        p.show(auto_close=False)
        for index in (0, scene.samples//2, scene.samples-1):
            p._emfeeld_playback.seek(float(ts[0].time_s[index]))
            image = p.screenshot(return_img=True)
            for i,t in enumerate(ts):
                a = p.actors[f'particle_{i}']
                np.testing.assert_array_equal(a.position, t.position_m[index])
                pixels, _ = magenta_region(p, image, t.position_m[index])
                assert pixels >= 80
        for t,saved in zip(ts,original): np.testing.assert_array_equal(t.position_m,saved)
    finally:p.close()


def test_static_scenes_do_not_acquire_particles_or_movement_labels():
    p = make_plotter(load_scene(ROOT/'examples/shell_fields.json'), off_screen=True)
    try:
        assert not any(name.startswith('particle_') for name in p.actors)
        assert not hasattr(p,'_emfeeld_playback')
        assert set(p.scalar_bars.keys()) == {'Potential [V]'}
    finally:p.close()
