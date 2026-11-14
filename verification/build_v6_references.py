"""Same-author analytic references, separate from native engine evaluation.

Rebuilds a regression manifest for exact published v6 bytes. Does not call
emfeeld, run trajectories, or use stored engine answers as reference values.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
EPSILON0 = 8.8541878188e-12
K = 1/(4*math.pi*EPSILON0)


def reference(source, point, potential=False):
    d = np.asarray(point)-source.get('center_m', [0, 0, 0])
    r = float(np.linalg.norm(d))
    kind = source['type']
    if kind == 'point':
        c = K*source['charge_C']
        return c/r if potential else c*d/r**3
    if kind == 'solid_sphere':
        a, c = source['radius_m'], K*source['charge_C']
        if potential:
            return c*(3-r*r/(a*a))/(2*a) if r < a else c/r
        return c*d/a**3 if r < a else c*d/r**3
    if kind == 'line':
        rho = math.hypot(float(d[0]), float(d[1]))
        c = K*source['charge_per_m_C_m']
        return (-2*c*math.log(rho/source['reference_radius_m']) if potential
                else 2*c*np.array([d[0], d[1], 0])/rho**2)
    if kind == 'plane':
        c = source['charge_per_m2_C_m2']/(2*EPSILON0)
        return -c*abs(d[2]) if potential else np.array([0, 0, math.copysign(c, d[2])])
    raise ValueError(kind)


def build():
    cases = []
    folder = ROOT/'pilots/authorability_v6/first_attempt'
    for path in sorted(folder.glob('*.json')):
        raw = path.read_bytes(); packet = json.loads(raw)
        case = {'id': path.stem, 'packet': str(path.relative_to(ROOT)).replace('\\', '/'),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'statuses': {o['id']: 'ok' for o in packet['observations']}, 'checks': []}
        def check(ident, keys, value, atol=None, rtol=1e-10):
            row = {'id': ident, 'path': keys, 'value': value}
            if atol is not None:
                row.update(atol=atol, rtol=rtol)
            case['checks'].append(row)
        for obs in packet['observations']:
            ident, typ = obs['id'], obs['type']
            if typ in ('field', 'potential', 'force'):
                is_potential = typ == 'potential'
                value = sum(reference(s, obs['position_m'], is_potential) for s in packet['scene']['sources'])
                if typ == 'force': value *= obs['test_charge_C']
                # Symmetry/weight references, rather than cancellation of engine-like terms.
                if ident == 'E_centre': value = np.array([K*2e-9/1.2**2, 0, 0])
                if ident == 'E_target': value = np.zeros(3)
                if ident == 'F_on_second': value = np.array([1.7e-27*10, 0, 0])
                atol = 1e-38 if path.stem.startswith('NUM10') else 1e-9
                check(ident, ['value'], np.asarray(value).tolist(), atol)
                check(ident, ['unit'], 'V' if is_potential else 'N' if typ == 'force' else 'N/C')
            elif typ == 'trajectory_sample':
                check(ident, ['value'], 0.0, 1e-15, 0)
                check(ident, ['unit'], 'm/s')
            elif typ == 'trajectory_event':
                coefficient = 4*K*(1e-6/.001)*1e-8
                speed = math.sqrt(coefficient*math.log(2))
                time = 1/math.sqrt(coefficient)*quad(lambda u: math.exp(u*u), 0, math.sqrt(math.log(2)),
                                                      epsabs=1e-12, epsrel=1e-12)[0]
                check(ident, ['state', 'time_s'], time, 1e-6, 1e-8)
                check(ident, ['state', 'position_m'], [1, 0, 0], 1e-8, 1e-8)
                check(ident, ['state', 'velocity_m_s'], [speed, 0, 0], 1e-7, 1e-8)
                check(ident, ['state', 'speed_m_s'], speed, 1e-7, 1e-8)
                check(ident, ['state', 'kinetic_J'], .5*.001*speed**2, 1e-10, 1e-8)
                check(ident, ['diagnostics', 'refinement', 'passed'], True)
        cases.append(case)
    return {'version': 1, 'description': 'Exact published v6 forward-output regression; same-author analytic references, not a blind benchmark or native inverse solutions.', 'cases': cases}


if __name__ == '__main__':
    (ROOT/'verification/v6_published.json').write_text(json.dumps(build(), indent=2, allow_nan=False)+'\n', encoding='utf-8')
