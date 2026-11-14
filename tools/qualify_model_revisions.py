"""Execute data-only electric/gravity examples with one root and two named hypotheses.

This driver supplies exact parent references, not physics answers. It does not
modify the engine or original examples. See verification/check_model_revision_runs.py.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from emfeeld.model_revisions import ModelStore, decode, encode, put
from emfeeld.model_runs import execute, compare_runs, present_run


def qualify(output, *, render=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    examples=ROOT/'examples/model_revisions'
    summary={'kind':'synthetic teaching workflow qualification, not a blind benchmark', 'models':{}}
    for kind,source in [('electric','examples/authoring/discovery_electric.json'),('gravity','examples/ideal_sun.json')]:
        folder=output/kind;folder.mkdir()
        store,root=ModelStore.import_legacy(ROOT/source,examples/(kind+'_import.json'),folder/'model')
        put(folder/'root.reference.json',encode(root));refs={'root':root}
        for proposal in decode((examples/(kind+'_hypotheses.json')).read_bytes())['changes']:
            proposal['parent']=root
            path=folder/(proposal['proposal_id']+'.proposal.json');put(path,encode(proposal))
            decision=store.revise(path)
            if decision['status']!='accepted':raise RuntimeError(str(decision))
            ref=decision['reference'];refs[ref['revision_id']]=ref
            put(folder/(ref['revision_id']+'.reference.json'),encode(ref))
        results={}
        for revision,ref in refs.items():
            for mode in ('static','motion'):
                run_id=revision+'-'+mode
                result=execute(store.path,folder/(revision+'.reference.json'),examples/(kind+'_'+mode+'.json'),
                    examples/('static_analysis.json' if mode=='static' else kind+'_analysis.json'),
                    examples/(kind+'_presentation.json'),folder/run_id,run_id=run_id)
                results[run_id]=result
                if not result['execution_complete']:raise RuntimeError(f'{kind}/{run_id}: {result}')
                if render and mode=='motion':
                    samples=decode((examples/(kind+'_analysis.json')).read_bytes())['samples']
                    present_run(folder/run_id,sample_index=samples//2,screenshot_directory=folder/(revision+'-presentation'))
        for child in ('source-hypothesis','launch-hypothesis'):
            put(folder/(child+'.comparison.json'),encode(compare_runs(folder/'root-motion',folder/(child+'-motion'))))
        summary['models'][kind]={'revisions':refs,'runs':{k:v['status'] for k,v in results.items()},
                                'source_model_reauthored':False,'rendered_frames':3 if render else 0}
    put(output/'qualification.json',encode(summary))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--render',action='store_true')
    a=p.parse_args();print(json.dumps(qualify(a.output,render=a.render),indent=2))
