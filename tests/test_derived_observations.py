"""Bounded derived observation coverage: exact run, physical meanings, refusal."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from emfeeld.model_revisions import ModelStore, RevisionError, encode, put, sha256, decode
from emfeeld.model_runs import execute
from emfeeld.derived_observations import derive, inspect


def save(path,data):
    put(path,encode(data));return path


def source_case(tmp,*,kind='electric',mode='trajectory'):
    if kind=='electric':
        sources=[{'type':'uniform','field_N_C':[2.,0.,0.]}]
        particles=[{'mass_kg':1.,'charge_C':1.,'position_m':[0.,0.,0.], 'velocity_m_s':[0.,0.,0.]},
                   {'mass_kg':1.,'charge_C':-1.,'position_m':[1.,0.,0.], 'velocity_m_s':[0.,0.,0.]}]
    else:
        sources=[{'type':'uniform','field_m_s2':[2.,0.,0.]}]
        particles=[{'mass_kg':1.,'position_m':[0.,0.,0.], 'velocity_m_s':[0.,0.,0.]},
                   {'mass_kg':2.,'position_m':[1.,0.,0.], 'velocity_m_s':[0.,0.,0.]}]
    scene={'schema_version':1,'kind':kind,'title':'Derived complete run',
           'sources':sources,'particles':particles,'duration_s':2.,'samples':9,
           'bounds_m':[-5.,5.,-5.,5.,-5.,5.]}
    root=save(tmp/'scene.json',scene);raw=root.read_bytes()
    assignment={'import_version':1,'model_id':'derived-model','revision_id':'root',
                'source_sha256':sha256(raw),'source_ids':['background'],
                'particle_ids':['body_left','body_right'],
                'default_origin':{'origin':'illustrative_choice','reason':'Fixture','evidence':'Explicit test'},
                'interpretation':{'statement':'Two independent test bodies in one constant field',
                     'assumptions':['Fixed source and independent tests'],
                     'requirements':['fixed_prescribed_sources','independent_nonrelativistic_test_particles'],
                     'unresolved':[],'scenario_intent':'illustrative_exploration'}}
    store,ref=ModelStore.import_legacy(root,save(tmp/'assignment.json',assignment),tmp/'store')
    requests=[{'id':'field_a','type':'field','position_m':[0.,0.,0.]},
              {'id':'field_b','type':'field','position_m':[2.,0.,0.]},
              {'id':'potential_a','type':'potential','position_m':[0.,0.,0.]},
              {'id':'delta_v','type':'potential_difference','from_m':[0.,0.,0.],'to_m':[2.,0.,0.]}]
    if mode=='trajectory':
        for ident,body,index in [('left','body_left',8),('right','body_right',8),
                                  ('left_at_end','body_left',4),('left_speed','body_left',8),
                                  ('right_speed','body_right',8)]:
            requests.append({'id':ident,'type':'trajectory_sample', 'particle_id':body,
                             'quantity':'speed' if 'speed' in ident else 'position', 'sample_index':index})
    inv={'investigation_version':1,'id':'observations','model_id':ref['model_id'],'observations':requests}
    ana={'analysis_version':1,'id':'analysis','mode':mode}
    if mode=='trajectory':
        ana.update(duration_s=2.,samples=9,checks={'position_atol_m':1e-6,'velocity_atol_m_s':1e-7,
                        'rtol':1e-7,'max_normalized_energy_drift':1e-7})
    view={'presentation_version':1,'id':'display','bounds_m':scene['bounds_m'],
          'entity_order':['background','body_left','body_right']}
    paths=[save(tmp/f'{n}.json',v) for n,v in [('ref',ref),('inv',inv),('ana',ana),('view',view)]]
    result=execute(store.path,*paths,tmp/'sealed',run_id='sealed')
    assert result['execution_complete'],result
    return {'derived_version':1,'id':'math-questions','source_run_sha256':sha256((tmp/'sealed/run.json').read_bytes()),
            'observations':[]}


def ratio(ident,a,b,part_a='magnitude',part_b='magnitude'):
    return {'id':ident,'type':'ratio','numerator':{'id':a,'part':part_a},
            'denominator':{'id':b,'part':part_b}}


def separation(ident,a,b):
    return {'id':ident,'type':'separation','left_id':a,'right_id':b}


def run(tmp,spec,*,where='out'):
    return derive(save(tmp/(where+'.json'),spec),using=tmp/'sealed',output=tmp/where)


def hashes(folder):
    return {p.relative_to(folder).as_posix():sha256(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind,mode',[('electric','trajectory'),('gravity','trajectory'),('electric','static'),('gravity','static')])
def test_field_ratio_reuses_sealed_run_and_is_dimensionless(tmp_path,kind,mode):
    spec=source_case(tmp_path,kind=kind,mode=mode)
    spec['observations']=[ratio('field_ratio','field_a','field_b')]
    original=hashes(tmp_path/'sealed');store=hashes(tmp_path/'store')
    result=run(tmp_path,spec)
    assert result['status']=='complete'
    assert result['observations'][0]['value']==pytest.approx(1.)
    assert result['observations'][0]['unit']=='1'
    assert result['observations'][0]['error_bound'] is None
    assert inspect(tmp_path/'out',using=tmp_path/'sealed')==result
    assert hashes(tmp_path/'sealed')==original and hashes(tmp_path/'store')==store


@pytest.mark.parametrize('kind,expected',[('electric',7.),('gravity',1.)])
def test_same_time_separation_matches_independent_uniform_field_formula(tmp_path,kind,expected):
    spec=source_case(tmp_path,kind=kind)
    spec['observations']=[separation('distance','left','right')]
    result=run(tmp_path,spec)
    item=result['observations'][0]
    assert result['status']=='complete'
    assert item['unit']=='m' and item['time_s']==2.
    assert item['value']==pytest.approx(expected,abs=1e-9)
    assert [p['particle_index'] for p in item['operands']]==[0,1]
    assert inspect(tmp_path/'out',using=tmp_path/'sealed')==result


def test_missing_and_mismatched_measurements_are_explicit_partial(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[ratio('good','field_a','field_b'),
        separation('wrong_time','left','left_at_end'),
        separation('same_particle','left','left_at_end'),
        ratio('missing','field_a','absent'),
        ratio('wrong_kind','potential_a','delta_v','value','value'),
        ratio('different_context','left_speed','field_a','value','magnitude')]
    result=run(tmp_path,spec)
    assert result['status']=='partial'
    assert [x['status'] for x in result['observations']]==['ok']+['unavailable']*5
    assert [x['code'] for x in result['observations'][1:]]==[
        'same_particle','same_particle','unknown_operand','operand_unavailable','incompatible_units']


def test_different_time_between_distinct_particles(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[separation('different','right','left_at_end')]
    report=run(tmp_path,spec)
    assert report['status']=='partial' and report['observations'][0]['code']=='different_saved_times'


def test_unphysical_absolute_potential_ratio_rejected_in_electric_and_gravity(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[ratio('gauge-dependent','potential_a','delta_v','value','value')]
    report=run(tmp_path,spec)
    assert report['observations'][0]['code']=='operand_unavailable'


@pytest.mark.parametrize('mutation',[lambda a:a.update(derived_version=True),
 lambda a:a.update(source_run_sha256='bogus'),
 lambda a:a.update(observations=[]),
 lambda a:a.update(observations=[ratio('a','field_a','field_b')]*2),
 lambda a:a.update(observations=[{'id':'wrong','type':'untrusted_expr','code':'1+1'}]),
 lambda a:a.update(observations=[{'id':'wrong','type':'ratio','numerator':{'id':'field_a','part':'foo'},'denominator':{'id':'field_b','part':'magnitude'}}])])
def test_invalid_request_fails_before_output(mutation,tmp_path):
    spec=source_case(tmp_path,mode='static');mutation(spec)
    old=hashes(tmp_path/'sealed')
    with pytest.raises((RevisionError,ValueError)):
        run(tmp_path,spec)
    assert not (tmp_path/'out').exists()
    assert hashes(tmp_path/'sealed')==old


def test_detect_tampering_and_output_collision(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[ratio('valid','field_a','field_b')]
    run(tmp_path,spec)
    with pytest.raises(FileExistsError):run(tmp_path,spec)
    (tmp_path/'out/result.json').write_bytes((tmp_path/'out/result.json').read_bytes()+b' ')
    with pytest.raises(RevisionError,match='derived output changed'):
        inspect(tmp_path/'out',using=tmp_path/'sealed')


def test_detect_tampered_native_data(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[separation('valid','left','right')]
    request=save(tmp_path/'req.json',spec)
    (tmp_path/'sealed/native/result.json').write_bytes((tmp_path/'sealed/native/result.json').read_bytes()+b' ')
    with pytest.raises(RevisionError,match='integrity|inventory'):
        derive(request,using=tmp_path/'sealed',output=tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_zero_speed_denominator_and_valid_speed_ratio(tmp_path):
    spec=source_case(tmp_path)
    results=decode((tmp_path/'sealed/native/result.json').read_bytes())['results']
    # Input metadata are obtained from independently executed native samples.
    all_speeds=[r for r in results if r['type']=='trajectory_sample' and r.get('quantity')=='speed']
    assert len(all_speeds)==2 and all(r['value']>0 for r in all_speeds)
    spec['observations']=[ratio('speed','left_speed','right_speed','value','value')]
    report=run(tmp_path,spec)
    assert report['status']=='complete'
    assert report['observations'][0]['value']==pytest.approx(1.)
    assert report['observations'][0]['time_s']==2.


def test_zero_denominator_rejected_even_with_successful_operands():
    from emfeeld.derived_observations import _ratio
    indexed={
       'a':{'type':'potential_difference','status':'ok','unit':'V','value':2.},
       'b':{'type':'potential_difference','status':'ok','unit':'V','value':0.}}
    row=_ratio(ratio('bad','a','b','value','value'),indexed)
    assert row['status']=='unavailable' and row['code']=='zero_denominator' and row['value'] is None


def test_ratio_rejects_nonfinite_and_failed_authored_check():
    from emfeeld.derived_observations import _ratio
    idx={'a':{'type':'field','unit':'N/C','status':'ok','magnitude':float('inf')},
         'b':{'type':'field','unit':'N/C','status':'ok','magnitude':3.}}
    row=_ratio(ratio('bad','a','b'),idx)
    assert row['code']=='operand_unavailable'
    idx['a']['magnitude']=1.
    idx['a']['check']={'passed':False}
    assert _ratio(ratio('bad','a','b'),idx)['code']=='operand_unavailable'


def test_ratio_rejects_overflow_and_different_saved_times():
    from emfeeld.derived_observations import _ratio
    idx={'a':{'type':'potential_difference','unit':'V','status':'ok','value':1e308},
         'b':{'type':'potential_difference','unit':'V','status':'ok','value':1e-308}}
    assert _ratio(ratio('bad','a','b','value','value'),idx)['code']=='numeric_range'
    idx={'a':{'type':'trajectory_sample','quantity':'speed','status':'ok','unit':'m/s','value':1.,'time_s':1.,'sample_index':3},
         'b':{'type':'trajectory_sample','quantity':'speed','status':'ok','unit':'m/s','value':2.,'time_s':2.,'sample_index':4}}
    assert _ratio(ratio('different','a','b','value','value'),idx)['code']=='different_saved_times'


def test_position_bad_shape_and_same_particle_are_explicitly_unavailable():
    from emfeeld.derived_observations import _separation
    row={'type':'trajectory_sample','quantity':'position','status':'ok','unit':'m','value':[0.,0.,0.],
         'particle_index':0,'time_s':1.,'sample_index':5}
    idx={'a':row,'b':{**row,'value':[1.,0.,0.]}}
    assert _separation(separation('bad','a','b'),idx)['code']=='same_particle'
    idx['b']={**idx['b'],'particle_index':1,'value':[1.,2.]}
    assert _separation(separation('bad','a','b'),idx)['code']=='operand_unavailable'


def test_separation_overflow_does_not_emit_infinite_measurement():
    from emfeeld.derived_observations import _separation
    row={'type':'trajectory_sample','quantity':'position','status':'ok','unit':'m','value':[1e308,0.,0.],
         'particle_index':0,'time_s':1.,'sample_index':5}
    idx={'a':row,'b':{**row,'value':[-1e308,0.,0.],'particle_index':1}}
    assert _separation(separation('bad','a','b'),idx)['code']=='numeric_range'


def test_missing_actual_saved_time_is_not_reported_as_valid():
    from emfeeld.derived_observations import _ratio, _separation
    row={'type':'trajectory_sample','quantity':'position','unit':'m','status':'ok',
         'particle_index':0,'value':[0.,0.,0.],'sample_index':3}
    row2={**row,'particle_index':1,'value':[1.,0.,0.]}
    assert _separation(separation('bad','a','b'),{'a':row,'b':row2})['code']=='invalid_saved_time'
    speed={'type':'trajectory_sample','quantity':'speed','unit':'m/s','status':'ok',
           'value':1.,'sample_index':3}
    assert _ratio(ratio('bad','a','b','value','value'),{'a':speed,'b':speed})['code']=='invalid_saved_time'


def test_request_exact_bytes_are_bound_by_hash(tmp_path):
    spec=source_case(tmp_path)
    spec['observations']=[ratio('valid','field_a','field_b')]
    result=run(tmp_path,spec)
    assert result['request_sha256']==sha256((tmp_path/'out/request.json').read_bytes())
    assert inspect(tmp_path/'out',using=tmp_path/'sealed')==result
