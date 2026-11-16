"""Same-author E1/G1/T1 transfer for bounded native scenario ensembles.

Two independently authored V3 sibling hypotheses per case; one freshly
recomputed baseline. Physical references are checked by a separate script.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from emfeeld.model_revisions import ModelStore,decode,encode,put,sha256
from emfeeld.model_runs import execute,inspect_run
from emfeeld.scenario_ensembles import run_ensemble,inspect_ensemble
from qualify_atomic_revisions import CASES,origin,proposal,inventory,assert_unchanged,save
from qualify_scenario_comparisons import inputs,pairs


def alternative(case,parent,store):
    p1,s1,b1=proposal(case,parent,store)
    p2=deepcopy(p1)
    p2['proposal_id']=case+'-siblingB'
    p2['revision_id']=case+'-siblingB'
    if case=='E1':
        row=p2['changes'][1]
        row['target_id']='alternate_positive_line'
        row['source']['center_m']=[.7,-.2,0]
        row['source']['charge_per_m_C_m']=2e-11
        s2=['axial_field','alternate_positive_line']
        b2=['test_charge']
    elif case=='G1':
        p2['changes'][0]['value']=3e9
        p2['changes'][1]['target_id']='body_4'
        p2['changes'][1]['particle']['position_m']=[-.4,1.,.3]
        p2['changes'][1]['particle']['velocity_m_s']=[-.02,.05,-.03]
        s2=['source_A','source_B']
        b2=['body_1','body_2','body_4']
    else:
        p2['changes'][0]['value']=4e-9
        p2['changes'][1]['value']=-1e-9
        s2=['shell','central_point']
        b2=[]
    return ((p1,s1,b1),(p2,s2,b2))


def run_case(folder,case,scene,root,store):
    cfg=CASES[case]
    base_inv,base_ana,base_pre=inputs(case,scene,cfg['sources']+cfg['particles'],
                                     side='L',particles=cfg['particles'],
                                     samples=scene.get('samples',2))
    base_inv['model_id']=root['model_id']
    templatepaths=[save(folder/f'template-{n}.json',val)
                   for n,val in zip(('ref','inv','analysis','view'),
                                    (root,base_inv,base_ana,base_pre))]
    template=folder/'parent-template'
    first=execute(store.path,*templatepaths,template,run_id=case+'-template')
    if first['status']!='complete' or not first['execution_complete']:
        raise AssertionError(f'{case}: template baseline is not complete: {first}')
    inspect_run(template,expected_reference=root)
    old_store,old_run=inventory(store.path),inventory(template)
    members=[]
    for i,(physical,source_ids,particle_ids) in enumerate(alternative(case,root,store),start=1):
        letter='A' if i==1 else 'B'
        inv,analysis,pres=inputs(case,scene,source_ids+particle_ids,
                                 side=letter,particles=particle_ids,
                                 samples=51 if cfg['mode']=='trajectory' else 2)
        inv['model_id']=root['model_id']
        reqs=deepcopy(pairs(case,cfg['particles'],particle_ids))
        for p in reqs:
            p['right_observation_id']=p['right_observation_id'].replace('R-',letter+'-',1)
        if case=='G1' and i==2:
            absent=reqs[-1]
            absent['id']='body-4-absent'
            absent['right_observation_id']=letter+'-body_4-position'
            absent['particle_id']='body_4'
        members.append({
            'id':'hypothesis-'+letter,
            'proposal':physical,
            'investigation':inv,'analysis':analysis,'presentation':pres,
            'pairs':reqs,
        })
    spec={
        'ensemble_version':1,'id':case+'-ensemble','parent':root,
        'source_run_sha256':sha256((template/'run.json').read_bytes()),
        'members':members,
    }
    request=save(folder/'ensemble-request.json',spec)
    out=folder/'ensemble'
    result=run_ensemble(request,store_path=store.path,using=template,output=out)
    expected='partial' if case=='G1' else 'complete'
    if result['status']!=expected:
        raise AssertionError(f'{case}: expected {expected} ensemble, got {result}')
    inspect_ensemble(out,store_path=store.path,using=template)
    assert_unchanged(template,old_run)
    assert_unchanged(store.path,old_store)
    if len(list((store.path/'revisions').iterdir()))!=3:
        raise AssertionError('expected parent plus exactly two accepted sibling revisions')
    if len(result['members'])!=2 or any(m['decision']!='accepted' for m in result['members']):
        raise AssertionError('both deliberately qualified hypotheses must construct')
    if case=='G1':
        if any(m['status']!='partial' for m in result['members']):
            raise AssertionError('added body must not be substituted for baseline member')
    else:
        if any(m['status']!='complete' for m in result['members']):
            raise AssertionError('qualified field/motion comparisons must complete')
    return {
        'status':result['status'],'template_sha256':sha256((template/'run.json').read_bytes()),
        'parent':root,'members':result['members'],
        'source_sha256':sha256((folder/'original.json').read_bytes()),
        'baseline_preserved':True,
        'accepted_child_revisions':2,
        'complete_hypothesis_runs':2,
    }


def qualify(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    record={'version':1,'status':'started','attribution':'same-author native case construction and references, not Chat B',
            'cases':{}}
    save(output/'started.json',record)
    for case,cfg in CASES.items():
        folder=output/case;folder.mkdir()
        raw=(ROOT/cfg['scene']).read_bytes()
        put(folder/'original.json',raw)
        scene=decode(raw)
        spec={
            'import_version':1,'model_id':f'ensemble-{case}',
            'revision_id':'root','source_sha256':sha256(raw),
            'source_ids':cfg['sources'],'particle_ids':cfg['particles'],
            'default_origin':origin(case),
            'interpretation':{
                'statement':scene['title'],
                'assumptions':['Fixed prescribed sources, independent nonrelativistic test particles'],
                'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
                'unresolved':[],'scenario_intent':'illustrative_exploration',
            },
        }
        store,root=ModelStore.import_legacy(folder/'original.json',
                                save(folder/'import.json',spec),folder/'store')
        record['cases'][case]=run_case(folder,case,scene,root,store)
    record['status']='complete'
    save(output/'qualification.json',record)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    print(encode(qualify(a.output)).decode())
