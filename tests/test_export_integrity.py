"""Regression tests for truthful source provenance and failure-safe screenshots."""
import json
from pathlib import Path

import numpy as np
import pytest

from emfeeld import cli
from emfeeld.scene import scene_from_dict

BASE = {'schema_version': 1, 'title': 'original', 'kind': 'electric',
        'sources': [{'type': 'uniform', 'field_N_C': [1, 0, 0]}],
        'bounds_m': [-2, 2, -2, 2, -2, 2]}


def test_npz_records_the_document_actually_parsed(tmp_path, monkeypatch):
    scene = tmp_path/'scene.json'
    original = json.dumps(BASE, indent=2)+'\n'
    scene.write_text(original, encoding='utf-8')
    replacement = dict(BASE, title='replaced while running')
    original_run = cli.run_scene
    def modify_during_run(model):
        scene.write_text(json.dumps(replacement), encoding='utf-8')
        return original_run(model)
    monkeypatch.setattr(cli, 'run_scene', modify_during_run)
    output = tmp_path/'result.npz'
    assert cli.main(['run', str(scene), '--output', str(output)]) == 0
    with np.load(output, allow_pickle=False) as saved:
        assert str(saved['scene_json']) == original
        assert json.loads(str(saved['scene_json']))['title'] == json.loads(str(saved['summary_json']))['title']


@pytest.mark.parametrize('error', [OSError, RuntimeError])
def test_failed_screenshot_retains_existing_file(tmp_path, monkeypatch, error):
    import emfeeld.viewer as viewer
    scene = tmp_path/'scene.json'
    scene.write_text(json.dumps(BASE), encoding='utf-8')
    old_input = scene.read_bytes()
    output = tmp_path/'preview.png'; output.write_bytes(b'previous complete picture')
    class FakePlot:
        closed = False
        def show(self, *, screenshot):
            Path(screenshot).write_bytes(b'incomplete picture')
            raise error('injected render failure')
        def close(self):
            self.closed = True
    plot = FakePlot()
    monkeypatch.setattr(viewer, 'make_plotter', lambda *a, **k: plot)
    assert cli.main(['view', str(scene), '--screenshot', str(output)]) == 2
    assert output.read_bytes() == b'previous complete picture'
    assert scene.read_bytes() == old_input
    assert plot.closed
    assert not list(tmp_path.glob('.emfeeld-*'))


@pytest.mark.parametrize('suffix', ['.png', '.jpg', ''])
def test_successful_screenshot_commits_staged_picture(tmp_path, monkeypatch, suffix):
    import emfeeld.viewer as viewer
    scene = tmp_path/'scene.json'; scene.write_text(json.dumps(BASE), encoding='utf-8')
    dest = tmp_path/('preview'+suffix)
    target = dest if suffix else dest.with_suffix('.png')
    target.write_bytes(b'old picture')
    class FakePlot:
        closed = False
        def show(self, *, screenshot):
            assert Path(screenshot) != target
            assert target.read_bytes() == b'old picture'
            assert Path(screenshot).suffix == (suffix or '.png')
            Path(screenshot).write_bytes(b'new complete picture')
        def close(self): self.closed = True
    plot = FakePlot(); monkeypatch.setattr(viewer, 'make_plotter', lambda *a, **k: plot)
    assert cli.main(['view', str(scene), '--screenshot', str(dest)]) == 0
    assert target.read_bytes() == b'new complete picture'
    assert plot.closed
    assert not list(tmp_path.glob('.emfeeld-*'))


def test_implicit_png_path_cannot_alias_input(tmp_path, monkeypatch):
    import emfeeld.viewer as viewer
    scene = tmp_path/'scene.png'; scene.write_text(json.dumps(BASE), encoding='utf-8')
    before = scene.read_bytes()
    monkeypatch.setattr(viewer, 'make_plotter', lambda *a, **k: pytest.fail('rendered before alias check'))
    assert cli.main(['view', str(scene), '--screenshot', str(tmp_path/'scene')]) == 2
    assert scene.read_bytes() == before
