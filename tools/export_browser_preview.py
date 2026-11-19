"""Build a NEW local Three.js demo folder from unchanged Python engine outputs.

Install the pinned browser-only dependency first with:
  npm install --prefix web/three_preview --ignore-scripts --no-audit --no-fund
No external server, uploaded data, executable authoring, or new field solver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from emfeeld.output_safety import protect_saved_evidence
from emfeeld.scene import scene_from_json
from emfeeld.visualization import build_visualization

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    protect_saved_evidence(args.output, new_directory=True)
    web = ROOT / 'web/three_preview'
    three = web / 'node_modules/three'
    version = json.loads((three / 'package.json').read_text())['version']
    if version != '0.180.0':
        raise ValueError('This preview requires the pinned three 0.180.0 package')
    # Preflight the inputs/dependencies before output creation.
    copied = {name: (web / name).read_bytes() for name in ['index.html','app.js','model.js','style.css']}
    for src, dst in [('build/three.module.js','vendor/three.module.js'),
                     ('build/three.core.js','vendor/three.core.js'),
                     ('examples/jsm/controls/OrbitControls.js','vendor/addons/controls/OrbitControls.js'),
                     ('LICENSE','vendor/THREE-LICENSE.txt')]:
        copied[dst] = (three / src).read_bytes()
    outputs = {}
    entries = []
    sha = lambda b: hashlib.sha256(b).hexdigest()
    for name in ['electric_composition', 'ideal_sun', 'line_plane_fields']:
        source = ROOT / f'examples/{name}.json'
        raw = source.read_bytes()
        scene = scene_from_json(raw.decode('utf-8'))
        snapshot = build_visualization(scene, resolution=21)
        encoded = (json.dumps(snapshot.to_dict(), allow_nan=False, separators=(',',':'))+'\n').encode()
        filename = f'{name}.json'
        outputs[filename] = encoded
        entries.append({'file':filename, 'title':scene.title, 'input':f'examples/{name}.json',
                        'input_sha256':sha(raw), 'sha256':sha(encoded)})
    copied.update(outputs)
    copied['manifest.json'] = (json.dumps({'prototype':True,'three_version':version,
        'physics_in_browser':False,'scenes':entries},indent=2)+'\n').encode()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in copied.items():
        path = args.output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (args.output/'INTEGRITY.json').write_text(json.dumps({'files':{k:sha(v) for k,v in copied.items()}},indent=2)+'\n')
    print(json.dumps({'output':str(args.output), 'scenes':len(entries), 'three_version':version,
                      'note':'Author rendering prototype, not a released or independently reviewed renderer'}))


if __name__ == '__main__':
    main()
