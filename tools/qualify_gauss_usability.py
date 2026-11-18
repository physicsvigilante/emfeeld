"""Retain actual default/small-window scenes; not human teaching acceptance."""
import argparse
from pathlib import Path

from emfeeld.gauss_lesson import GaussState, GaussianCube, GaussianSphere, HeldCharge
from emfeeld.gauss_view import GaussLesson, save_snapshot
from emfeeld.output_safety import protect_saved_evidence


def qualify(output):
    output = Path(output)
    protect_saved_evidence(output, new_directory=True)
    sphere = GaussianSphere()
    q = lambda x, sign=1: HeldCharge(sign * 1e-9, (x, 0, 0))
    cases = [
        ('near_inside_small', sphere, (q(.9999),), (840, 560), True),
        ('near_outside_small', sphere, (q(1.0001),), (840, 560), True),
        ('near_inside_default', sphere, (q(.9999),), (1440, 960), True),
        ('zero_net_small', sphere, (q(.9999), q(0, -1)), (840, 560), True),
        ('boundary_small', sphere, (q(1),), (840, 560), False),
        ('cube_small', GaussianCube(), (q(.5),), (840, 560), False),
    ]
    for name, surface, charges, size, visible in cases:
        state = GaussState(surface=surface, charges=charges)
        lesson = GaussLesson(state, off_screen=True)
        try:
            lesson.plot.window_size = size
            lesson.plot.show(auto_close=False, interactive=False)
            report = save_snapshot(state, output / name, lesson=lesson)
            assert report['display']['sampling_caution_visible'] is visible
            assert report['display']['window_size_pixels'] == list(size)
            if name in ('near_outside_small', 'zero_net_small'):
                assert report['physics']['exact_total_N_m2_per_C'] == 0
            if name == 'boundary_small':
                assert report['physics']['exact_total_N_m2_per_C'] is None
            print(name, report['physics']['status'], 'caution:', visible, flush=True)
        finally:
            lesson.plot.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    qualify(parser.parse_args().output)
