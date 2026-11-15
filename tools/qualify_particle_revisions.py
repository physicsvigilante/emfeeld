"""Exercise bounded particle add/remove through the public native model workflow.

Frozen E1/G1/T1 arrangement data are authored scenes; the production module has
no case-specific dispatch. Stored trajectories are checked separately by
verification/check_particle_revision_runs.py, not by this driver.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from emfeeld.model_revisions import ModelStore, decode, encode, put, sha256
from emfeeld.model_runs import execute, inspect_run, present_run

CASES={
    'E1':{'scene':'examples/marker_regression/E1.json',
          'sources':['negative_line','axial_field'],'particles':['body_1'],
          'probes':[[1.2,.2,.8],[1.5,-.4,1.4]],'mode':'trajectory'},
    'G1':{'scene':'examples/marker_regression/G1.json',
          'sources':['source_A','source_B'],'particles':['body_1','body_2'],
          'probes':[[.5,.7,.3],[.8,-.6,.3]],'mode':'trajectory'},
    'T1':{'scene':'examples/structural_revisions/T1.json',
          'sources':['shell','point'],'particles':[],
          'probes':[[.4,.6,.3],[2.8,.25,.4],[-1.1,.9,.75]],'mode':'static'}
}


def save(path,value):put(path,encode(value));return path


def stored_bytes(folder):
    return {p.relative_to(folder).as_posix():sha256(p.read_bytes())
            for p in folder.rglob('*') if p.is_file()}


def unmodified(folder,original):
    for name,digest in original.items():
        if sha256((folder/name).read_bytes())!=digest:
            raise AssertionError(f'original artifact changed: {folder/name}')


def investigation(case,source,body_names,*,purpose='root'):
    info=CASES[case]
    observations=[]
    for i,point in enumerate(info['probes']):
        for q in ('field','potential'):
            observations.append({'id':f'{q}_{i}','type':q,'position_m':point})
    if info['mode']=='trajectory':
        for body in body_names:
            for index in (0,source['samples']//2,source['samples']-1):
                for q in ('position','velocity','speed','kinetic_energy','potential_energy','total_energy'):
                    observations.append({'id':f'{body}_{q}_{index}',
                        'type':'trajectory_sample','particle_id':body,
                        'quantity':q,'sample_index':index})
    return {'investigation_version':1,'id':f'{case}-{purpose}',
            'model_id':f'particle-{case}','observations':observations}


def analysis(case,source):
    info=CASES[case]
    data={'analysis_version':1,'id':'accepted-analysis','mode':info['mode']}
    if info['mode']=='trajectory':
        data.update(duration_s=source['duration_s'],samples=source['samples'],checks={
             'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,
             'rtol':1e-7,'max_normalized_energy_drift':1e-7})
    return data


def presentation(case,source,names,purpose):
    return {'presentation_version':1,'id':f'{case}-{purpose}',
            'bounds_m':source['bounds_m'],
            'entity_order':CASES[case]['sources']+names}


def request(case,reference,ident,operation,target,*,particle=None,expected=None):
    p={'proposal_version':2,'proposal_id':ident,'revision_id':ident,
       'parent':deepcopy(reference),'category':'structural_change',
       'operation':operation,'target_id':target,'expected_role':'particle',
       'scenario_intent':'teacher_hypothesis',
       'provenance':{'origin':'illustrative_choice',
                     'reason':'Bounded test-particle structural hypothesis',
                     'evidence':f'Frozen {case} test, not textbook source facts'}}
    if operation=='add_particle':p['particle']=particle
    else:p['expected_particle']=expected
    return p


def run_model(folder,store,ref,inv,ana,view,ident):
    paths=[save(folder/f'{ident}.{key}.json',value) for key,value in
           [('reference',ref),('investigation',inv),('analysis',ana),('presentation',view)]]
    run=folder/ident
    summary=execute(store.path,*paths,run,run_id=ident)
    inspect_run(run,expected_reference=ref)
    return run,summary


def qualify(output,*,render=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'qualification_version':1,'parent_main':'7e6bd8c72cac7708ab3c2355cc1a98db09762133',
            'status':'started','cases':{},'meaning':'same-author acceptance; Chat B review is separate'}
    save(output/'started.json',report)
    for case,info in CASES.items():
        folder=output/case;folder.mkdir()
        src_raw=(ROOT/info['scene']).read_bytes();src=decode(src_raw)
        put(folder/'source.json',src_raw)
        origin={'origin':'illustrative_choice','reason':'Frozen candidate test arrangement',
                'evidence':f'original scene {info["scene"]}; not externally verified givens'}
        assignment={'import_version':1,'model_id':f'particle-{case}',
             'revision_id':'root','source_sha256':sha256(src_raw),
             'source_ids':info['sources'],'particle_ids':info['particles'],
             'default_origin':origin,
             'interpretation':{'statement':src['title'],
                 'assumptions':['Prescribed sources; independent nonrelativistic test bodies; no backreaction'],
                 'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
                 'unresolved':[],'scenario_intent':'illustrative_exploration'}}
        store,root=ModelStore.import_legacy(folder/'source.json',save(folder/'assignment.json',assignment),folder/'store')
        baseinv=investigation(case,src,info['particles'])
        ana=analysis(case,src)
        basepres=presentation(case,src,info['particles'],'root')
        baseline,base_summary=run_model(folder,store,root,baseinv,ana,basepres,'root-run')
        if not base_summary['execution_complete']:
            raise AssertionError(f'{case} baseline is not an admitted complete run: {base_summary}')
        retained_store=stored_bytes(store.path);retained_run=stored_bytes(baseline)
        records=[{'reference':root,'run':'root-run','status':'complete'}]
        outcomes={'root_reference':root,'source_sha256':sha256(src_raw),
                  'initial_source_ids':info['sources'],'initial_particle_ids':info['particles'],
                  'runs':records,'revisions':[], 'baseline_preserved':False}
        if case=='E1':
            particle={'mass_kg':2e-6,'charge_C':3e-7,
                'position_m':[1.65,-.45,.2],'velocity_m_s':[0.,.15,.1]}
            name='new_body'
            p=request(case,root,'add-second-body','add_particle',name,particle=particle)
            decision=store.revise(save(folder/'add.proposal.json',p))
            if decision['status']!='accepted':raise AssertionError(decision)
            ref=decision['reference'];new_names=['body_1',name]
            inv=investigation(case,src,new_names,purpose='with-second')
            view=presentation(case,src,new_names,'with-second')
            run,summ=run_model(folder,store,ref,inv,ana,view,'added-run')
            if not summ['execution_complete']:raise AssertionError(summ)
            outcomes['revisions'].append({'operation':'add_particle','reference':ref,'id':name})
            outcomes['runs'].append({'reference':ref,'run':'added-run','status':'complete'})
            # The original baseline has not been reused as a numerical result.
            if render:present_run(run,sample_index=src['samples']//2,
                                  screenshot_directory=folder/'view-added')
        elif case=='G1':
            # Body 2 must be reindexed from native execution slot 1 to slot 0.
            name='body_1';props=store.read(root)[0]['entities'][name]['properties']
            p=request(case,root,'remove-body-one','remove_particle',name,expected=props)
            decision=store.revise(save(folder/'remove.proposal.json',p))
            if decision['status']!='accepted':raise AssertionError(decision)
            ref=decision['reference'];new_names=['body_2']
            # Same previously accepted investigation must explicitly reject a
            # dangling reference to the deleted body. Presentation is corrected
            # by an explicit authored replacement, not silently modified.
            revised_view=presentation(case,src,new_names,'removed')
            blocked,blocked_summary=run_model(folder,store,ref,baseinv,ana,revised_view,'rejected-original-questions')
            if blocked_summary['status']!='rejected' or blocked_summary.get('code')!='wrong_role':
                raise AssertionError(('missing named particle was not refused',blocked_summary))
            inv=investigation(case,src,new_names,purpose='survivor-only')
            good,summ=run_model(folder,store,ref,inv,ana,revised_view,'removed-run')
            if not summ['execution_complete']:raise AssertionError(summ)
            outcomes['revisions'].append({'operation':'remove_particle','reference':ref,'id':name})
            outcomes['runs'].append({'reference':ref,'run':'rejected-original-questions','status':'rejected','code':'wrong_role'})
            outcomes['runs'].append({'reference':ref,'run':'removed-run','status':'complete'})
            if render:present_run(good,sample_index=src['samples']//2,
                                  screenshot_directory=folder/'view-removed')
        else:  # preselected static T1: shell dynamics remain unsupported
            name='hypothetical_probe'
            props={'mass_kg':1e-6,'charge_C':1e-7,
                'position_m':[2.5,.25,.4],'velocity_m_s':[0.,.15,0.]}
            p=request(case,root,'add-hypothetical','add_particle',name,particle=props)
            d=store.revise(save(folder/'add.proposal.json',p))
            if d['status']!='accepted':raise AssertionError(d)
            addref=d['reference'];names=[name]
            added,added_s=run_model(folder,store,addref,
                 investigation(case,src,names,purpose='static-added'),ana,
                 presentation(case,src,names,'static-added'),'static-added-run')
            if not added_s['execution_complete']:raise AssertionError(added_s)
            expected=store.read(addref)[0]['entities'][name]['properties']
            p=request(case,addref,'remove-hypothetical','remove_particle',name,expected=expected)
            d2=store.revise(save(folder/'remove.proposal.json',p))
            if d2['status']!='accepted':raise AssertionError(d2)
            remref=d2['reference']
            removed,removed_s=run_model(folder,store,remref,
                 investigation(case,src,[],purpose='static-removed'),ana,
                 presentation(case,src,[],'static-removed'),'static-removed-run')
            if not removed_s['execution_complete']:raise AssertionError(removed_s)
            outcomes['revisions'].extend([{'operation':'add_particle','reference':addref,'id':name},
                                         {'operation':'remove_particle','reference':remref,'id':name}])
            outcomes['runs'].extend([{'reference':addref,'run':'static-added-run','status':'complete'},
                                    {'reference':remref,'run':'static-removed-run','status':'complete'}])
            outcomes['meaning']='T1 is static; no shell/point trajectory is claimed or generated'
            if render:
                present_run(baseline,sample_index=0,screenshot_directory=folder/'view-root-static')
                present_run(removed,sample_index=0,screenshot_directory=folder/'view-removed-static')
        unmodified(store.path,retained_store)
        unmodified(baseline,retained_run)
        # Every accepted revision must derive from exactly the retained root or
        # its stated parent. Source identities always remain unchanged.
        source_records=store.read(root)[0]['entities']
        for item in outcomes['revisions']:
            newrev=store.read(item['reference'])[0]
            if newrev['source_order']!=info['sources']:
                raise AssertionError('source order changed')
            for s in info['sources']:
                if newrev['entities'][s]!=source_records[s]:
                    raise AssertionError('source properties or provenance changed')
        outcomes['baseline_preserved']=True
        report['cases'][case]=outcomes
    report['status']='complete'
    save(output/'qualification.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    print(encode(qualify(args.output,render=args.render)).decode(),end='')
