"""Bounded V3 sibling scenarios with fresh native runs and sealed comparisons.

Orchestration only: physical identity, source admission, numerical checks,
potential conventions and comparison semantics belong to existing modules.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

from . import model_runs, scenario_comparisons
from .atomic_revisions import _OPERATIONS
from .model_cli import _settings
from .observations import packet_from_dict
from .scene import strict_keys
from .model_revisions import (ModelStore, RevisionError, check_reference, decode,
                              encode, exact_keys, identifier, put, sha256)

MIN_MEMBERS = 2
MAX_MEMBERS = 4
QUALIFICATION = ('native revision, run and sealed comparison qualification; '
                 'not independent physics certification or classroom evaluation')
MEANING = ('Independent prescribed-source model alternatives; comparing saved '
           'measurements does not simulate a physical transition or its work.')


def _inventory(output):
    return {p.relative_to(output).as_posix(): sha256(p.read_bytes())
            for p in sorted(output.rglob('*'))
            if p.is_file() and p != output/'integrity.json'}


def _member_dir(output, index):
    return output / f'member-{index:02d}'


def _run_id(ensemble, member=None):
    return f'ensemble-{ensemble}-baseline' if member is None else f'ensemble-{ensemble}-{member}'



def _finite_tree(value, path='ensemble'):
    """Reject JSON exponent overflow before any output or revision is created.

    Shared decode excludes NaN/Infinity *tokens* but JSON 1e400 is a legal
    numeric literal parsed by Python to float infinity. Do not weaken decode
    for old APIs; guard every nested numeric operand at this new boundary.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(item, f'{path}.{key}')
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _finite_tree(item, f'{path}[{i}]')
    elif type(value) in (int, float):
        try:
            valid = math.isfinite(float(value))
        except (ValueError, OverflowError):
            valid = False
        if not valid:
            raise ValueError(f'{path}: nonfinite or non-float64 JSON numeric value')


def _native_grammar(member, kind):
    """Pure native V1 schema preflight, independent of sibling physics.

    Use the existing presentation and observation validators on a temporary
    schema-only, non-integrated uniform scene. This validates complete input
    shapes, keys, units and selectors while deliberately *not* checking
    whether a particle is present in this member's eventual physical scene.
    Missing/removed named particle and stale presentation mappings must
    retain their honest per-member native rejection semantics.
    """
    investigation = member['investigation']
    analysis = member['analysis']
    presentation = member['presentation']
    exact_keys(investigation, ('investigation_version', 'id', 'model_id', 'observations'))
    exact_keys(analysis, ('analysis_version', 'id', 'mode'),
               ('duration_s', 'samples', 'checks'))
    exact_keys(presentation, ('presentation_version', 'id', 'bounds_m'),
               ('replay_seconds', 'camera', 'entity_order'))
    if analysis['mode'] == 'static':
        exact_keys(analysis, ('analysis_version', 'id', 'mode'))
    elif analysis['mode'] == 'trajectory':
        exact_keys(analysis, ('analysis_version', 'id', 'mode',
                              'duration_s', 'samples', 'checks'))
        exact_keys(analysis['checks'], ('position_atol_m', 'velocity_atol_m_s',
                                        'rtol', 'max_normalized_energy_drift'))
        for key, value in analysis['checks'].items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'analysis.checks.{key}: strictly positive finite number required')
    else:
        raise RevisionError('unsupported_analysis', 'unsupported native analysis mode')

    # A presentation's entity_order describes a *future* sibling. Validate
    # names/shapes but defer equality with the accepted child entity set.
    order = presentation.get('entity_order', [])
    if not isinstance(order, list):
        raise ValueError('presentation.entity_order must be an array')
    for ident in order:
        identifier(ident)
    model_runs._presentation(presentation, {'entities': {k: {} for k in order}})

    observations = investigation['observations']
    if not isinstance(observations, list) or not observations:
        raise ValueError('investigation observations must be a nonempty array')
    has_motion = any(isinstance(row, dict) and
                     row.get('type') in ('trajectory_sample', 'trajectory_event')
                     for row in observations)
    # Native lower() rejects a motion request in static mode before attempting
    # any physical calculation. Enforce that same cross-field V1 grammar here,
    # *before* creating the ensemble or reserving either sibling revision.
    # The dummy packet parser validates each request's shape but cannot enforce
    # the investigation-vs-analysis relationship on its own.
    if has_motion and analysis['mode'] != 'trajectory':
        raise RevisionError('unsupported_analysis',
                            'trajectory requests require a trajectory analysis')
    lifted = []
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError('observation must be an object')
        entry = dict(row)
        if 'particle_index' in entry:
            raise RevisionError('positional_reference', 'observation must name physical particle_id')
        if entry.get('type') in ('trajectory_sample', 'trajectory_event'):
            identifier(entry.pop('particle_id', None))
            entry['particle_index'] = 0  # syntax-only placeholder, never a physical binding
        lifted.append(entry)

    # A native observation packet parser owns the exact V1 grammar, including
    # nested expectation/event selector schemas. No dynamics are executed.
    field_key = 'field_N_C' if kind == 'electric' else 'field_m_s2'
    dummy_particle = {'mass_kg': 1., 'charge_C': 1. if kind == 'electric' else 0.,
                      'position_m': [0., 0., 0.], 'velocity_m_s': [0., 0., 0.]}
    dummy_scene = {'schema_version': 1, 'title': 'Schema-only ensemble validation',
                   'kind': kind, 'sources': [{'type': 'uniform', field_key: [0.,0.,0.]}],
                   'particles': [dummy_particle] if has_motion else [],
                   'duration_s': analysis.get('duration_s', 1.),
                   'samples': analysis.get('samples', 2),
                   'bounds_m': presentation['bounds_m']}
    packet_from_dict({'observation_schema_version': 1,
                      'scene': dummy_scene, 'observations': lifted})


def _validate_member(row, parent, kind, names, proposals, revisions, added):
    exact_keys(row, ('id','proposal','investigation','analysis','presentation','pairs'))
    name=identifier(row['id'])
    if len(name)>25:
        raise ValueError('member id must be at most 25 characters')
    if name in names:
        raise RevisionError('duplicate_identity','ensemble member ids must be unique')
    names.add(name)
    proposal=row['proposal']
    exact_keys(proposal, ('proposal_version','proposal_id','revision_id','parent',
                          'category','scenario_intent','changes'))
    if type(proposal['proposal_version']) is not int or proposal['proposal_version']!=3:
        raise ValueError('ensemble members must use exact V3 atomic revisions')
    if proposal['category']!='atomic_change' or proposal['parent']!=parent:
        raise RevisionError('stale_parent','each atomic member must use the same exact pinned parent')
    prop_id=identifier(proposal['proposal_id'])
    rev_id=identifier(proposal['revision_id'])
    if prop_id in proposals or rev_id in revisions:
        raise RevisionError('duplicate_identity','duplicate proposal or revision ID across ensemble')
    proposals.add(prop_id);revisions.add(rev_id)
    if not isinstance(proposal['changes'],list) or not 2<=len(proposal['changes'])<=4:
        raise ValueError('V3 member requires 2..4 distinct physical edits')
    seen=set()
    for change in proposal['changes']:
        if not isinstance(change,dict):
            raise ValueError('each physical edit must be an object')
        op=change.get('operation')
        if not isinstance(op,str) or op not in _OPERATIONS:
            raise RevisionError('unsupported_change','unsupported V3 physical operation')
        exact_keys(change,('operation','category','target_id','expected_role',
                           'provenance',*_OPERATIONS[op]))
        target=identifier(change['target_id'])
        if target in seen:
            raise RevisionError('duplicate_target','one physical target can be edited once in a transaction')
        seen.add(target)
        prov=change['provenance']
        exact_keys(prov,('origin','reason','evidence'))
        if (prov['origin'] not in ('supplied_fact','source_convention','adopted_assumption',
                                   'unit_conversion','illustrative_choice')
                or any(not isinstance(prov[k],str) or not prov[k].strip()
                       for k in ('reason','evidence'))):
            raise ValueError('member physical inputs require explicit literal provenance')
        if op.startswith('add_'):
            if target in added:
                raise RevisionError('identity_conflict','sibling hypotheses may not reuse inserted physical IDs')
            added.add(target)
    for key,required in (
            ('investigation',('investigation_version','id','model_id','observations')),
            ('analysis',('analysis_version','id','mode')),
            ('presentation',('presentation_version','id','bounds_m','entity_order'))):
        value=row[key]
        if not isinstance(value,dict) or not set(required).issubset(value):
            raise ValueError(f'{key} must be a complete native version-1 object')
        identifier(value['id'])
        if type(value[key+'_version']) is not int or value[key+'_version']!=1:
            raise ValueError(f'{key} version must be JSON integer 1')
    if row['investigation']['model_id']!=parent['model_id']:
        raise RevisionError('wrong_model','member investigation belongs to another physical model')
    _native_grammar(row, kind)
    # Existing compare validator is the authority for exact pair grammar,
    # not a copied or loosened observation-matching implementation.
    scenario_comparisons._validate({
        'comparison_version':1,'id':_comparison_id(parent['model_id'],name),
        'left_run_sha256':'0'*64,'right_run_sha256':'0'*64,
        'pairs':row['pairs'],
    })


def _comparison_id(model_id,member):
    # This is a *local* comparison file identifier, not physical identity.
    return identifier(f'comparison-{member}')


def validate_spec(spec,store,*,allow_reserved=False):
    _finite_tree(spec)
    # Confirm the whole authored input can be serialized before any write.
    encode(spec)
    exact_keys(spec, ('ensemble_version','id','parent','source_run_sha256','members'))
    if type(spec['ensemble_version']) is not int or spec['ensemble_version']!=1:
        raise ValueError('only ensemble_version 1 is supported')
    name=identifier(spec['id'])
    if len(name)>25:
        raise ValueError('ensemble id must be at most 25 characters')
    check_reference(spec['parent'])
    if (not isinstance(spec['source_run_sha256'],str)
            or len(spec['source_run_sha256'])!=64
            or any(ch not in '0123456789abcdef' for ch in spec['source_run_sha256'])):
        raise ValueError('source_run_sha256 must be exact lowercase 64-hex SHA')
    members=spec['members']
    if not isinstance(members,list) or not MIN_MEMBERS<=len(members)<=MAX_MEMBERS:
        raise ValueError('ensemble requires 2..4 authored members')
    parent,_=store.read(spec['parent'])
    ids=set();props=set();revs=set();added=set()
    for row in members:
        _validate_member(row,spec['parent'],parent['kind'],ids,props,revs,added)
    # Collision check is a preflight guard, not a promise of transaction
    # isolation with concurrent writers. The model store remains authoritative.
    if not allow_reserved:
        for proposal_id,revision_id in zip(
            (m['proposal']['proposal_id'] for m in members),
            (m['proposal']['revision_id'] for m in members)):
            if ((store.path/'proposals'/sha256(proposal_id.encode())).exists()
                    or store._directory(revision_id).exists()):
                raise RevisionError('identity_conflict','proposal or revision identity already reserved')
    return spec


def _protected_output(request,store_path,using,output):
    if output.exists() or output.is_symlink():
        raise FileExistsError('ensemble output must be a fresh directory')
    if output.resolve()==request.resolve():
        raise ValueError('output aliases source request')
    for parent in (store_path,using):
        if output.resolve().is_relative_to(parent.resolve()):
            raise ValueError('ensemble output must remain outside model store and original native run')
    for ancestor in (output.resolve(),*output.resolve().parents):
        if ((ancestor/'model.json').is_file()
                and (ancestor/'revisions').is_dir()
                and (ancestor/'proposals').is_dir()):
            raise ValueError('ensemble output cannot be placed within a model store')


def _source(store,using,spec):
    raw=(using/'run.json').read_bytes()
    if sha256(raw)!=spec['source_run_sha256']:
        raise RevisionError('wrong_run','saved parent template does not match the exact run.json pin')
    captured,template=_settings(using,store)
    run,revision,summary,report=model_runs.inspect_run(using,expected_reference=spec['parent'])
    if (not summary.get('execution_complete') or summary.get('status')!='complete'
            or not summary.get('numerical_checks_passed')
            or run['reference']!=spec['parent'] or report is None):
        raise RevisionError('invalid_template','baseline template must be complete, sealed and exact parent')
    return captured,template


def run_ensemble(spec_path,*,store_path,using,output):
    spec_path,store_path,using,output=map(Path,(spec_path,store_path,using,output))
    _protected_output(spec_path,store_path,using,output)
    raw=spec_path.read_bytes()
    spec=decode(raw)
    store=ModelStore(store_path)
    validate_spec(spec,store)
    captured,template=_source(store,using,spec)

    output.mkdir(parents=True,exist_ok=False)
    inputs=output/'inputs'; inputs.mkdir()
    put(inputs/'ensemble.json',raw)
    put(inputs/'template.json',encode(template))
    for key,value in captured.items():
        put(inputs/key,value)
    put(output/'started.json',encode({
        'ensemble_version':1,'id':spec['id'],'status':'pending',
        'request_sha256':sha256(raw),'source_run_sha256':spec['source_run_sha256'],
        'meaning':'Only a sealed summary and final integrity inventory can claim completion'}))
    baseline_ref=inputs/'baseline.reference.json'
    put(baseline_ref,encode(spec['parent']))
    baseline_path=output/'baseline'
    base=model_runs.execute(store.path,baseline_ref,inputs/'investigation.json',
                            inputs/'analysis.json',inputs/'presentation.json',
                            baseline_path,run_id=_run_id(spec['id']))
    model_runs.inspect_run(baseline_path,expected_reference=spec['parent'])
    complete_base=base.get('status')=='complete' and base.get('execution_complete') is True
    rows=[]
    for i,row in enumerate(spec['members'],start=1):
        name=row['id']
        if not complete_base:
            rows.append({'id':name,'index':i,'status':'not_attempted',
                         'decision':'not_attempted','reference':None,
                         'reason':'fresh baseline incomplete; member never attempted'})
            continue
        folder=_member_dir(output,i);folder.mkdir()
        proposal_path=folder/'proposal.json'
        put(proposal_path,encode(row['proposal']))
        decision=store.revise(proposal_path)
        put(folder/'decision.json',encode(decision))
        item={'id':name,'index':i,'decision':decision['status'],
              'reference':decision.get('reference'),'status':'rejected'}
        if decision['status']!='accepted':
            item['reason']=decision.get('reason','native atomic V3 revision not accepted')
            rows.append(item)
            continue
        ref=folder/'reference.json';put(ref,encode(decision['reference']))
        for tag,obj in (('investigation',row['investigation']),
                        ('analysis',row['analysis']),('presentation',row['presentation'])):
            put(folder/(tag+'.json'),encode(obj))
        native_path=folder/'run'
        calculated=model_runs.execute(store.path,ref,
                         folder/'investigation.json',folder/'analysis.json',
                         folder/'presentation.json',native_path,
                         run_id=_run_id(spec['id'],name))
        model_runs.inspect_run(native_path,expected_reference=decision['reference'])
        item['run_status']=calculated['status']
        if not calculated.get('execution_complete'):
            item['status']='partial'
            item['reason']='native analysis incomplete; no cross-scenario comparison attempted'
            rows.append(item)
            continue
        compare_request={
            'comparison_version':1,'id':_comparison_id(spec['id'],name),
            'left_run_sha256':sha256((baseline_path/'run.json').read_bytes()),
            'right_run_sha256':sha256((native_path/'run.json').read_bytes()),
            'pairs':row['pairs'],
        }
        cmp=folder/'comparison.request.json';put(cmp,encode(compare_request))
        result=scenario_comparisons.compare(cmp,left=baseline_path,right=native_path,
                                            output=folder/'comparison')
        scenario_comparisons.inspect(folder/'comparison',left=baseline_path,right=native_path)
        item['comparison_status']=result['status']
        item['status']='complete' if result['status']=='complete' else 'partial'
        rows.append(item)
    summary={
        'ensemble_version':1,'id':spec['id'],'parent':spec['parent'],
        'source_run_sha256':spec['source_run_sha256'],
        'template':template,
        'baseline':{'status':base['status'],'execution_complete':complete_base,
                    'reference':spec['parent'],'path':'baseline'},
        'members':rows,
        'status':'complete' if complete_base and all(x['status']=='complete' for x in rows) else 'partial',
        'meaning':MEANING,'qualification':QUALIFICATION,
    }
    put(output/'summary.json',encode(summary))
    lines=['# Sealed bounded scenario ensemble','',f"Ensemble: {spec['id']}",
           f"Status: {summary['status']}",'',
           'Every member is a separately authored hypothetical static configuration.',
           'A valid model revision is not a numerical result; rejected/partial evidence is retained.',
           'Comparisons are from independently recorded native runs, not physical transitions.',
           'See exact request, per-member decisions, saved runs and sealed comparison records.','']
    put(output/'REPORT.md','\n'.join(lines).encode('utf-8'))
    put(output/'integrity.json',encode({'files':_inventory(output)}))
    return summary


def inspect_ensemble(output,*,store_path,using):
    output,store_path,using=map(Path,(output,store_path,using))
    recorded=decode((output/'integrity.json').read_bytes())
    if recorded.get('files')!=_inventory(output):
        raise RevisionError('ensemble_integrity','ensemble output inventory mismatch')
    spec_raw=(output/'inputs/ensemble.json').read_bytes()
    spec=decode(spec_raw)
    store=ModelStore(store_path)
    # Revalidate the complete authored grammar read-only. Accepted members
    # legitimately reserve identities, so skip only the collision preflight.
    validate_spec(spec,store,allow_reserved=True)
    if sha256((using/'run.json').read_bytes())!=spec['source_run_sha256']:
        raise RevisionError('wrong_run','template identity no longer matches')
    captured,template=_source(store,using,spec)
    if decode((output/'inputs/template.json').read_bytes())!=template:
        raise RevisionError('ensemble_integrity','captured template metadata changed')
    for key,raw in captured.items():
        if (output/'inputs'/key).read_bytes()!=raw:
            raise RevisionError('ensemble_integrity','captured original native settings changed')
    pending=decode((output/'started.json').read_bytes())
    if pending != {'ensemble_version':1,'id':spec['id'],'status':'pending',
                   'request_sha256':sha256(spec_raw),
                   'source_run_sha256':spec['source_run_sha256'],
                   'meaning':'Only a sealed summary and final integrity inventory can claim completion'}:
        raise RevisionError('ensemble_integrity','pending marker or request binding inconsistent')
    if decode((output/'inputs/baseline.reference.json').read_bytes())!=spec['parent']:
        raise RevisionError('ensemble_integrity','baseline reference differs from source parent')
    _,_,base,_=model_runs.inspect_run(output/'baseline',expected_reference=spec['parent'])
    complete_base=base.get('status')=='complete' and base.get('execution_complete') is True
    rows=[]
    for i,member in enumerate(spec['members'],start=1):
        name=member['id']
        folder=_member_dir(output,i)
        if not complete_base:
            if folder.exists():
                raise RevisionError('ensemble_integrity','member attempted despite incomplete baseline')
            rows.append({'id':name,'index':i,'status':'not_attempted',
                         'decision':'not_attempted','reference':None,
                         'reason':'fresh baseline incomplete; member never attempted'})
            continue
        if decode((folder/'proposal.json').read_bytes())!=member['proposal']:
            raise RevisionError('ensemble_integrity','stored V3 proposal differs from authored member')
        decision=decode((folder/'decision.json').read_bytes())
        proposal_id=member['proposal']['proposal_id']
        stored_dir=store.path/'proposals'/sha256(proposal_id.encode())
        stored_decision=stored_dir/'decision.json'
        if decision!=decode(stored_decision.read_bytes()):
            raise RevisionError('ensemble_integrity','decision differs from native store decision')
        # The store's ORIGINAL raw proposal bytes, not just its decision, must
        # match the immutable attempt and its recorded SHA even for rejections.
        original=(stored_dir/'proposal.json').read_bytes()
        if (decision.get('proposal_id')!=proposal_id
                or sha256(original)!=decision.get('proposal_sha256')
                or original!=(folder/'proposal.json').read_bytes()):
            raise RevisionError('ensemble_integrity','native store proposal bytes differ from decision and ensemble evidence')
        row={'id':name,'index':i,'decision':decision['status'],
             'reference':decision.get('reference'),'status':'rejected'}
        if decision['status']!='accepted':
            row['reason']=decision.get('reason','native atomic V3 revision not accepted')
            rows.append(row)
            continue
        reference=decision['reference']
        child,_=store.read(reference)
        if (child['parent']!=spec['parent'] or child['operation']!=member['proposal']
                or decode((folder/'reference.json').read_bytes())!=reference):
            raise RevisionError('ensemble_integrity','accepted model revision not bound to authored proposal')
        for tag in ('investigation','analysis','presentation'):
            if decode((folder/(tag+'.json')).read_bytes())!=member[tag]:
                raise RevisionError('ensemble_integrity','authored native analysis differs from retained member')
        _,_,native,_=model_runs.inspect_run(folder/'run',expected_reference=reference)
        row['run_status']=native['status']
        if not native.get('execution_complete'):
            row['status']='partial'
            row['reason']='native analysis incomplete; no cross-scenario comparison attempted'
            if (folder/'comparison').exists():
                raise RevisionError('ensemble_integrity','comparison exists for incomplete source')
            rows.append(row)
            continue
        pair_request={
            'comparison_version':1,'id':_comparison_id(spec['id'],name),
            'left_run_sha256':sha256((output/'baseline/run.json').read_bytes()),
            'right_run_sha256':sha256((folder/'run/run.json').read_bytes()),
            'pairs':member['pairs'],
        }
        if decode((folder/'comparison.request.json').read_bytes())!=pair_request:
            raise RevisionError('ensemble_integrity','saved cross-scenario request differs')
        result=scenario_comparisons.inspect(folder/'comparison',
                            left=output/'baseline',right=folder/'run')
        row['comparison_status']=result['status']
        row['status']='complete' if result['status']=='complete' else 'partial'
        rows.append(row)
    expected={
        'ensemble_version':1,'id':spec['id'],'parent':spec['parent'],
        'source_run_sha256':spec['source_run_sha256'],'template':template,
        'baseline':{'status':base['status'],'execution_complete':complete_base,
                    'reference':spec['parent'],'path':'baseline'},
        'members':rows,
        'status':'complete' if complete_base and all(r['status']=='complete' for r in rows) else 'partial',
        'meaning':MEANING,'qualification':QUALIFICATION,
    }
    saved=decode((output/'summary.json').read_bytes())
    if expected!=saved:
        raise RevisionError('ensemble_integrity','summary completion contradicts actual saved native evidence')
    return saved


def view_ensemble(output, *, store_path, using, member_id=None, baseline=False,
                  sample_index=0, screenshot_output=None):
    """Present exactly one integrity-checked recorded native run, never an inferred scenario transition."""
    if baseline == (member_id is not None):
        raise ValueError('select exactly one of baseline or a named ensemble member')
    if member_id is not None and (type(member_id) is not str or not member_id):
        raise ValueError('member selection requires one exact declared member ID')
    if type(sample_index) is not int or sample_index < 0:
        raise ValueError('sample index must be a nonnegative recorded sample integer')
    output, store_path, using = map(Path, (output, store_path, using))
    # Check all ensemble/source/model evidence before resolving a selection or
    # constructing any interactive viewer or screenshot directory.
    summary = inspect_ensemble(output, store_path=store_path, using=using)
    if baseline:
        if summary['baseline']['status'] != 'complete' or not summary['baseline']['execution_complete']:
            raise RevisionError('preview_unavailable', 'fresh baseline native run is incomplete')
        selected = output/'baseline'
        reference = summary['parent']
        selection = 'baseline'
    else:
        row = next((item for item in summary['members'] if item['id'] == member_id), None)
        if row is None:
            raise RevisionError('unknown_member', 'selected member ID is not declared by this ensemble')
        # A comparison can legitimately be partial because the baseline has no
        # physical counterpart; a complete native member run is still viewable.
        if row.get('decision') != 'accepted' or row.get('run_status') != 'complete':
            raise RevisionError('preview_unavailable', 'selected member has no complete native run')
        selected = _member_dir(output, row['index'])/'run'
        reference = row['reference']
        selection = member_id
    screenshot = None
    if screenshot_output is not None:
        screenshot = Path(screenshot_output)
        if screenshot.exists() or screenshot.is_symlink():
            raise FileExistsError('presentation output must be a fresh directory')
        dest = screenshot.resolve()
        if any(dest.is_relative_to(root.resolve()) for root in (output,store_path,using)):
            raise ValueError('presentation output must be outside the sealed ensemble, store and template')
    # Reuse the existing sealed native presentation and sample guards; no new
    # field evaluation, interpolation, physical mutation or renderer dispatch.
    run, _, native, _ = model_runs.inspect_run(selected, expected_reference=reference)
    if native['status'] != 'complete' or not native['execution_complete']:
        raise RevisionError('preview_unavailable','selected run is not complete')
    if native['mode'] == 'static' and sample_index != 0:
        raise ValueError('static field presentation has no physical sample evolution')
    model_runs.present_run(selected, sample_index=sample_index, screenshot_directory=screenshot)
    return {'status':'complete', 'ensemble_id':summary['id'],
            'ensemble_status':summary['status'], 'selection':selection,
            'run_id':run['run_id'], 'reference':reference,
            'presentation':'recorded native run only; not teacher acceptance',
            'meaning':MEANING}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run','inspect','view'))
    parser.add_argument('spec_or_output')
    parser.add_argument('--store',required=True)
    parser.add_argument('--using',required=True)
    parser.add_argument('--output')
    selector=parser.add_mutually_exclusive_group()
    selector.add_argument('--baseline',action='store_true')
    selector.add_argument('--member')
    parser.add_argument('--sample-index',type=int)
    args=parser.parse_args(argv)
    try:
        if args.command=='run':
            if args.output is None:
                raise ValueError('run requires --output')
            if args.baseline or args.member is not None or args.sample_index is not None:
                raise ValueError('run does not accept view selection or sample-index flags')
            result=run_ensemble(args.spec_or_output,store_path=args.store,
                                using=args.using,output=args.output)
        elif args.command=='inspect':
            if args.output is not None:
                raise ValueError('inspect does not accept --output')
            if args.baseline or args.member is not None or args.sample_index is not None:
                raise ValueError('inspect does not accept view selection or sample-index flags')
            result=inspect_ensemble(args.spec_or_output,store_path=args.store,
                                    using=args.using)
        else:
            result=view_ensemble(args.spec_or_output,store_path=args.store,
                                 using=args.using,member_id=args.member,baseline=args.baseline,
                                 sample_index=0 if args.sample_index is None else args.sample_index,
                                 screenshot_output=args.output)
        print(encode(result).decode(),end='')
        return 0 if result['status']=='complete' else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('emfeeld scenario ensemble: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
