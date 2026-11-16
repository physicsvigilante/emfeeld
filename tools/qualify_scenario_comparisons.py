"""Native E1/G1/T1 sealed cross-scenario V1 qualification (same author).

Uses existing atomic revisions, source scenes and native model runs. A separately
expressed verification script checks ideal fields, potential differences and
RK4 trajectories. Never changes existing tests, physics, viewer or solver.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from emfeeld.model_revisions import ModelStore, decode, encode, put, sha256
from emfeeld.model_runs import execute, inspect_run
from emfeeld.scenario_comparisons import compare, inspect
from qualify_atomic_revisions import CASES, origin, proposal, inventory, assert_unchanged, save


def inputs(case,scene,names,*,side,particles,samples):
    cfg=CASES[case]
    probes=cfg['probes']
    observations=[]
    for n,point in enumerate(probes):
        observations.append({'id':f'{side}-field-{n}', 'type':'field','position_m':point})
    observations.append({'id':f'{side}-step', 'type':'potential_difference',
                         'from_m':probes[0],'to_m':probes[1]})
    mode=cfg['mode']
    analysis={'analysis_version':1,'id':f'{case}-{side}-analysis','mode':mode}
    if mode=='trajectory':
        analysis.update(duration_s=scene['duration_s'],samples=samples,
            checks={'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,
                    'rtol':1e-7,'max_normalized_energy_drift':1e-7})
        for body in particles:
            for quantity in ('position','velocity'):
                observations.append({'id':f'{side}-{body}-{quantity}',
                     'type':'trajectory_sample','particle_id':body,
                     'quantity':quantity,'sample_index':samples//2})
    investigation={'investigation_version':1,'id':f'{case}-{side}-questions',
                   'model_id':f'cross-{case}','observations':observations}
    presentation={'presentation_version':1,'id':f'{case}-{side}-view',
                  'bounds_m':scene['bounds_m'],'entity_order':names}
    return investigation,analysis,presentation


def native(folder,store,reference,scenario,side):
    ref=save(folder/f'{side}-reference.json',reference)
    names=('investigation','analysis','presentation')
    paths=[save(folder/f'{side}-{key}.json',item) for key,item in zip(names,scenario)]
    target=folder/side
    summary=execute(store.path,ref,*paths,target,run_id=f'{folder.name}-{side}')
    if not summary.get('execution_complete') or summary['status']!='complete':
        raise AssertionError(f'{folder.name} {side} native calculation incomplete: {summary}')
    inspect_run(target,expected_reference=reference)
    return target


def member(pair_id,kind,left_name,right_name,particle=None):
    row={'id':pair_id,'type':kind,'left_observation_id':left_name,
         'right_observation_id':right_name}
    if particle is not None:row['particle_id']=particle
    return row


def pairs(case,pre,post):
    obs=[member('field-vector','field_vector','L-field-0','R-field-0'),
         member('field-magnitude','field_magnitude','L-field-1','R-field-1'),
         member('potential-step','potential_difference','L-step','R-step')]
    if case=='T1':
        obs.append(member('second-vector','field_vector','L-field-2','R-field-2'))
    else:
        for body in pre:
            for quantity in ('position','velocity'):
                obs.append(member(body+'-'+quantity,'particle_'+quantity,
                       f'L-{body}-{quantity}',f'R-{body}-{quantity}',body))
    if case=='G1':
        obs.append(member('body-3-absent','particle_position',
                          'L-body_3-position','R-body_3-position','body_3'))
    return obs


def qualify(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'qualification_version':1,'status':'started',
            'source_commit':'1b7d5c652bb635723746b3c6ce77baee536b997e',
            'attribution':'same-author E1/G1/T1 transfer, separate-reference checker required',
            'cases':{}}
    save(output/'started.json',report)
    for case,cfg in CASES.items():
        folder=output/case;folder.mkdir()
        raw=(ROOT/cfg['scene']).read_bytes()
        put(folder/'original.json',raw)
        scene=decode(raw)
        spec={'import_version':1,'model_id':f'cross-{case}',
              'revision_id':'root','source_sha256':sha256(raw),
              'source_ids':cfg['sources'],'particle_ids':cfg['particles'],
              'default_origin':origin(case),
              'interpretation':{
                 'statement':scene['title'],'assumptions':['Prescribed static sources, independent test particles; no feedback'],
                 'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
                 'unresolved':[],'scenario_intent':'illustrative_exploration'}}
        store,root=ModelStore.import_legacy(folder/'original.json',save(folder/'import.json',spec),folder/'store')
        nleft=scene.get('samples',2)
        pre=cfg['particles']
        baseline=native(folder,store,root,
             inputs(case,scene,cfg['sources']+pre,side='L',particles=pre,samples=nleft),'left')
        old_store,old_run=inventory(store.path),inventory(baseline)
        new,source_ids,particle_ids=proposal(case,root,store)
        decision=store.revise(save(folder/'atomic-proposal.json',new))
        if decision['status']!='accepted':raise AssertionError((case,decision))
        ref=decision['reference'];child=store.read(ref)[0]
        if child['parent']!=root or child['source_order']!=source_ids or child['particle_order']!=particle_ids:
            raise AssertionError('named V3 mapping or parent changed unexpectedly')
        nright=51 if cfg['mode']=='trajectory' else 2
        final=native(folder,store,ref,
             inputs(case,scene,source_ids+particle_ids,side='R',particles=particle_ids,samples=nright),'right')
        assert_unchanged(store.path,old_store)
        assert_unchanged(baseline,old_run)
        request={'comparison_version':1,'id':case+'-cross-scenarios',
                 'left_run_sha256':sha256((baseline/'run.json').read_bytes()),
                 'right_run_sha256':sha256((final/'run.json').read_bytes()),
                 'pairs':pairs(case,pre,particle_ids)}
        req=save(folder/'comparison-request.json',request)
        comparison=compare(req,left=baseline,right=final,output=folder/'comparison')
        inspect(folder/'comparison',left=baseline,right=final)
        expected_status='partial' if case=='G1' else 'complete'
        if comparison['status']!=expected_status:
            raise AssertionError(f'{case} comparison should be {expected_status}: {comparison}')
        if case=='G1':
            unavailable=[x for x in comparison['comparisons'] if x['status']!='ok']
            if len(unavailable)!=1 or unavailable[0]['code']!='unknown_operand':
                raise AssertionError('G1 added body must not be invented in baseline')
        if len(list((store.path/'revisions').iterdir()))!=2:
            raise AssertionError('one atomic revision expected, not intermediate descendants')
        report['cases'][case]={
            'status':comparison['status'], 'root_reference':root,'final_reference':ref,
            'original_sha256':sha256(raw),'left_run_sha256':request['left_run_sha256'],
            'right_run_sha256':request['right_run_sha256'],
            'pairs':len(request['pairs']),'complete_pairs':sum(x['status']=='ok' for x in comparison['comparisons']),
            'unavailable_pairs':sum(x['status']!='ok' for x in comparison['comparisons']),
            'baseline_preserved':True,'accepted_atomic_revisions':1,
            'left_samples':nleft,'right_samples':nright,'left':'left','right':'right',
            'comparison':'comparison',
        }
    report['status']='complete'
    save(output/'qualification.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    print(encode(qualify(a.output)).decode())
