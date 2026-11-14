"""Display-only replay of saved samples. No physics or graphics imports."""
from math import isfinite
from time import monotonic


def _positive(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and positive")
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


class PlaybackState:
    """A paused-first, non-looping clock selecting nearest saved samples.

    replay_seconds is wall-clock time for the entire simulated interval. It is
    not a physical timestep. Delayed frames may skip samples, never integrate
    new states or interpolate positions. Stepping always pauses playback.
    """

    def __init__(self, duration_s, samples, *, replay_seconds=12.0):
        self.duration_s = _positive(duration_s, "duration_s")
        self.replay_seconds = _positive(replay_seconds, "replay_seconds")
        if type(samples) is not int or samples < 2:
            raise ValueError("samples must be an integer >= 2")
        self.samples = samples
        self.progress = 0.0
        self.playing = False

    @property
    def index(self):
        return min(self.samples - 1, round(self.progress * (self.samples - 1)))

    @property
    def time_s(self):
        return self.duration_s * (self.index / (self.samples - 1))

    def play(self):
        if self.progress >= 1.0:
            self.progress = 0.0
        self.playing = True

    def pause(self):
        self.playing = False

    def restart(self):
        self.progress = 0.0
        self.pause()

    def seek(self, time_s):
        time_s = float(time_s)
        if not isfinite(time_s):
            raise ValueError("seek time must be finite")
        self.progress = min(1.0, max(0.0, time_s / self.duration_s))
        self.pause()

    def step(self, direction):
        if type(direction) is not int or direction not in (-1, 1):
            raise ValueError("step direction must be -1 or 1")
        index = min(self.samples - 1, max(0, self.index + direction))
        self.progress = index / (self.samples - 1)
        self.pause()

    def advance(self, elapsed_s):
        elapsed_s = float(elapsed_s)
        if not isfinite(elapsed_s) or elapsed_s < 0:
            raise ValueError("elapsed time must be finite and nonnegative")
        if self.playing:
            self.progress = min(1.0, self.progress + elapsed_s / self.replay_seconds)
            if self.progress >= 1.0:
                self.pause()


class PlaybackController:
    """Bind a sample clock to one plotter. Created only for moving scenes.

    Windowed viewers use a native repeating VTK timer. Offscreen VTK has no
    native event loop: tests/capture tools must supply TimerEvents explicitly.
    The enclosing plotter calls close() before releasing its interactor.
    """

    def __init__(self, plot, state, display):
        self.plot, self.state, self.display = plot, state, display
        self.slider = None
        self.timer_id = None
        self.observer_id = None
        self.closed = False
        self._last_wall = None
        self._clock = monotonic
        plot.add_key_event("space", self.toggle)
        plot.add_key_event("Home", self.restart)
        plot.add_key_event("Left", self.backward)
        plot.add_key_event("Right", self.forward)

    def _update(self):
        if self.closed:
            return
        self.display(self.state)
        if self.slider is not None:
            self.slider.GetRepresentation().SetValue(self.state.time_s)
        self.plot.render()

    def _stop_timer(self):
        if self.timer_id is not None and self.plot.iren is not None:
            self.plot.iren.destroy_timer(self.timer_id)
        self.timer_id = None
        self._last_wall = None

    def pause(self, *_args):
        if self.closed:
            return
        self.state.pause()
        self._stop_timer()
        self._update()

    def toggle(self):
        if self.closed:
            return
        if self.state.playing:
            self.pause()
            return
        interactor = self.plot.iren
        if self.observer_id is None:
            self.observer_id = interactor.add_observer("TimerEvent", self.on_timer)
        self.state.play()
        self._last_wall = self._clock()
        if not self.plot.off_screen:
            if not interactor.initialized:
                interactor.initialize()
            self.timer_id = interactor.create_timer(33, repeating=True)
            if self.timer_id <= 0:
                self.timer_id = None
                self.pause()
                raise RuntimeError("VTK could not create a playback timer")
        self._update()

    def on_timer(self, *_args):
        if self.closed or not self.state.playing:
            return
        now = self._clock()
        self.state.advance(max(0.0, now - self._last_wall))
        self._last_wall = now
        if not self.state.playing:
            self._stop_timer()
        self._update()

    def seek(self, time_s):
        if self.closed:
            return
        self.state.seek(time_s)
        self._stop_timer()
        self._update()

    def restart(self):
        if self.closed:
            return
        self.state.restart()
        self._stop_timer()
        self._update()

    def _step(self, direction):
        if self.closed:
            return
        self.state.step(direction)
        self._stop_timer()
        self._update()

    def backward(self):
        self._step(-1)

    def forward(self):
        self._step(1)

    def close(self):
        if self.closed:
            return
        self.state.pause()
        self._stop_timer()
        if self.observer_id is not None and self.plot.iren is not None:
            self.plot.iren.remove_observer(self.observer_id)
        self.observer_id = None
        self.closed = True
