"""Execute actual Chromium WebGL against the generated, local Three.js folder.

Requires the optional test-only playwright package and Chromium. This is author
browser automation, not independent review, human interaction or pixel parity.
"""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preview', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--chromium', default=None)
    args = p.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.preview.resolve()
    manifest = json.loads((root/'manifest.json').read_text())
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    result = [];errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=args.chromium,
                args=['--no-sandbox','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])
            page = browser.new_page(viewport={'width':1280,'height':900},device_scale_factor=1)
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='networkidle')
            page.wait_for_function('window.emfeeldPreview || window.emfeeldPreviewError')
            assert page.evaluate('window.emfeeldPreviewError || null') is None
            for i, entry in enumerate(manifest['scenes']):
                if i:
                    page.select_option('#scene', str(i))
                    page.wait_for_function('(file)=>window.emfeeldPreview.inspect().source.file===file && !document.querySelector("#scene").disabled', arg=entry['file'])
                source = json.loads((root/entry['file']).read_text())
                before = page.evaluate('window.emfeeldPreview.inspect()')
                assert before['snapshot'] == source
                assert before['three_revision'] == '180'
                assert 'WebGL' in before['webgl_version']
                positions = [t['positions_m'] for t in source['trajectories']]
                indices = [0, source['animation']['samples']//2, source['animation']['samples']-1] if positions else [0]
                records = []
                for index in indices:
                    if positions:
                        page.locator('#frame').fill(str(index));page.locator('#frame').dispatch_event('input')
                    report = page.evaluate('window.emfeeldPreview.inspect()')
                    assert report['snapshot'] == source  # camera/replay must not mutate the physical payload
                    assert report['frame']['index'] == index
                    expected = [t[index] for t in positions]
                    assert report['frame']['positions_m'] == expected
                    origin = report['transform']['origin_m'];scale=report['transform']['scale_m']
                    for actual, world in zip(report['marker_display'], expected):
                        assert all(math.isclose(a,(b-o)/scale,rel_tol=1e-13,abs_tol=1e-14)
                                   for a,b,o in zip(actual,world,origin))
                    assert len(report['arrow_origins']) == len(source['field']['schematic_arrows']['origins_m'])
                    for actual,world in zip(report['arrow_origins'],source['field']['schematic_arrows']['origins_m']):
                        assert all(math.isclose(a,(b-o)/scale,rel_tol=1e-13,abs_tol=1e-14)
                                   for a,b,o in zip(actual,world,origin))
                    page.screenshot(path=str(args.output/f'{i}-sample-{index}.png'))
                    records.append({'index':index,'physical_time_s':report['frame']['time_s'],
                                    'actual_marker_display':report['marker_display']})
                if positions:
                    page.locator('#frame').fill('0');page.locator('#frame').dispatch_event('input')
                    page.click('#play');page.wait_for_function('Number(document.querySelector("#frame").value)>0')
                    page.click('#play')
                else:
                    assert page.locator('#play').is_disabled()
                camera = page.evaluate('window.emfeeldPreview.inspect().camera')
                box = page.locator('canvas').first.bounding_box()
                page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5)
                page.mouse.down();page.mouse.move(box['x']+box['width']*.65,box['y']+box['height']*.55,steps=10);page.mouse.up()
                page.wait_for_function('(c)=>JSON.stringify(window.emfeeldPreview.inspect().camera)!==JSON.stringify(c)',arg=camera)
                assert page.evaluate('window.emfeeldPreview.inspect().snapshot') == source
                result.append({'file':entry['file'],'webgl':before['webgl_version'],
                               'omitted_cells':before['omitted_cells'],'samples':records})
            assert not errors, errors
            browser.close()
        (args.output/'report.json').write_text(json.dumps({'scenes':result,'browser_errors':errors,
            'physics_in_browser':False,'independent_review':'not_evaluated'},indent=2)+'\n')
        print(json.dumps({'actual_chromium_webgl_scenes':len(result),'browser_errors':errors}))
    finally:
        server.shutdown();server.server_close();thread.join()
    files = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in args.output.iterdir() if path.is_file()}
    (args.output/'integrity.json').write_text(json.dumps({'files':files},indent=2)+'\n')


if __name__ == '__main__':
    main()
