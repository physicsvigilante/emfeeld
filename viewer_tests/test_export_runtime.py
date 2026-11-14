"""Exercise the actual PyVista exporter through the failure-safe scene CLI."""
import json
from pathlib import Path

import pytest
import pyvista  # Required real viewer dependency, never silently skipped.
from PIL import Image
from emfeeld.cli import main


@pytest.mark.parametrize('suffix', ['.png', ''])
def test_real_atomic_screenshot_with_explicit_or_default_extension(tmp_path, suffix):
    data = {'schema_version': 1, 'title': 'Export runtime verification', 'kind': 'electric',
            'sources': [{'type': 'solid_sphere', 'charge_C': 1e-9, 'radius_m': .5}],
            'bounds_m': [-2, 2, -2, 2, -2, 2]}
    path = tmp_path/'scene.json'; path.write_text(json.dumps(data), encoding='utf-8')
    original = path.read_bytes()
    requested = tmp_path/('preview'+suffix)
    target = requested if suffix else requested.with_suffix('.png')
    target.write_bytes(b'previous output')
    assert main(['view', str(path), '--screenshot', str(requested)]) == 0
    assert target.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    with Image.open(target) as image:
        assert image.width >= 500 and image.height >= 300
        assert any(lo != hi for lo,hi in image.convert('RGB').getextrema())
    assert original == path.read_bytes()
    assert not list(tmp_path.glob('.emfeeld-*'))
