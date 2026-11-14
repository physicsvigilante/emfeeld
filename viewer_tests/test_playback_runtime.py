"""Real PyVista/VTK event tests; deterministic clock, not OS timer delivery."""
from pathlib import Path
import numpy as np
import pytest
from emfeeld import load_scene
from emfeeld import playback
from emfeeld.viewer import make_plotter

ROOT = Path(__file__).resolve().parents[1]


def key(plot, value):
    native = plot.iren.interactor
    native.SetKeySym(value)
    native.InvokeEvent('KeyPressEvent')


def tick(plot):
    plot.iren.interactor.InvokeEvent('TimerEvent')


@pytest.mark.parametrize('name', ['ideal_sun', 'electric_sphere', 'electric_composition'])
def test_real_keys_timer_slider_and_immutable_numerics(name, monkeypatch):
    clock = [100.]
    monkeypatch.setattr(playback, 'monotonic', lambda: clock[0])
    scene = load_scene(ROOT/'examples'/f'{name}.json')
    expected = scene.trajectories()
    original = [t.position_m.copy() for t in expected]
    monkeypatch.setattr(type(scene), 'trajectories', lambda self: expected)
    plot = make_plotter(scene, off_screen=True)
    controller = plot._emfeeld_playback
    try:
        plot.show(auto_close=False, interactive=False)
        axes = plot.renderer.cube_axes_actor
        labels = {a:list(getattr(axes, f'{a}_labels')) for a in 'xyz'}
        datasets = [a.mapper.dataset for a in plot.renderer.actors.values()
                    if hasattr(a, 'mapper') and hasattr(a.mapper, 'dataset')]
        markers = [next(m for m in datasets if m.n_points == 1 and
                        np.array_equal(m.points, t.position_m[:1])) for t in expected]
        potential = next(m for m in datasets if 'potential' in m.array_names)
        potential_before = potential['potential'].copy()
        # Any attempted resimulation during playback now fails this test.
        def forbidden(self):
            raise AssertionError('Playback must not recalculate trajectories')
        monkeypatch.setattr(type(scene), 'trajectories', forbidden)
        def check(index):
            assert controller.state.index == index
            for marker, trajectory in zip(markers, expected):
                np.testing.assert_array_equal(marker.points, trajectory.position_m[index:index+1])
            np.testing.assert_array_equal(axes.bounds, scene.bounds_m)
            for axis in 'xyz':
                assert list(getattr(axes, f'{axis}_labels')) == labels[axis]
            assert plot.renderer.actors['time'].input == f'Sample time: {controller.state.time_s:.6g} s'
            assert controller.slider.GetRepresentation().GetValue() == pytest.approx(controller.state.time_s)
            assert len(plot.scalar_bars.keys()) == 1
        check(0)
        key(plot, 'space'); assert controller.state.playing
        clock[0] += 3; tick(plot); check(round((scene.samples-1)/4))
        key(plot, 'space'); assert not controller.state.playing
        clock[0] += 20; tick(plot); check(round((scene.samples-1)/4))
        key(plot, 'space'); clock[0] += 3; tick(plot)
        middle = round((scene.samples-1)/2); check(middle)
        controller.slider.InvokeEvent('StartInteractionEvent')
        assert not controller.state.playing
        clock[0] += 5; tick(plot); check(middle)
        controller.slider.GetRepresentation().SetValue(scene.duration_s*.75)
        controller.slider.InvokeEvent('EndInteractionEvent')
        third = round((scene.samples-1)*.75); check(third)
        key(plot, 'Left'); check(third-1)
        key(plot, 'Right'); check(third)
        key(plot, 'Home'); check(0)
        assert not controller.state.playing
        key(plot, 'space'); clock[0] += 13; tick(plot)
        check(scene.samples-1)
        assert not controller.state.playing
        assert plot.renderer.actors['playback_status'].input == 'Finished'
        key(plot, 'space'); check(0)
        assert controller.state.playing
        np.testing.assert_array_equal(potential['potential'], potential_before)
        for t, saved in zip(expected, original):
            np.testing.assert_array_equal(t.position_m, saved)
    finally:
        plot.close()
    assert controller.closed and not controller.state.playing
    assert controller.timer_id is None and controller.observer_id is None
    controller.on_timer(); controller.toggle(); controller.close()  # inert/idempotent


def test_two_windows_have_separate_clocks(monkeypatch):
    clock=[0.]
    monkeypatch.setattr(playback, 'monotonic', lambda: clock[0])
    scene=load_scene(ROOT/'examples'/'ideal_sun.json')
    first=make_plotter(scene,off_screen=True)
    second=make_plotter(scene,off_screen=True)
    try:
        for plot in (first,second): plot.show(auto_close=False,interactive=False)
        key(first,'space');clock[0]=6.;tick(first);tick(second)
        assert first._emfeeld_playback.state.index == 500
        assert second._emfeeld_playback.state.index == 0
        first.close()
        key(second,'space');clock[0]=9.;tick(second)
        assert second._emfeeld_playback.state.index == 250
    finally:
        first.close();second.close()


def test_static_scene_has_no_playback_controller():
    plot=make_plotter(load_scene(ROOT/'examples'/'shell_fields.json'),off_screen=True)
    try:
        assert not hasattr(plot, '_emfeeld_playback')
        assert len(plot.widgets.slider_widgets)==0
    finally:
        plot.close()
