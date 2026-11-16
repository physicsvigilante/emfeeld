"""Strict, sealed cross-revision differences of existing native observations.

No source-field evaluation, integration, implicit observation pairing, model
revision, interpolation, or trusted interpretation of unkeyed hashes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import math
from pathlib import Path
import re
import sys

import numpy as np

from .model_revisions import RevisionError, decode, encode, identifier, put, sha256
from .model_runs import inspect_run

MAX_PAIRS = 16
TYPES = ('field_vector', 'field_magnitude', 'potential_difference',
         'particle_position', 'particle_velocity')
QUALIFICATION = 'read-only post-run arithmetic; native accuracy inherited, not independently certified'
MEANING = ('Signed right-minus-left differences between separately simulated static '
           'physical scenarios; not a time-dependent transition or physical work')


def _exact(row, required):
    if not isinstance(row, dict) or set(row) != set(required):
        raise ValueError(f'exactly {sorted(required)} keys required')


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('expected finite SI number, not bool/string')
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError('value outside finite float64 range') from exc
    if not math.isfinite(value):
        raise ValueError('number must be finite')
    return value


def _vector(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('expected explicit three-component vector')
    return [_number(x) for x in value]


def _validate(spec):
    _exact(spec, {'comparison_version','id','left_run_sha256','right_run_sha256','pairs'})
    if type(spec['comparison_version']) is not int or spec['comparison_version'] != 1:
        raise ValueError('only comparison_version 1 is supported')
    identifier(spec['id'])
    for key in ('left_run_sha256','right_run_sha256'):
        if not isinstance(spec[key], str) or re.fullmatch('[0-9a-f]{64}', spec[key]) is None:
            raise ValueError(key+' must be exact lowercase 64-hex SHA256')
    pairs = spec['pairs']
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= MAX_PAIRS:
        raise ValueError('1..16 named comparison pairs required')
    seen = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError('comparison pair must be an object')
        typ = pair.get('type')
        if not isinstance(typ, str) or typ not in TYPES:
            raise ValueError('unsupported comparison type')
        expected = {'id', 'type', 'left_observation_id', 'right_observation_id'}
        if typ.startswith('particle_'):
            expected.add('particle_id')
        _exact(pair, expected)
        for key in expected - {'type'}:
            identifier(pair[key])
        if pair['id'] in seen:
            raise ValueError('duplicate comparison pair ID')
        seen.add(pair['id'])


def _run_record(folder, expected_sha):
    """Verify source run, extra native metadata and captured named identity.

    inspect_run is the authoritative native input-to-result binding validator.
    Additional checks here do NOT reevaluate the physical source equations.
    """
    folder = Path(folder)
    if sha256((folder/'run.json').read_bytes()) != expected_sha:
        raise RevisionError('wrong_run', 'source run.json SHA does not match request pin')
    run, revision, summary, report = inspect_run(folder)
    if (report is None or summary.get('status') != 'complete'
            or summary.get('execution_complete') is not True
            or summary.get('numerical_checks_passed') is not True
            or summary.get('unfulfilled_requests') != {}):
        raise RevisionError('incomplete_run', 'comparison requires complete, numerically checked sealed native runs')
    packet = decode((folder/'native/packet.json').read_bytes())
    mapping = decode((folder/'mapping.json').read_bytes())
    investigation = decode((folder/'investigation.json').read_bytes())
    analysis = decode((folder/'analysis.json').read_bytes())
    rows = report.get('results')
    requests = packet.get('observations')
    authored = investigation.get('observations')
    if (report.get('status') != 'ok' or not isinstance(rows,list)
            or not isinstance(requests,list) or not isinstance(authored,list)
            or not rows or len(rows)!=len(requests) or len(rows)!=len(authored)):
        raise RevisionError('invalid_native_run', 'native report/request collection is inconsistent')
    ids = [r.get('id') for r in rows if isinstance(r,dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise RevisionError('invalid_native_run', 'native result IDs must be unique and complete')
    if not isinstance(report.get('versions'),dict) or not isinstance(report.get('constants_SI'),dict):
        raise RevisionError('invalid_native_run', 'native runtime and physical-constant evidence required')
    if set(report['versions']) != {'python','numpy','scipy'} or set(report['constants_SI']) != {'G','epsilon_0'}:
        raise RevisionError('invalid_native_run', 'native runtime/physical-constant metadata is incomplete')
    if not isinstance(run.get('implementation_sha256'),dict) or not run['implementation_sha256']:
        raise RevisionError('invalid_native_run', 'recorded source implementation identity required')
    counts=report.get('counts')
    if (not isinstance(counts,dict) or counts.get('requests') != len(rows)
            or counts.get('evaluated') != len(rows)
            or summary.get('request_statuses') != {r['id']:'ok' for r in rows}):
        raise RevisionError('invalid_native_run', 'native evaluation counts and completion claims disagree')
    if (report.get('kind') != revision['kind'] or packet['scene']['kind'] != revision['kind']
            or mapping.get('physical_time_origin_s') != 0.
            or revision['time_origin_s'] != 0.):
        raise RevisionError('invalid_native_run', 'kind or physical-time/frame receipt mismatch')
    if not isinstance(mapping.get('particles'),dict) or mapping['particles'] != {x:i for i,x in enumerate(revision['particle_order'])}:
        raise RevisionError('invalid_native_run', 'stable particle-to-index mapping invalid')
    if (not isinstance(run.get('root_reference'),dict)
            or run['reference']['model_id'] != run['root_reference'].get('model_id')
            or run['reference']['model_id'] != revision['model_id']):
        raise RevisionError('invalid_native_run', 'model root/revision identity mismatch')
    if not isinstance(analysis,dict) or analysis.get('mode') not in ('static','trajectory'):
        raise RevisionError('invalid_native_run', 'analysis mode missing')

    # _capture writes a nested native inventory for all trajectory runs and
    # particle-free static runs. Static probes with present particles are
    # request-only and have no nested trajectory archive.
    native = folder/'native'
    nested = native/'integrity.json'
    if nested.is_file():
        saved = decode(nested.read_bytes())
        actual = {p.name:sha256(p.read_bytes()) for p in native.iterdir()
                  if p.is_file() and p.name!='integrity.json'}
        if (saved.get('files') != actual
                or saved.get('scene_sha256') != report.get('scene_sha256')):
            raise RevisionError('invalid_native_run', 'nested native inventory or scene SHA mismatch')
    elif analysis['mode'] == 'trajectory' or not revision['particle_order']:
        raise RevisionError('invalid_native_run', 'captured run lacks required native inventory')

    for req, row, original in zip(requests, rows, authored):
        if not isinstance(row,dict) or not isinstance(req,dict) or not isinstance(original,dict):
            raise RevisionError('invalid_native_run', 'malformed native result/request')
        check=row.get('check',{})
        if (not isinstance(check,dict)
                or req.get('id') != row.get('id') or row.get('id') != original.get('id')
                or row.get('type') != req.get('type') or row.get('type') != original.get('type')
                or row.get('kind') != revision['kind'] or row.get('status') != 'ok'
                or check.get('passed') is False):
            raise RevisionError('invalid_native_run', 'native result identity/status contradicts request or completion')
        typ = row['type']
        if typ == 'trajectory_sample':
            ident = original.get('particle_id')
            if (ident not in mapping['particles']
                    or row.get('quantity') != req.get('quantity')
                    or row.get('particle_index') != req.get('particle_index')
                    or mapping['particles'][ident] != req['particle_index']
                    or row.get('selection') != {k:req[k] for k in ('sample_index','time_s','time_selection','max_time_error_s') if k in req}):
                raise RevisionError('invalid_native_run', 'trajectory sample/selection/physical ID binding contradicts native request')
        elif typ == 'field':
            if row.get('position_m') != req.get('position_m'):
                raise RevisionError('invalid_native_run', 'field result location changed from the authored request')
        elif typ == 'potential_difference':
            if (row.get('from_m') != req.get('from_m') or row.get('to_m') != req.get('to_m')
                    or row.get('convention') != 'potential(to_m) - potential(from_m)'):
                raise RevisionError('invalid_native_run', 'potential-difference endpoints or sign convention changed')
        # Other native request types are still validated by inspect_run, but
        # are outside the V1 comparison operand surface.
    return {
        'folder':folder,'run':run,'revision':revision,'summary':summary,
        'report':report,'packet':packet,'mapping':mapping,'investigation':investigation,
        'analysis':analysis,'results':{r['id']:r for r in rows},
        'requests':{r['id']:r for r in requests},
        'authored':{r['id']:r for r in authored},
        'metadata':{
            'source_run_sha256':expected_sha,'run_id':run['run_id'],
            'reference':run['reference'],'root_reference':run['root_reference'],
            'native_packet_sha256':sha256((folder/'native/packet.json').read_bytes()),
            'implementation_sha256':run['implementation_sha256'],
            'versions':report['versions'],'constants_SI':report['constants_SI'],
        },
    }


def _compatible_runs(left, right):
    if (left['run']['root_reference'] != right['run']['root_reference']
            or left['revision']['model_id'] != right['revision']['model_id']):
        raise RevisionError('incompatible_models', 'two runs must share the same exact model root')
    if left['run']['reference'] == right['run']['reference']:
        raise RevisionError('incompatible_revisions', 'cross-scenario comparison needs two different revisions')
    if left['revision']['kind'] != right['revision']['kind']:
        raise RevisionError('incompatible_physics', 'both runs must use same physical domain')
    for field,code in [('implementation_sha256','incompatible_implementation'),
                       ('versions','incompatible_runtime'),('constants_SI','incompatible_constants')]:
        if left['metadata'][field] != right['metadata'][field]:
            raise RevisionError(code, 'two runs have different saved '+field+' identities')


def _unavailable(pair, code, left, right, reason=None):
    return {**_row_head(pair, left, right),
            'status':'unavailable','code':code,'value':None,'unit':None,
            'error_bound':None,'method':'signed_right_minus_left',
            'reason':reason or code,'context':None}


def _row_head(pair, left, right):
    """Keep the *actual* source-native rows and authored requests per side."""
    ids = {'left':pair['left_observation_id'], 'right':pair['right_observation_id']}
    refs = {}
    for name, source in (('left',left),('right',right)):
        ident = ids[name]
        refs[name] = {
            'observation_id':ident,
            'request':deepcopy(source['authored'].get(ident)),
            'native_request':deepcopy(source['requests'].get(ident)),
            'native_result':deepcopy(source['results'].get(ident)),
        }
    return {'id':pair['id'],'type':pair['type'],'left_observation_id':ids['left'],
            'right_observation_id':ids['right'],'particle_id':pair.get('particle_id'),
            'operands':refs}


def _sample(source, ident):
    row = source['results'][ident]
    index = row.get('sample_index')
    if type(index) is not int or index < 0:
        raise ValueError('invalid sample_index')
    recorded = _number(row.get('time_s'))
    native = source['folder']/'native/trajectories.npz'
    if not native.is_file():
        raise RevisionError('invalid_native_run', 'complete trajectory sample missing native saved arrays')
    idx = row['particle_index']
    if type(idx) is not int or idx < 0:
        raise RevisionError('invalid_native_run', 'recorded particle index is not valid')
    name = 'position_m' if row['quantity']=='position' else 'velocity_m_s'
    try:
        with np.load(native,allow_pickle=False) as archive:
            times = archive[f'p{idx}_time_s']
            values = archive[f'p{idx}_{name}']
            if (times.ndim!=1 or values.shape!=(len(times),3)
                    or not 0 <= index < len(times)):
                raise RevisionError('invalid_native_run', 'saved sample index/shape mismatches archived trajectory')
            t = _number(float(times[index]))
            actual = [_number(float(x)) for x in values[index]]
    except (OSError,ValueError,IndexError,KeyError,TypeError,OverflowError) as exc:
        raise RevisionError('invalid_native_run', 'malformed or missing native saved trajectory') from exc
    if recorded != t or row['value'] != actual:
        raise RevisionError('invalid_native_run', 'recorded saved sample contradicts original NPZ time/state')
    return index, recorded


def _pair(pair, left, right):
    heading = _row_head(pair, left, right)
    a_id,b_id=pair['left_observation_id'],pair['right_observation_id']
    if a_id not in left['results'] or b_id not in right['results']:
        return _unavailable(pair,'unknown_operand',left,right)
    a,b=left['results'][a_id],right['results'][b_id]
    typ=pair['type']
    observed_type='trajectory_sample' if typ.startswith('particle_') else 'potential_difference' if typ=='potential_difference' else 'field'
    if a['type']!=observed_type or b['type']!=observed_type:
        return _unavailable(pair,'incompatible_observation_type',left,right)
    if a.get('status')!='ok' or b.get('status')!='ok':
        return _unavailable(pair,'operand_unavailable',left,right)
    # The global complete-run preflight has already established all check
    # metadata is structured and no authored numerical check failed.
    unit={'field_vector':'N/C' if left['revision']['kind']=='electric' else 'm/s^2',
          'field_magnitude':'N/C' if left['revision']['kind']=='electric' else 'm/s^2',
          'potential_difference':'V' if left['revision']['kind']=='electric' else 'J/kg',
          'particle_position':'m','particle_velocity':'m/s'}[typ]
    if a.get('unit')!=unit or b.get('unit')!=unit:
        return _unavailable(pair,'incompatible_units',left,right)
    context={}
    try:
        if typ.startswith('field_'):
            x,y=_vector(left['requests'][a_id]['position_m']),_vector(right['requests'][b_id]['position_m'])
            if x != y:
                return _unavailable(pair,'different_world_point',left,right)
            context={'position_m':x}
            va,vb=_vector(a.get('value')),_vector(b.get('value'))
            if typ=='field_magnitude':
                ma,mb=_number(a.get('magnitude')),_number(b.get('magnitude'))
                for vector,magnitude in ((va,ma),(vb,mb)):
                    wanted=math.hypot(*vector)
                    if not math.isfinite(wanted) or magnitude < 0 or not math.isclose(wanted,magnitude,rel_tol=1e-12,abs_tol=0):
                        return _unavailable(pair,'numeric_range',left,right,reason='field vector and saved magnitude disagree')
                va,vb=ma,mb
        elif typ=='potential_difference':
            a_req,b_req=left['requests'][a_id],right['requests'][b_id]
            from_a,from_b=_vector(a_req['from_m']),_vector(b_req['from_m'])
            to_a,to_b=_vector(a_req['to_m']),_vector(b_req['to_m'])
            if from_a != from_b or to_a != to_b:
                return _unavailable(pair,'endpoints_mismatch',left,right)
            context={'from_m':from_a,'to_m':to_a,'convention':'potential(to_m) - potential(from_m)'}
            va,vb=_number(a.get('value')),_number(b.get('value'))
        else:
            physical_id=pair['particle_id']
            authored_a=left['authored'][a_id]
            authored_b=right['authored'][b_id]
            if (authored_a.get('particle_id')!=physical_id or authored_b.get('particle_id')!=physical_id
                    or physical_id not in left['mapping']['particles'] or physical_id not in right['mapping']['particles']):
                return _unavailable(pair,'particle_identity_mismatch',left,right)
            desired='position' if typ=='particle_position' else 'velocity'
            if a.get('quantity')!=desired or b.get('quantity')!=desired:
                return _unavailable(pair,'incompatible_observation_type',left,right)
            if (a.get('particle_index')!=left['mapping']['particles'][physical_id]
                    or b.get('particle_index')!=right['mapping']['particles'][physical_id]):
                raise RevisionError('invalid_native_run', 'saved index contradicts stable physical ID mapping')
            if (type(a.get('sample_index')) is not int or type(b.get('sample_index')) is not int
                    or a['sample_index'] < 0 or b['sample_index'] < 0):
                return _unavailable(pair,'invalid_saved_sample',left,right)
            try:
                _number(a.get('time_s'));_number(b.get('time_s'))
            except ValueError:
                return _unavailable(pair,'invalid_saved_sample',left,right)
            ia,ta=_sample(left,a_id);ib,tb=_sample(right,b_id)
            if ta!=tb:
                return _unavailable(pair,'different_saved_time',left,right)
            context={'particle_id':physical_id, 'time_s':ta,
                     'left_sample_index':ia,'right_sample_index':ib}
            va,vb=_vector(a.get('value')),_vector(b.get('value'))
        if isinstance(va,list):
            value=[y-x for x,y in zip(va,vb)]
            if not all(math.isfinite(x) for x in value):
                raise ValueError('nonfinite vector difference')
        else:
            value=vb-va
            if not math.isfinite(value):
                raise ValueError('nonfinite scalar difference')
    except RevisionError:
        # Tampered/sealed-native contradictions are hard source failures; do
        # not disguise them as a mere unavailable numerical pair.
        raise
    except (ValueError,TypeError,OverflowError) as exc:
        return _unavailable(pair,'numeric_range',left,right,reason=str(exc))
    return {**heading,'status':'ok','code':None,'value':value,'unit':unit,
            'error_bound':None,'method':'signed_right_minus_left',
            'reason':None,'context':context}


def _build(spec,raw,left,right):
    comparisons=[_pair(pair,left,right) for pair in spec['pairs']]
    return {'comparison_version':1,'id':spec['id'],
            'status':'complete' if all(c['status']=='ok' for c in comparisons) else 'partial',
            'request_sha256':sha256(raw),
            'left':deepcopy(left['metadata']),'right':deepcopy(right['metadata']),
            'comparisons':comparisons,'meaning':MEANING,'qualification':QUALIFICATION}


def _sources(left_path,right_path,spec):
    left=_run_record(left_path,spec['left_run_sha256'])
    right=_run_record(right_path,spec['right_run_sha256'])
    _compatible_runs(left,right)
    return left,right


def _inventory(folder):
    return {p.relative_to(folder).as_posix():sha256(p.read_bytes())
            for p in sorted(folder.rglob('*')) if p.is_file() and p!=folder/'integrity.json'}


def compare(request_path,*,left,right,output):
    request_path,left,right,output=map(Path,(request_path,left,right,output))
    if output.exists() or output.is_symlink():
        raise FileExistsError('comparison output must be a fresh directory')
    for protected in (left,right):
        if output.resolve().is_relative_to(protected.resolve()):
            raise ValueError('comparison output must stay outside either source run')
    raw=request_path.read_bytes()
    spec=decode(raw)
    _validate(spec)
    a,b=_sources(left,right,spec)
    # All compatibility decisions precede output directory creation.
    output.mkdir(parents=True,exist_ok=False)
    put(output/'request.json',raw)
    put(output/'started.json',encode({'comparison_version':1,'id':spec['id'],
                                     'status':'pending','request_sha256':sha256(raw)}))
    result=_build(spec,raw,a,b)
    put(output/'result.json',encode(result))
    put(output/'integrity.json',encode({'files':_inventory(output)}))
    return result


def inspect(output,*,left,right):
    output,left,right=map(Path,(output,left,right))
    saved=decode((output/'integrity.json').read_bytes())
    if saved.get('files')!=_inventory(output):
        raise RevisionError('comparison_integrity','sealed comparison output changed')
    raw=(output/'request.json').read_bytes()
    spec=decode(raw);_validate(spec)
    pending=decode((output/'started.json').read_bytes())
    if pending != {'comparison_version':1,'id':spec['id'],
                   'status':'pending','request_sha256':sha256(raw)}:
        raise RevisionError('comparison_integrity','started record cannot assert completed evidence')
    a,b=_sources(left,right,spec)
    expected=_build(spec,raw,a,b)
    saved_result=decode((output/'result.json').read_bytes())
    if saved_result != expected:
        raise RevisionError('comparison_integrity','saved results/aggregate status do not follow pinned native observations')
    return saved_result


def main(argv=None):
    # Frozen public CLI supports SPEC.json directly; 'run' is an optional
    # explicit alias consistent with the existing derived-observations command.
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ('run','inspect'):
        argv.insert(0,'run')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run','inspect'))
    parser.add_argument('spec_or_output')
    parser.add_argument('--left',required=True)
    parser.add_argument('--right',required=True)
    parser.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        if args.command=='run':
            if not args.output:
                raise ValueError('run requires --output')
            result=compare(args.spec_or_output,left=args.left,right=args.right,output=args.output)
        else:
            if args.output:
                raise ValueError('inspect does not accept --output')
            result=inspect(args.spec_or_output,left=args.left,right=args.right)
        print(encode(result).decode(),end='')
        return 0 if result['status']=='complete' else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('emfeeld cross-scenario comparison: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
