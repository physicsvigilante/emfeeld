"""Exercise the installed native apply command using existing teaching fixtures.

No new physics or precomputed answers. Compatible immutable run copies let the
unchanged separate harmonic/Kepler checker assess this command's actual outputs.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from emfeeld.model_revisions import ModelStore, decode, encode, put
from emfeeld.model_runs import execute, inspect_run


def qualify(output, *, render=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    examples=ROOT/'examples/model_revisions'
    summary={'meaning':'native-command integration using exposed illustrative fixtures; not independent review', 'models':{}}
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    for kind,source in [('electric','examples/authoring/discovery_electric.json'),('gravity','examples/ideal_sun.json')]:
        folder=output/kind;folder.mkdir()
        store,root=ModelStore.import_legacy(ROOT/source,examples/(kind+'_import.json'),folder/'model')
        root_path=folder/'root.reference.json';put(root_path,encode(root))
        view=examples/(kind+'_presentation.json'); inv=examples/(kind+'_motion.json'); analysis=examples/(kind+'_analysis.json')
        for mode in ('motion','static'):
            result=execute(store.path,root_path,examples/(kind+'_'+mode+'.json'),
                analysis if mode=='motion' else examples/'static_analysis.json',view,folder/('root-'+mode),run_id='root-'+mode)
            if not result['execution_complete']:raise RuntimeError(str(result))
        original=store.read(root)[1]; attempts={}
        for item in decode((examples/(kind+'_hypotheses.json')).read_bytes())['changes']:
            item['parent']=root
            proposal=folder/(item['proposal_id']+'.proposal.json');put(proposal,encode(item))
            attempt=folder/(item['revision_id']+'-apply')
            command=[sys.executable,'-m','emfeeld','model','apply',str(proposal),'--store',str(store.path),
                '--using',str(folder/'root-motion'),'--output',str(attempt),'--run-id',item['revision_id']+'-motion']
            if render:
                sample=decode(analysis.read_bytes())['samples']//2
                command+=['--render','--sample-index',str(sample)]
            completed=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
            put(folder/(item['revision_id']+'.stdout.txt'),completed.stdout.encode())
            put(folder/(item['revision_id']+'.stderr.txt'),completed.stderr.encode())
            if completed.returncode:raise RuntimeError(f'Native command failed: {completed.returncode}: {completed.stderr}')
            outcome=decode((attempt/'outcome.json').read_bytes())
            assert outcome['status']=='complete'
            assert inspect_run(attempt/'run')[0]['reference']==outcome['decision']['reference']
            # Byte-exact copy, NOT another calculation or replacement numerical result.
            shutil.copytree(attempt/'run',folder/(item['revision_id']+'-motion'))
            static=execute(store.path,attempt/'reference.json',examples/(kind+'_static.json'),
                examples/'static_analysis.json',view,folder/(item['revision_id']+'-static'),run_id=item['revision_id']+'-static')
            assert static['execution_complete'] and store.read(root)[1]==original
            attempts[item['revision_id']]={'status':outcome['status'],'reference':outcome['decision']['reference'],
                                           'presentation':outcome['presentation']['status']}
        summary['models'][kind]={'root':root,'attempts':attempts,'original_bytes_unchanged':True}
    put(output/'qualification.json',encode(summary))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--render',action='store_true')
    a=p.parse_args();print(json.dumps(qualify(a.output,render=a.render),indent=2))
