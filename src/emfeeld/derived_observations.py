"""Sealed, post-run scalar ratios and same-time test-body separations.

No new physical equations, integrations, native observations, or visualization.
The exact-byte native model-run inventory is mandatory and is never modified.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import sys

from .model_revisions import RevisionError, decode, encode, identifier, put, sha256
from .model_runs import inspect_run

MAX_REQUESTS = 32


def _exact(row, required):
    if not isinstance(row, dict) or set(row) != set(required):
        raise ValueError(f'expected exactly {sorted(required)}')


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('expected finite JSON number, not bool or string')
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError('number outside finite float64 range') from exc
    if not math.isfinite(number):
        raise ValueError('nonfinite number')
    return number


def _validate(data):
    _exact(data, {'derived_version', 'id', 'source_run_sha256', 'observations'})
    if type(data['derived_version']) is not int or data['derived_version'] != 1:
        raise ValueError('only derived_version 1 supported')
    identifier(data['id'])
    if not isinstance(data['source_run_sha256'], str) or re.fullmatch('[0-9a-f]{64}',data['source_run_sha256']) is None:
        raise ValueError('source_run_sha256 must be the exact run.json SHA256')
    requests=data['observations']
    if not isinstance(requests,list) or not 1 <= len(requests) <= MAX_REQUESTS:
        raise ValueError('1..32 named requests required')
    seen=set()
    for row in requests:
        if not isinstance(row,dict):raise ValueError('request must be object')
        typ=row.get('type')
        if typ=='ratio':
            _exact(row, {'id','type','numerator','denominator'})
            for key in ('numerator','denominator'):
                _exact(row[key],{'id','part'})
                identifier(row[key]['id'])
                if row[key]['part'] not in ('value','magnitude'):
                    raise ValueError('part must be value or magnitude')
        elif typ=='separation':
            _exact(row, {'id','type','left_id','right_id'})
            identifier(row['left_id']);identifier(row['right_id'])
            if row['left_id']==row['right_id']:
                raise ValueError('separation requires two different observation IDs')
        else:raise ValueError(f'unsupported derived type {typ!r}')
        identifier(row['id'])
        if row['id'] in seen:raise ValueError('duplicate derived observation ID')
        seen.add(row['id'])


def _outcome(row, code, *, reason=None):
    return {'id':row['id'],'type':row['type'],'status':'unavailable',
            'code':code,'reason':reason or code,'value':None,'unit':None,
            'error_bound':None,'method':'postrun_named_observations'}


def _eligible_scalar(row, part):
    typ=row.get('type')
    if typ in ('field','force') and part=='magnitude':
        val=row.get('magnitude')
    elif typ=='potential_difference' and part=='value':
        val=row.get('value')
    elif typ=='trajectory_sample' and part=='value' and row.get('quantity') in ('speed','kinetic_energy'):
        val=row.get('value')
    else:raise ValueError('unsupported_scalar_kind')
    if row.get('status') != 'ok' or row.get('check',{}).get('passed') is False:
        raise ValueError('operand_not_verified')
    val=_number(val)
    unit=row.get('unit')
    if not isinstance(unit,str) or not unit:raise ValueError('missing_unit')
    return val,unit


def _ratio(req, indexed):
    a,b=(indexed.get(req[name]['id']) for name in ('numerator','denominator'))
    if a is None or b is None:return _outcome(req,'unknown_operand')
    try:
        av,au=_eligible_scalar(a,req['numerator']['part'])
        bv,bu=_eligible_scalar(b,req['denominator']['part'])
    except (ValueError,TypeError,AttributeError) as exc:
        return _outcome(req,'operand_unavailable',reason=str(exc))
    if au != bu:return _outcome(req,'incompatible_units')
    ta=a.get('type')=='trajectory_sample';tb=b.get('type')=='trajectory_sample'
    if ta != tb:return _outcome(req,'incompatible_time_context')
    if ta and (type(a.get('sample_index')) is not int or type(b.get('sample_index')) is not int
               or type(a.get('time_s')) not in (int, float) or type(b.get('time_s')) not in (int, float)
               or not math.isfinite(a['time_s']) or not math.isfinite(b['time_s'])):
        return _outcome(req,'invalid_saved_time')
    if ta and (a['time_s']!=b['time_s'] or a['sample_index']!=b['sample_index']):
        return _outcome(req,'different_saved_times')
    if bv==0.:return _outcome(req,'zero_denominator')
    try:
        value=av/bv
    except (OverflowError,ZeroDivisionError):
        return _outcome(req,'numeric_range')
    if not math.isfinite(value):return _outcome(req,'numeric_range')
    return {'id':req['id'],'type':'ratio','status':'ok','code':None,'value':value,'unit':'1',
            'method':'postrun_scalar_ratio','error_bound':None,
            'operands':[{'observation_id':req['numerator']['id'],'part':req['numerator']['part'],'value':av,'unit':au},
                        {'observation_id':req['denominator']['id'],'part':req['denominator']['part'],'value':bv,'unit':bu}],
            'time_s':a['time_s'] if ta else None,
            'meaning':'dimensionless value of selected scalars; existing native error bounds not upgraded'}


def _position(row):
    if row.get('status')!='ok' or row.get('check',{}).get('passed') is False:
        raise ValueError('operand_not_verified')
    if row.get('type')!='trajectory_sample' or row.get('quantity')!='position' or row.get('unit')!='m':
        raise ValueError('requires saved position in metres')
    coords=row.get('value')
    if not isinstance(coords,list) or len(coords)!=3:raise ValueError('expected 3-vector')
    return tuple(_number(x) for x in coords)


def _separation(req,indexed):
    a=indexed.get(req['left_id']);b=indexed.get(req['right_id'])
    if a is None or b is None:return _outcome(req,'unknown_operand')
    try:
        x,y=_position(a),_position(b)
    except (ValueError,TypeError,AttributeError) as exc:
        return _outcome(req,'operand_unavailable',reason=str(exc))
    if type(a.get('particle_index')) is not int or type(b.get('particle_index')) is not int:
        return _outcome(req,'missing_particle_identity')
    if a['particle_index']==b['particle_index']:
        return _outcome(req,'same_particle')
    if (type(a.get('sample_index')) is not int or type(b.get('sample_index')) is not int
        or type(a.get('time_s')) not in (int,float) or type(b.get('time_s')) not in (int,float)
        or not math.isfinite(a['time_s']) or not math.isfinite(b['time_s'])):
        return _outcome(req,'invalid_saved_time')
    if a['time_s']!=b['time_s'] or a['sample_index']!=b['sample_index']:
        return _outcome(req,'different_saved_times')
    try:
        distance=math.dist(x,y)
    except OverflowError:return _outcome(req,'numeric_range')
    if not math.isfinite(distance):return _outcome(req,'numeric_range')
    return {'id':req['id'],'type':'separation','status':'ok','code':None,'value':distance,
            'unit':'m','method':'postrun_euclidean_distance','error_bound':None,
            'time_s':a['time_s'],'sample_index':a['sample_index'],
            'operands':[{'observation_id':req['left_id'],'particle_index':a['particle_index'],'position_m':list(x)},
                        {'observation_id':req['right_id'],'particle_index':b['particle_index'],'position_m':list(y)}],
            'meaning':'separation of independently modeled test bodies at identical saved time; no interparticle force'}


def _inventory(output):
    return {p.relative_to(output).as_posix():sha256(p.read_bytes())
            for p in sorted(output.rglob('*')) if p.is_file() and p!=output/'integrity.json'}


def derive(request_path, *, using, output):
    request_path,using,output=map(Path,(request_path,using,output))
    if output.exists() or output.is_symlink():raise FileExistsError('output already exists')
    if output.resolve().is_relative_to(using.resolve()):
        raise ValueError('output cannot be inside native run')
    raw=request_path.read_bytes();spec=decode(raw);_validate(spec)
    saved=using/'run.json'
    if sha256(saved.read_bytes()) != spec['source_run_sha256']:
        raise RevisionError('wrong_run','run.json SHA256 differs from pinned source-run identity')
    run,rev,summary,report=inspect_run(using)  # checks exact run inventory and binding
    if report is None or not summary.get('execution_complete') or not report.get('results'):
        raise RevisionError('incomplete_run','a completed, sealed source run is required')
    results=report['results'];ids=[row['id'] for row in results]
    if len(ids)!=len(set(ids)):raise RevisionError('invalid_native_report','duplicate native observation identity')
    indexed={row['id']:row for row in results}
    derived=[]
    for req in spec['observations']:
        derived.append(_ratio(req,indexed) if req['type']=='ratio' else _separation(req,indexed))
    status='complete' if all(row['status']=='ok' for row in derived) else 'partial'
    output.mkdir(parents=True,exist_ok=False)
    put(output/'request.json',raw)
    result={'derived_version':1,'id':spec['id'],'status':status,'request_sha256':sha256(raw),'source_run_sha256':spec['source_run_sha256'],
            'source_run_id':run['run_id'],'source_reference':run['reference'],
            'native_packet_sha256':sha256((using/'native/packet.json').read_bytes()),
            'observations':derived,'qualification':'post-run arithmetic, not new solver or independent accuracy certification'}
    put(output/'result.json',encode(result))
    put(output/'integrity.json',encode({'files':_inventory(output)}))
    return result


def inspect(output,*,using):
    output,using=Path(output),Path(using)
    inventory=decode((output/'integrity.json').read_bytes())
    if inventory.get('files')!=_inventory(output):
        raise RevisionError('derived_integrity','derived output changed or has missing/extra files')
    spec=decode((output/'request.json').read_bytes());_validate(spec)
    result=decode((output/'result.json').read_bytes())
    if (result.get('request_sha256')!=sha256((output/'request.json').read_bytes())
        or result['source_run_sha256']!=spec['source_run_sha256'] or result['id']!=spec['id']):
        raise RevisionError('derived_integrity','captured source binding differs')
    if sha256((using/'run.json').read_bytes())!=spec['source_run_sha256']:
        raise RevisionError('wrong_run','source run differs from captured pin')
    run,rev,summary,report=inspect_run(using)
    if result['source_reference']!=run['reference'] or result['source_run_id']!=run['run_id']:
        raise RevisionError('wrong_run','native run identity mismatch')
    if result['native_packet_sha256']!=sha256((using/'native/packet.json').read_bytes()):
        raise RevisionError('wrong_run','native packet mismatch')
    # Recheck deterministic post-processing without re-evaluating the physical model.
    indexed={row['id']:row for row in report['results']}
    expected=[_ratio(r,indexed) if r['type']=='ratio' else _separation(r,indexed) for r in spec['observations']]
    if expected != result['observations']:
        raise RevisionError('derived_integrity','derived values do not follow pinned native observations')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('run','inspect'))
    p.add_argument('request_or_output');p.add_argument('--using',required=True)
    p.add_argument('--output')
    a=p.parse_args(argv)
    try:
        if a.command=='run':
            if not a.output:raise ValueError('run requires --output')
            result=derive(a.request_or_output,using=a.using,output=a.output)
        else:
            if a.output:raise ValueError('inspect does not accept --output')
            result=inspect(a.request_or_output,using=a.using)
        print(encode(result).decode(),end='')
        return 0 if result['status']=='complete' else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'emfeeld derived: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
