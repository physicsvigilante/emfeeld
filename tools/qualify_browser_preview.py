"""Execute actual Chromium WebGL against the generated, local Three.js folder.

Requires the optional test-only playwright package and Chromium. This is author
browser automation, not independent review, human interaction or pixel parity.
"""
import argparse
import copy
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


def refusal_cases(source):
    """Test-only JSON mutations; matching hashes ensure the validator is reached."""
    cases = []
    def change(name, path, value, expected, remove=False):
        d = copy.deepcopy(source)
        target = d
        for key in path[:-1]:
            target = target[key]
        if remove:
            del target[path[-1]]
        else:
            target[path[-1]] = value
        cases.append((name, d, expected))
    for name, path, value, expected in [
        ('potential-role', ('potential','role'), 'physical_material_surface', 'potential slice'),
        ('source-role', ('geometry',0,'role'), 'physical_impenetrable_wall', 'source geometry role'),
        ('marker-role', ('trajectories',0,'marker_role'), 'actual_radius_and_charge_sign', 'saved trajectory'),
        ('annotation-role', ('annotations',0,'role'), 'unknown', 'annotations'),
        ('time-unit', ('animation','time_unit'), 'years', 'saved timeline'),
    ]:
        change(name, path, value, expected)
        change('missing-'+name, path, None, expected, remove=True)
    change('missing-source-id', ('geometry',0,'id'), None, 'source id', remove=True)
    change('missing-marker-id', ('trajectories',0,'id'), None, 'trajectory id', remove=True)
    change('missing-moving-slice', ('moving_slice',), None, 'display flags', remove=True)
    change('nonboolean-moving-slice', ('moving_slice',), 'false', 'display flags')
    change('missing-uniform-flag', ('has_uniform_source',), None, 'display flags', remove=True)
    change('span-overflow', ('bounds_m',), [-1e308,1e308,-1,1,-1,1], 'Unrenderable bounds span')
    change('extreme-translated-bounds', ('bounds_m',), [1e308-3e306,1e308+3e306,-1,1,-1,1], 'Unrenderable')
    change('arrow-underflow', ('field','schematic_arrows','display_length_m'), 5e-324, 'arrow length')
    change('marker-underflow', ('trajectories',0,'marker_radius_m'), 5e-324, 'marker length')
    change('source-coordinate-overflow', ('geometry',0,'center_m',0), 1e308, 'source position')
    change('trajectory-coordinate-overflow', ('trajectories',0,'positions_m',0,0), 1e308, 'trajectory position')
    change('arrow-coordinate-overflow', ('field','schematic_arrows','origins_m',0,0), 1e308, 'arrow position')
    change('potential-coordinate-overflow', ('potential','points_m',0,0,0), 1e308, 'potential position')
    for shape in ['line','plane']:
        d = copy.deepcopy(source)
        d['geometry'][0].update(shape=shape, role='truncated_infinite_source', direction=[0,0,0], display_span_m=1)
        cases.append((shape+'-zero-direction', d, 'infinite-source patch'))
    # Review-02 regressions: all ordinary fields remain valid; only these
    # rendered primitives lose distinctions/area on Float32 buffer conversion.
    def buffer_scene():
        d = copy.deepcopy(source)
        d['bounds_m'] = [-10,10,-10,10,-10,10]
        d['animation']['samples'] = 61
        for path in d['trajectories']:
            path['positions_m'] = [[20*(.25+i*1e-6),0,0] for i in range(61)]
        return d
    def small_path(d, base=.25, step=1e-11):
        d['trajectories'][0]['positions_m'] = [[20*(base+i*step),0,0] for i in range(61)]
    def small_surface(d):
        d['potential']['points_m'] = [[[5,5,0],[5,5+2e-8,0]],[[5+2e-8,5,0],[5+2e-8,5+2e-8,0]]]
        d['potential']['values'] = [1,2,3,4]
    d = buffer_scene(); small_path(d)
    cases.append(('float32-path-in-bounds', d, 'Float32 trajectory segment'))
    d = buffer_scene(); small_surface(d)
    cases.append(('float32-potential-in-bounds', d, 'Float32 potential triangle'))
    d = buffer_scene(); small_path(d); small_surface(d)
    cases.append(('float32-combined-in-bounds', d, 'Float32 trajectory segment'))
    d = buffer_scene(); small_path(d, 999999, 1e-6)
    cases.append(('float32-path-far', d, 'Float32 trajectory segment'))
    d = buffer_scene()
    d['geometry'] = [dict(id='line-f32', shape='line', role='truncated_infinite_source',
                         center_m=[19999980,0,0], direction=[1,0,0], display_span_m=2e-5)]
    d['has_uniform_source'] = False
    cases.append(('float32-source-line', d, 'Float32 source line segment'))
    d = buffer_scene()
    d['potential']['points_m'] = [[[2.5,2.5,0],[2.5,7.5,0]],[[5,5,0],[7.5,7.5+2e-8,0]]]
    d['potential']['values'] = [1,2,3,4]
    cases.append(('float32-triangle-collinear', d, 'Float32 potential triangle'))
    return cases


def qualify_refusals(browser, base_url, manifest, root, output, errors):
    source = json.loads((root/manifest['scenes'][0]['file']).read_text())
    results = []
    def new_page(entries, payload):
        page = browser.new_page(viewport={'width':1280,'height':900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        modified = dict(manifest, scenes=entries)
        page.route('**/manifest.json', lambda route: route.fulfill(json=modified))
        page.route('**/refusal.json', lambda route: route.fulfill(body=payload, content_type='application/json'))
        return page
    def assert_refused(page, expected, count):
        page.wait_for_function('!!window.emfeeldPreviewError && !document.querySelector("#scene").disabled')
        message = page.evaluate('window.emfeeldPreviewError')
        assert expected in message, (expected, message)
        assert 'checksum' not in message.lower(), message
        state = page.evaluate('window.emfeeldPreview.inspect()')
        assert state['available'] is False and state['actor_count'] == 0, state
        assert state['construction_count'] == count, state
        assert state['snapshot'] is None and state['frame'] is None and state['source'] is None, state
        assert page.locator('#error').is_visible()
        for control in ['play','frame','reset','potential']:
            assert page.locator('#'+control).is_disabled(), control
        for readout in ['positions','time','range','provenance','notes']:
            assert page.locator('#'+readout).inner_text() == '', readout
        return message
    cases = refusal_cases(source)
    for name, snapshot, expected in cases:
        payload = (json.dumps(snapshot, allow_nan=False, separators=(',',':'))+'\n').encode()
        entry = dict(manifest['scenes'][0], file='refusal.json', sha256=hashlib.sha256(payload).hexdigest())
        page = new_page([entry], payload)
        try:
            page.goto(base_url, wait_until='networkidle')
            message = assert_refused(page, expected, 0)
            if name in ['potential-role','arrow-underflow','float32-path-in-bounds',
                        'float32-potential-in-bounds','float32-source-line','float32-triangle-collinear']:
                page.screenshot(path=str(output/(name+'-refused.png')))
            results.append({'case':name, 'error':message, 'construction_count':0, 'actor_count':0,
                            'payload_sha256':entry['sha256']})
        finally:
            page.close()
    # Real scene-change events must remove stale actors/readouts and allow recovery,
    # including when the very first scene was rejected before any construction.
    recoveries = []
    for name, snapshot, expected in cases:
        if name != 'potential-role' and not name.startswith('float32-'):
            continue
        payload = json.dumps(snapshot, allow_nan=False).encode()
        bad = dict(manifest['scenes'][0], file='refusal.json', sha256=hashlib.sha256(payload).hexdigest())
        for invalid_first in [False, True]:
            entries = [bad,manifest['scenes'][0]] if invalid_first else [manifest['scenes'][0],bad]
            page = new_page(entries, payload)
            try:
                page.goto(base_url, wait_until='networkidle')
                if not invalid_first:
                    page.wait_for_function('window.emfeeldPreview?.inspect().available && !document.querySelector("#scene").disabled')
                    # Reject while genuine replay is active, not just an idle scene.
                    page.click('#play')
                    page.wait_for_function('Number(document.querySelector("#frame").value)>0')
                    page.select_option('#scene', '1')
                assert_refused(page, expected, 0 if invalid_first else 1)
                page.select_option('#scene', '1' if invalid_first else '0')
                page.wait_for_function('window.emfeeldPreview?.inspect().available && !window.emfeeldPreviewError && !document.querySelector("#scene").disabled')
                state = page.evaluate('window.emfeeldPreview.inspect()')
                assert state['snapshot'] == source and state['actor_count'] > 0
                assert state['construction_count'] == (1 if invalid_first else 2)
                assert page.locator('#error').is_hidden() and page.locator('#play').is_enabled()
                page.click('#play')
                page.wait_for_function('Number(document.querySelector("#frame").value)>0')
                page.click('#play')
                recoveries.append({'case':name, 'invalid_first':invalid_first, 'recovered':True,
                                   'real_replay_advanced':True, 'payload_sha256':bad['sha256']})
            finally:
                page.close()
    return {'refusals':results, 'recovery':recoveries}


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
            page.wait_for_function('window.emfeeldPreview?.inspect().available || window.emfeeldPreviewError')
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
                assert not any(text in page.locator('#notes').inner_text() for text in ['Space:', 'Home:', 'Left / Right'])
                page.uncheck('#potential')
                assert page.evaluate('window.emfeeldPreview.inspect().potential_visible') is False
                page.check('#potential')
                assert page.evaluate('window.emfeeldPreview.inspect().potential_visible') is True
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
            refusal_report = qualify_refusals(browser, f'http://127.0.0.1:{server.server_port}',
                                               manifest, root, args.output, errors)
            assert not errors, errors
            browser.close()
        (args.output/'report.json').write_text(json.dumps({'scenes':result,'browser_errors':errors,
            'physics_in_browser':False,'independent_review':'not_evaluated', **refusal_report},indent=2)+'\n')
        print(json.dumps({'actual_chromium_webgl_scenes':len(result),'browser_errors':errors,
                          'refusal_cases':len(refusal_report['refusals']), 'recovery_cases':len(refusal_report['recovery'])}))
    finally:
        server.shutdown();server.server_close();thread.join()
    files = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in args.output.iterdir() if path.is_file()}
    (args.output/'integrity.json').write_text(json.dumps({'files':files},indent=2)+'\n')


if __name__ == '__main__':
    main()
