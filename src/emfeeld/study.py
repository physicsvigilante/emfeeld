"""Two configurations, one explicit source-strength change, recorded trajectories.

Run: python -m emfeeld.study run STUDY.json --output NEW_DIRECTORY [--render]
View: python -m emfeeld.study view DIRECTORY --configuration baseline|variant
No natural-language inference, inverse solving, collisions or new field laws.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from .dynamics import Trajectory, integrate
from .fields import DomainError, G, epsilon_0
from .observations import load_packet, packet_from_dict, run_packet, _digest, _number
from .scene import strict_keys
from .trajectory_samples import SOLVER_SETTINGS

CONFIGURATIONS = ('baseline', 'variant')
STRENGTHS = ('charge_C', 'mass_kg', 'charge_per_m_C_m', 'mass_per_m_kg_m',
             'charge_per_m2_C_m2', 'mass_per_m2_kg_m2')
REQUIREMENTS = ('fixed_prescribed_sources', 'independent_nonrelativistic_test_particles')
ARRAYS = ('time_s', 'position_m', 'velocity_m_s', 'kinetic_J', 'potential_J')
MEANING = ('Two-run agreement and energy drift are diagnostics, not certified error '
           'bounds or independent physical/source-interpretation verification.')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')


def validate_study(data):
    """Validate study metadata and baseline; derive the sole variant by replacement.

    Unknown physical requirements and baseline/variant model admission failures
    are reported without substituting a simpler source. They are not successes.
    """
    strict_keys(data, ('study_version', 'title', 'interpretation', 'baseline', 'change', 'checks'),
                ('study_version', 'title', 'interpretation', 'baseline', 'change', 'checks'))
    if type(data['study_version']) is not int or data['study_version'] != 1:
        raise ValueError('only study_version 1 is supported')
    _text(data['title'], 'title')
    record = data['interpretation']
    names = ('statement', 'givens', 'assumptions', 'illustrative_choices',
             'computed_inputs', 'unresolved', 'requirements')
    strict_keys(record, names, names)
    _text(record['statement'], 'statement')
    for name in names[1:]:
        if not isinstance(record[name], list):
            raise ValueError(f'interpretation.{name} must be an array')
        for item in record[name]:
            _text(item, name)
    change = data['change']
    names = ('source_index', 'parameter', 'from_value', 'to_value', 'origin', 'reason')
    strict_keys(change, names, names)
    if type(change['source_index']) is not int or change['source_index'] < 0:
        raise ValueError('source_index must be a nonnegative integer')
    if not isinstance(change['parameter'], str) or change['parameter'] not in STRENGTHS:
        raise ValueError('V1 changes one source strength only; no geometry/reference/launch changes')
    for name in ('from_value', 'to_value'):
        _number(change[name], name)
    if change['from_value'] == change['to_value']:
        raise ValueError('change must not be a no-op')
    if change['origin'] not in ('given', 'assumed', 'illustrative', 'computed'):
        raise ValueError('change origin must be explicit')
    _text(change['reason'], 'change.reason')
    checks = data['checks']
    names = ('position_atol_m', 'velocity_atol_m_s', 'rtol', 'max_normalized_energy_drift')
    strict_keys(checks, names, names)
    for name in names:
        _number(checks[name], name, positive=True)
    if not isinstance(data['baseline'], dict):
        raise ValueError('baseline must be an embedded observation packet')
    # Explicit requirements are author assertions, not automated NLP verification.
    unsupported = [x for x in record['requirements'] if x not in REQUIREMENTS]
    if unsupported or record['unresolved']:
        return {}, {'study': {'status': 'unsupported' if unsupported else 'incomplete',
                             'details': unsupported or record['unresolved']}}
    baseline = deepcopy(data['baseline'])
    try:
        packet_from_dict(baseline)
    except ValueError as exc:
        return {}, {'baseline': {'status': 'invalid_model', 'details': str(exc)}}
    try:
        source = baseline['scene']['sources'][change['source_index']]
    except IndexError as exc:
        raise ValueError('source_index outside baseline sources') from exc
    key = change['parameter']
    if key not in source or source[key] != change['from_value']:
        raise ValueError('from_value must match an existing source strength exactly')
    variant = deepcopy(baseline)
    variant['scene']['sources'][change['source_index']][key] = change['to_value']
    issues = {}
    try:
        packet_from_dict(variant)
    except ValueError as exc:
        issues['variant'] = {'status': 'invalid_model', 'details': str(exc)}
    return {'baseline': baseline, 'variant': variant}, issues


def validate_recorded(scene, trajectories):
    """Shape, time, initial-state and finite-data guard; NOT authenticity proof."""
    if len(trajectories) != len(scene.particles):
        raise ValueError('recorded particle count does not match scene')
    times = np.linspace(0., scene.duration_s, scene.samples)
    for particle, t in zip(scene.particles, trajectories):
        if t is None:
            raise ValueError('complete trajectories required; failed particles cannot be hidden')
        shapes = ((scene.samples,), (scene.samples, 3), (scene.samples, 3),
                  (scene.samples,), (scene.samples,))
        for name, shape in zip(ARRAYS, shapes):
            a = np.asarray(getattr(t, name))
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError(f'invalid recorded {name}')
        if (not np.array_equal(t.time_s, times)
                or not np.array_equal(t.position_m[0], particle.position_m)
                or not np.array_equal(t.velocity_m_s[0], particle.velocity_m_s)):
            raise ValueError('recorded times or initial conditions do not match scene')


def check_trajectory(scene, particle, trajectory, settings):
    if trajectory is None:
        return {'passed': False, 'reason': 'no complete captured trajectory'}
    refined = integrate(scene.model, particle, trajectory.time_s,
                        **{k: v / 10 for k, v in SOLVER_SETTINGS.items()},
                        max_step_s=scene.duration_s / 400)
    differences = {}
    passed = True
    for name, key in (('position_m', 'position_atol_m'), ('velocity_m_s', 'velocity_atol_m_s')):
        a, b = getattr(trajectory, name), getattr(refined, name)
        difference = np.abs(a - b)
        passed = passed and bool(np.all(difference <= settings[key] + settings['rtol'] * np.maximum(np.abs(a), np.abs(b))))
        differences[name] = float(np.max(difference))
    drift = max(float(trajectory.normalized_energy_drift), float(refined.normalized_energy_drift))
    passed = passed and math.isfinite(drift) and drift <= settings['max_normalized_energy_drift']
    return {'passed': passed, 'max_differences': differences, 'max_normalized_energy_drift': drift,
            'meaning': MEANING}


def _write(path, data):
    path.write_bytes((json.dumps(data, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def _capture(folder, packet, settings):
    scene, _ = packet_from_dict(packet)
    capture = {}
    native = run_packet(packet, capture=capture)
    trajectories = capture['trajectories']
    checks = []
    for i, (particle, trajectory) in enumerate(zip(scene.particles, trajectories)):
        try:
            check = check_trajectory(scene, particle, trajectory, settings)
        except (DomainError, FloatingPointError, OverflowError) as exc:
            check = {'passed': False, 'reason': str(exc)}
        except RuntimeError as exc:
            if not str(exc).startswith(('trajectory integration failed:', 'trajectory energies are nonfinite;',
                                        'trajectory integration produced nonfinite')):
                raise
            check = {'passed': False, 'reason': str(exc)}
        checks.append({'particle_index': i, **check})
    ready = all(t is not None for t in trajectories) and all(c['passed'] for c in checks)
    if ready:
        validate_recorded(scene, trajectories)
    _write(folder / 'packet.json', packet)
    _write(folder / 'result.json', native)
    arrays = {f'p{i}_{key}': getattr(t, key) for i, t in enumerate(trajectories)
              if t is not None for key in ARRAYS}
    # No pickled objects; failure of any particle blocks the full apparatus preview.
    np.savez_compressed(folder / 'trajectories.npz', **arrays)
    record = {'scene_sha256': native['scene_sha256'], 'render_ready': ready,
              'field_source_sha256': digest(Path(__file__).with_name('fields.py').read_text(encoding='utf-8').encode()),
              'trajectory_checks': checks, 'settings': settings,
              'event_policy': 'Event searches are separate from captured full-horizon trajectories.',
              'meaning': MEANING, 'static_checks': 'Native evaluation; no independent per-study reference implied.'}
    _write(folder / 'checks.json', record)
    files = {p.name: digest(p.read_bytes()) for p in sorted(folder.iterdir()) if p.is_file()}
    _write(folder / 'integrity.json', {'files': files, 'scene_sha256': native['scene_sha256']})
    unresolved = {r['id']: r['status'] for r in native['results']
                  if r['status'] != 'ok' or r.get('check', {}).get('passed') is False}
    return {'request_statuses': {r['id']: r['status'] for r in native['results']},
            'unfulfilled_requests': unresolved, 'render_ready': ready,
            'numerical_checks_passed': all(c['passed'] for c in checks),
            'scene_sha256': native['scene_sha256']}, native


def load_recorded(folder):
    folder = Path(folder)
    integrity = load_packet(folder / 'integrity.json')
    required = {'packet.json', 'result.json', 'checks.json', 'trajectories.npz'}
    if set(integrity.get('files', {})) != required:
        raise ValueError('invalid captured-run inventory')
    for name in required:
        if digest((folder / name).read_bytes()) != integrity['files'][name]:
            raise ValueError(f'captured-run hash mismatch: {name}')
    packet = load_packet(folder / 'packet.json')
    scene, _ = packet_from_dict(packet)
    if _digest(packet['scene']) != integrity['scene_sha256']:
        raise ValueError('captured scene identity mismatch')
    record = load_packet(folder / 'checks.json')
    if not record['render_ready']:
        raise ValueError('preview unavailable: incomplete or unqualified captured trajectories')
    native = load_packet(folder / 'result.json')
    if native['scene_sha256'] != integrity['scene_sha256'] or native['input'] != packet:
        raise ValueError('observation report does not belong to this packet')
    if native['constants_SI'] != {'G': G, 'epsilon_0': epsilon_0}:
        raise ValueError('installed physical constants differ from the captured run')
    if record['field_source_sha256'] != digest(Path(__file__).with_name('fields.py').read_text(encoding='utf-8').encode()):
        raise ValueError('field implementation differs from the captured run')
    trajectories = []
    with np.load(folder / 'trajectories.npz', allow_pickle=False) as data:
        if set(data.files) != {f'p{i}_{k}' for i in range(len(scene.particles)) for k in ARRAYS}:
            raise ValueError('recorded trajectory inventory mismatch')
        for i in range(len(scene.particles)):
            trajectories.append(Trajectory(**{k: data[f'p{i}_{k}'].copy() for k in ARRAYS}, evaluations=0))
    validate_recorded(scene, trajectories)
    return scene, tuple(trajectories)


def _comparisons(a, b):
    rows = []
    for x, y in zip(a.get('results', []), b.get('results', [])):
        row = {'id': x['id'], 'baseline_status': x['status'], 'variant_status': y['status'],
               'comparison': 'not_available'}
        if x['status'] == y['status'] == 'ok':
            if 'value' in x and 'value' in y and x.get('unit') == y.get('unit'):
                left, right = np.asarray(x['value']), np.asarray(y['value'])
                if left.shape == right.shape:
                    if x.get('time_s') != y.get('time_s'):
                        row['comparison'] = 'different_sample_times'; rows.append(row); continue
                    row.update(comparison='variant_minus_baseline', time_s=x.get('time_s'), unit=x['unit'],
                               baseline=x['value'], variant=y['value'], difference=(right-left).tolist())
            elif 'state' in x and 'state' in y:
                row.update(comparison='separate_event_states_not_equal_times',
                           baseline=x['state'], variant=y['state'], units=x['units'])
        rows.append(row)
    return rows


def run_study(path, output, *, render=False):
    path, output = Path(path), Path(output)
    raw = path.read_bytes()
    data = load_packet(path)
    if path.read_bytes() != raw:
        raise ValueError('study input changed while reading')
    packets, issues = validate_study(data)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'study.json').write_bytes(raw)
    summary = {'study_version': 1, 'title': data['title'], 'input_sha256': digest(raw),
               'change': data['change'], 'interpretation': data['interpretation'],
               'configurations': {}, 'issues': issues,
               'evaluation': {
                   'interpretation_fidelity': 'author_recorded; human review required',
                   'physical_correctness': 'see numerical checks; not independent certification',
                   'simulation_coverage': 'per-request statuses and complete-trajectory availability',
                   'educational_usefulness': 'awaiting teacher task feedback',
                   'textbook_answer_completeness': 'not evaluated; optional'},
               'engine_sha256': {p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}}
    summary['execution_complete'] = False
    summary['presentation'] = {'status': 'not_requested'}
    _write(output / 'summary.json', summary)  # Interrupted attempts never look complete.
    reports = {}
    for name in CONFIGURATIONS:
        if name in packets:
            folder = output / name
            folder.mkdir()
            if name in issues:
                _write(folder / 'packet.json', packets[name])
                _write(folder / 'rejection.json', issues[name])
                continue
            summary['configurations'][name], reports[name] = _capture(folder, packets[name], data['checks'])
    summary['comparisons'] = _comparisons(reports.get('baseline', {}), reports.get('variant', {}))
    summary['execution_complete'] = not issues and all(
        not x['unfulfilled_requests'] and x['numerical_checks_passed']
        for x in summary['configurations'].values())
    summary['presentation'] = {'status': 'not_requested'}
    _write(output / 'summary.json', summary)
    if render:
        try:
            summary['presentation'] = render_study(output)
        except (ValueError, OSError, RuntimeError) as exc:
            summary['presentation'] = {'status': 'failed', 'reason': str(exc)}
        _write(output / 'summary.json', summary)
    def display(value):
        if value is None:
            return '-'
        if isinstance(value, list):
            return '(' + ', '.join(f'{x:.7g}' for x in value) + ')'
        return f'{value:.7g}' if isinstance(value, (int, float)) else str(value)
    lines = [f"# {data['title']}", '', '## Teaching question', data['interpretation']['statement']]
    for key in ('givens', 'assumptions', 'illustrative_choices', 'computed_inputs', 'unresolved'):
        lines += ['', '### ' + key.replace('_', ' ').title()]
        lines += ['- ' + x for x in data['interpretation'][key]] or ['None recorded.']
    change = data['change']
    lines += ['', '## The only model change',
              f"Source {change['source_index']}: {change['parameter']} changes from "
              f"{display(change['from_value'])} to {display(change['to_value'])} ({change['origin']}).",
              change['reason'], 'Geometry, source types, launch states, potential references and observation requests stay fixed.',
              '', '## Computed measurements',
              '| Measurement | Unit | Physical time (s) | Baseline | Variant | Variant minus baseline |',
              '|---|---|---:|---|---|---|']
    for row in summary['comparisons']:
        if row['comparison'] == 'variant_minus_baseline':
            lines.append(f"| {row['id']} | {row['unit']} | {display(row['time_s'])} | "
                         f"{display(row['baseline'])} | {display(row['variant'])} | {display(row['difference'])} |")
        elif row['comparison'] == 'separate_event_states_not_equal_times':
            lines.append(f"| {row['id']} | event state | different event times | "
                         f"t={row['baseline']['time_s']:.7g} | t={row['variant']['time_s']:.7g} | not a same-time comparison |")
        else:
            lines.append(f"| {row['id']} | - | - | {row['baseline_status']} | {row['variant_status']} | unavailable |")
    lines += ['', '## Coverage and numerical checks']
    for name, item in summary['configurations'].items():
        lines.append(f"- {name}: numerical checks passed={item['numerical_checks_passed']}; "
                     f"unfulfilled requests={item['unfulfilled_requests']}; complete preview={item['render_ready']}.")
    lines += [str(issues) if issues else 'No admission issues recorded.', MEANING,
              '', '## Separate evaluation dimensions',
              *[f'- {k}: {v}' for k, v in summary['evaluation'].items()], '',
              '## Presentation', str(summary['presentation']['status']),
              'Shared colour range applies to potential only. Field arrows indicate direction, not strength.',
              'Each frame names its configuration and physical time. Playback uses captured arrays; event searches remain separate.']
    for frame in summary['presentation'].get('frames', []):
        lines += [f"![{frame['configuration']} at {frame['time_s']:.7g} s]({frame['file']})"]
    (output / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return summary


def _view_data(output):
    from .viewer import sample_values
    summary = load_packet(Path(output) / 'summary.json')
    if set(summary['configurations']) != set(CONFIGURATIONS) or not all(
            c['render_ready'] for c in summary['configurations'].values()):
        raise ValueError('both configurations require complete checked trajectories for comparison')
    study_path = Path(output) / 'study.json'
    if digest(study_path.read_bytes()) != summary['input_sha256']:
        raise ValueError('original study hash mismatch')
    expected, issues = validate_study(load_packet(study_path))
    if issues:
        raise ValueError('study has unresolved admission issues')
    for name in CONFIGURATIONS:
        actual = load_packet(Path(output) / name / 'packet.json')
        if actual != expected[name]:
            raise ValueError('captured configuration differs from the declared single change')
    records = [load_recorded(Path(output) / name) for name in CONFIGURATIONS]
    scenes = [r[0] for r in records]
    if scenes[0].bounds_m != scenes[1].bounds_m or scenes[0].model.kind != scenes[1].model.kind:
        raise ValueError('comparison view requires the same bounds and physical kind')
    bounds = scenes[0].bounds_m
    x, y = np.meshgrid(np.linspace(bounds[0], bounds[1], 41),
                       np.linspace(bounds[2], bounds[3], 41), indexing='ij')
    points = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, (bounds[4]+bounds[5])/2)))
    values = np.concatenate([sample_values(s.model, points, potential=True) for s in scenes])
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError('no finite common potential samples')
    low, high = float(values.min()), float(values.max())
    if low == high:
        padding = max(abs(low)*1e-6, 1e-12)
        low, high = low-padding, high+padding
    return records, (low, high)


def render_study(output):
    from .viewer import make_plotter
    output = Path(output)
    try:
        records, clim = _view_data(output)
    except ValueError as exc:
        return {'status': 'unavailable', 'reason': str(exc)}
    frames = []
    for name, (scene, trajectories) in zip(CONFIGURATIONS, records):
        plot = make_plotter(scene, recorded=trajectories, potential_clim=clim,
                            study_label=f'{name}; captured run', off_screen=True)
        try:
            plot.show(auto_close=False)
            indices = sorted({0, scene.samples//2, scene.samples-1}) if trajectories else [0]
            for index in indices:
                time = float(np.linspace(0, scene.duration_s, scene.samples)[index])
                if trajectories:
                    plot._emfeeld_playback.seek(time)
                filename = f'{name}_{index:05}.png'
                plot.screenshot(str(output / filename))
                frames.append({'file': filename, 'configuration': name, 'time_s': time,
                               'sha256': digest((output/filename).read_bytes())})
        finally:
            plot.close()
    return {'status': 'rendered_not_teacher_accepted', 'potential_clim': list(clim),
            'frames': frames, 'trajectory_source': 'captured arrays; zero integration during rendering'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'view'))
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--configuration', choices=CONFIGURATIONS, default='baseline')
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            if args.output is None:
                parser.error('run requires a new --output directory')
            report = run_study(args.input, args.output, render=args.render)
            print(json.dumps({'execution_complete': report['execution_complete'],
                              'output': str(args.output), 'issues': report['issues']}))
            rendered = not args.render or report['presentation']['status'] == 'rendered_not_teacher_accepted'
            return 0 if report['execution_complete'] and rendered else 1
        if args.output is not None or args.render:
            parser.error('view takes no --output or --render')
        from .viewer import make_plotter
        records, clim = _view_data(args.input)
        scene, trajectories = records[CONFIGURATIONS.index(args.configuration)]
        plot = make_plotter(scene, recorded=trajectories, potential_clim=clim,
                            study_label=f'{args.configuration}; captured run')
        try:
            plot.show()
        finally:
            plot.close()
        return 0
    except (ValueError, OSError) as exc:
        print(f'emfeeld study: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
