"""Opt-in real windowed-timer smoke check. Requires a display (or Linux Xvfb).

Uses actual VTK native timer delivery; never invokes TimerEvent manually.
No human keyboard/mouse or Windows qualification is implied.
"""
import argparse
import json
from pathlib import Path
import time

from emfeeld import load_scene
from emfeeld.viewer import make_plotter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    scene=load_scene(Path(__file__).resolve().parents[1]/'examples/ideal_sun.json')
    plot=make_plotter(scene,off_screen=False,replay_seconds=1.2)
    controller=plot._emfeeld_playback
    events=[]
    report={'scope':'Real native timer delivery on this display; programmatic keys only.'}
    try:
        plot.show(auto_close=False,interactive=False,interactive_update=True)
        report['window']=plot.render_window.GetClassName()
        report['interactor']=plot.iren.interactor.GetClassName()
        def key(value):
            plot.iren.interactor.SetKeySym(value)
            plot.iren.interactor.InvokeEvent('KeyPressEvent')
        plot.iren.add_observer('TimerEvent',lambda *_: events.append(controller.state.index))
        def pump_until(predicate, timeout=5):
            deadline=time.monotonic()+timeout
            while not predicate() and time.monotonic()<deadline:
                plot.iren.process_events()
                time.sleep(.005)
            assert predicate(), 'Native timer did not reach the requested state'
        key('space')
        first_timer=controller.timer_id
        assert first_timer is not None and first_timer>0
        pump_until(lambda:controller.state.index>=250)
        key('space')
        paused=controller.state.index
        assert not controller.state.playing and controller.timer_id is None
        until=time.monotonic()+.15
        while time.monotonic()<until:
            plot.iren.process_events();time.sleep(.005)
        assert controller.state.index==paused
        key('space')
        assert controller.timer_id is not None
        pump_until(lambda:not controller.state.playing)
        assert controller.state.index==scene.samples-1 and controller.timer_id is None
        assert len(events)>=2
        assert tuple(plot.renderer.cube_axes_actor.bounds)==scene.bounds_m
        key('Home');assert controller.state.index==0
        key('space');assert controller.timer_id is not None
        report.update(status='PASS',timer_events=len(events),paused_sample=paused,
                      completed_sample=scene.samples-1,first_timer_id=first_timer)
    finally:
        plot.close()
    assert controller.closed and controller.timer_id is None and controller.observer_id is None
    report['close_cleanup']='PASS: closed while playing, timer and observer released'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
