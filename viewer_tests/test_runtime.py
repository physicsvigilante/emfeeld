"""Optional real PyVista tests. Run explicitly with the [dev,view] extras installed.

The ordinary headless suite's testpaths remains tests/. No skips or fake backends
are used here; missing PyVista is an error when this suite is requested.
"""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('viewer_qualification', ROOT / 'tools/qualify_viewer.py')
QUALIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFY)


@pytest.mark.parametrize('example', ['electric_composition', 'ideal_sun', 'shell_fields'])
def test_real_legend_slider_axes_and_captures(example, tmp_path):
    scene = QUALIFY.load_scene(ROOT / 'examples' / f'{example}.json')
    result = QUALIFY.capture(example, scene, tmp_path)
    assert result['status'] == 'PASS'
    assert len(result['frames']) == (3 if scene.particles else 1)
    for frame in result['frames']:
        assert frame['axis_bounds_m'] == list(scene.bounds_m)
        assert (tmp_path / frame['file']).is_file()


def test_real_flat_nested_geometry_and_pixels_match(tmp_path):
    cases = dict(QUALIFY.cases())
    flat = QUALIFY.capture('composition_flat', cases['composition_flat'], tmp_path)
    nested = QUALIFY.capture('composition_nested', cases['composition_nested'], tmp_path)
    assert flat['geometry'] == nested['geometry']
    assert flat['frames'][0]['png_sha256'] == nested['frames'][0]['png_sha256']
