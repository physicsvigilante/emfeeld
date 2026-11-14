"""Regression tests for authored-input coercion and destructive scene outputs."""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest
from emfeeld import cli
from emfeeld.scene import scene_from_dict, load_scene, source_from_dict
from emfeeld.observations import packet_from_dict

BASE = {'schema_version': 1, 'title': 'safety', 'kind': 'electric',
        'sources': [{'type': 'point', 'charge_C': 1e-9}],
        'bounds_m': [-2, 2, -2, 2, -2, 2]}


@pytest.mark.parametrize('bad', [True, False, '1', None, float('nan'), float('inf')])
@pytest.mark.parametrize('location', ['strength', 'center', 'bounds', 'duration', 'mass', 'velocity'])
def test_scene_numeric_input_does_not_coerce(bad, location):
    data = deepcopy(BASE)
    if location == 'strength': data['sources'][0]['charge_C'] = bad
    if location == 'center': data['sources'][0]['center_m'] = [bad, 0, 0]
    if location == 'bounds': data['bounds_m'][0] = bad
    if location == 'duration': data['duration_s'] = bad
    if location in ('mass', 'velocity'):
        data.update(duration_s=1, particles=[{'mass_kg': 1, 'charge_C': 1e-6,
                    'position_m': [1, 0, 0], 'velocity_m_s': [0, 0, 0]}])
        if location == 'mass': data['particles'][0]['mass_kg'] = bad
        else: data['particles'][0]['velocity_m_s'][0] = bad
    with pytest.raises(ValueError): scene_from_dict(data)


@pytest.mark.parametrize('source_type', [[], {}, 1, True, None])
def test_malformed_source_tag_is_a_schema_error(source_type):
    with pytest.raises(ValueError):
        source_from_dict('electric', {'type': source_type, 'charge_C': 1e-9})


def test_loader_and_packet_boundary_agree_on_bad_coordinate(tmp_path):
    data = deepcopy(BASE); data['sources'][0]['center_m'] = ['1', 0, 0]
    path = tmp_path/'bad.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_scene(path)
    with pytest.raises(ValueError): packet_from_dict({'observation_schema_version': 1,
        'scene': data, 'observations': [{'id': 'V', 'type': 'potential', 'position_m': [1, 0, 0]}]})


@pytest.mark.parametrize('command,flag', [('run', '--output'), ('view', '--screenshot')])
@pytest.mark.parametrize('alias', ['same', 'relative', 'symlink', 'hardlink'])
def test_scene_output_cannot_overwrite_input(tmp_path, monkeypatch, command, flag, alias):
    path = tmp_path/'scene.json'; path.write_text(json.dumps(BASE)); before = path.read_bytes()
    dest = path
    if alias == 'relative':
        monkeypatch.chdir(tmp_path); dest = Path('scene.json')
    elif alias == 'symlink':
        dest = tmp_path/'alias.json'; dest.symlink_to(path)
    elif alias == 'hardlink':
        dest = tmp_path/'alias.json'; os.link(path, dest)
    # Must reject before integration or graphics, not after destroying the file.
    monkeypatch.setattr(cli, 'run_scene', lambda *_: pytest.fail('ran before path check'))
    import emfeeld.viewer as viewer
    monkeypatch.setattr(viewer, 'make_plotter', lambda *_args, **_kwargs: pytest.fail('rendered before path check'))
    assert cli.main([command, str(path), flag, str(dest)]) == 2
    assert path.read_bytes() == before


def test_failed_npz_export_preserves_previous_output(tmp_path, monkeypatch):
    path = tmp_path/'scene.json'; path.write_text(json.dumps(BASE)); before = path.read_bytes()
    dest = tmp_path/'old.npz'; dest.write_bytes(b'previous result')
    def fail_after_write(handle, **_arrays):
        handle.write(b'incomplete result')
        raise OSError('simulated write failure')
    monkeypatch.setattr(np, 'savez_compressed', fail_after_write)
    assert cli.main(['run', str(path), '--output', str(dest)]) == 2
    assert dest.read_bytes() == b'previous result'
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.emfeeld-*'))


def test_successful_npz_export_replaces_previous_output(tmp_path):
    path = tmp_path/'scene.json'; path.write_text(json.dumps(BASE))
    dest = tmp_path/'old.npz'; dest.write_bytes(b'previous result')
    assert cli.main(['run', str(path), '--output', str(dest)]) == 0
    with np.load(dest, allow_pickle=False) as saved:
        assert json.loads(str(saved['scene_json'])) == BASE
    assert not list(tmp_path.glob('.emfeeld-*'))
