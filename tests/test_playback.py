"""Replay state tests require neither PyVista nor a graphics runtime."""
import pytest
from emfeeld.playback import PlaybackState


@pytest.mark.parametrize('duration', [1e-9, 10., 31557718.872965656])
def test_clock_plays_existing_sample_range(duration):
    state = PlaybackState(duration, 1001, replay_seconds=12)
    assert (state.index, state.playing) == (0, False)
    state.advance(100)
    assert state.index == 0
    state.play(); state.advance(3)
    assert state.index == 250
    state.pause(); state.advance(1000)
    assert state.index == 250
    state.play(); state.advance(3)
    assert state.index == 500
    assert state.time_s == pytest.approx(duration / 2)
    state.advance(7)
    assert state.index == 1000 and not state.playing
    state.play()
    assert state.index == 0 and state.playing


def test_seek_steps_restart_and_clamping():
    state = PlaybackState(4, 5)
    state.play(); state.seek(2.1)
    assert state.index == 2 and not state.playing
    state.step(1); assert state.index == 3
    state.step(-1); assert state.index == 2
    state.seek(100); state.step(1)
    assert state.index == 4
    state.seek(-100); state.step(-1)
    assert state.index == 0
    state.play(); state.advance(3); state.restart()
    assert state.index == 0 and not state.playing


def test_elapsed_not_event_count_controls_replay():
    a, b = PlaybackState(100, 101), PlaybackState(100, 101)
    a.play(); b.play()
    a.advance(6)
    for _ in range(60): b.advance(.1)
    assert a.index == b.index == 50


@pytest.mark.parametrize('kwargs', [dict(duration_s=0),dict(duration_s=float('nan')),
    dict(duration_s=True),dict(samples=1),dict(samples=True),dict(samples=2.5),
    dict(replay_seconds=0),dict(replay_seconds=-1),dict(replay_seconds=float('inf'))])
def test_invalid_state_arguments(kwargs):
    args=dict(duration_s=1,samples=3);args.update(kwargs)
    with pytest.raises(ValueError): PlaybackState(**args)


@pytest.mark.parametrize('value', [float('nan'),float('inf'),-1])
def test_invalid_elapsed(value):
    with pytest.raises(ValueError): PlaybackState(1,3).advance(value)


@pytest.mark.parametrize('value', [float('nan'),float('inf')])
def test_invalid_seek(value):
    with pytest.raises(ValueError): PlaybackState(1,3).seek(value)


@pytest.mark.parametrize('value', [0,2,True,.5])
def test_invalid_step(value):
    with pytest.raises(ValueError): PlaybackState(1,3).step(value)


def test_sample_time_does_not_overflow_for_finite_duration():
    state = PlaybackState(1e308, 1001)
    state.seek(1e308)
    assert state.time_s == 1e308
