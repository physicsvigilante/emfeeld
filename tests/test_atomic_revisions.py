"""Adversarial V3 atomic model construction and native execution semantics."""
from copy import deepcopy
import json

import pytest

from emfeeld import model_runs
from emfeeld.model_revisions import encode
from test_model_revisions import (
    imported, base_scene, revise, execute, proposal as v1,
    computed_receipt, write,
)
from test_structural_revisions import addition as v2_source
from test_particle_revisions import addition as v2_particle


ORIGIN = {
    'origin': 'illustrative_choice',
    'reason': 'Explicit alternative teacher hypothesis',
    'evidence': 'V3 contract qualification fixture, not source-given',
}


def member(operation, target, *, role='source', **payload):
    categories = {
        'replace_property': 'component_property',
        'add_source': 'structural_change',
        'remove_source': 'structural_change',
        'add_particle': 'structural_change',
        'remove_particle': 'structural_change',
    }
    return {'operation': operation, 'category': categories[operation],
            'target_id': target, 'expected_role': role,
            'provenance': deepcopy(ORIGIN), **payload}


def replace(target, old, new, *, prop='charge_C', role='source', category='component_property'):
    p = member('replace_property', target, role=role, property=prop,
               expected_value=old, value=new)
    p['category'] = category
    return p


def add_source(target='extra', *, source=None):
    return member('add_source', target,
                  source=source or {'type': 'uniform', 'field_N_C': [0, 0, .1]})


def add_particle(target='other'):
    return member('add_particle', target, role='particle', particle={
        'mass_kg': 2e-6, 'charge_C': 3e-7,
        'position_m': [.4, -.2, .1], 'velocity_m_s': [.02, -.04, .03],
    })


def remove(store, ref, target, role):
    row = store.read(ref)[0]['entities'][target]
    return member('remove_' + role, target, role=role,
                  **{'expected_' + role: deepcopy(row['properties'])})


def atomic(ref, members, ident='atomic'):
    return {
        'proposal_version': 3, 'proposal_id': ident, 'revision_id': ident,
        'parent': deepcopy(ref), 'category': 'atomic_change',
        'scenario_intent': 'teacher_hypothesis', 'changes': deepcopy(members),
    }


def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob('*') if p.is_file()}


def test_two_property_changes_publish_one_descendant_and_seal_native_run(tmp_path):
    store, root = imported(tmp_path)
    original = files(store.path)
    status, baseline = execute(tmp_path, store, root, mode='static', name='baseline')
    assert status['execution_complete']
    original_run = files(baseline)
    parts = [replace('left', -1e-9, -3e-9),
             replace('right', -2e-9, -4e-9)]
    p = atomic(root, parts)
    outcome = revise(tmp_path, store, p)
    assert outcome['status'] == 'accepted' and outcome['numerical_work'] == 'not_run'
    rev, _ = store.read(outcome['reference'])
    assert rev['parent'] == root and rev['operation'] == p
    assert rev['source_order'] == ['left', 'right']
    assert rev['particle_order'] == ['probe']
    assert rev['entities']['probe'] == store.read(root)[0]['entities']['probe']
    assert len(list((store.path/'revisions').iterdir())) == 2
    for path, value in original.items():
        assert (store.path/path).read_bytes() == value
    assert files(baseline) == original_run
    run, output = execute(tmp_path, store, outcome['reference'], mode='static', name='child-run')
    assert run['execution_complete']
    model_runs.inspect_run(output, expected_reference=outcome['reference'])


def test_atomic_source_replacement_preserves_survivors_and_append_order(tmp_path):
    store, root = imported(tmp_path)
    p = atomic(root, [
        remove(store, root, 'left', 'source'),
        add_source('replacement'),
    ])
    d = revise(tmp_path, store, p)
    assert d['status'] == 'accepted'
    snap = store.read(d['reference'])[0]
    assert snap['source_order'] == ['right', 'replacement']
    assert snap['particle_order'] == ['probe']
    assert snap['entities']['right'] == store.read(root)[0]['entities']['right']
    assert snap['entities']['replacement']['properties']['origin_m'] == [0, 0, 0]
    assert snap['entities']['replacement']['provenance']['origin_m']['origin'] == 'source_convention'
    assert len(list((store.path/'revisions').iterdir())) == 2


def test_last_source_can_be_replaced_but_not_removed_without_another_source(tmp_path):
    scene = base_scene()
    scene['sources'] = scene['sources'][:1]
    store, root = imported(tmp_path, scene, mutate=lambda x: x.update(source_ids=['left']))
    good = atomic(root, [remove(store, root, 'left', 'source'), add_source('new')])
    d = revise(tmp_path, store, good)
    assert d['status'] == 'accepted'
    assert store.read(d['reference'])[0]['source_order'] == ['new']
    # A two-member transaction still cannot leave an empty source assembly.
    bad = atomic(root, [remove(store, root, 'left', 'source'),
                        replace('probe', 1e-6, 2e-6, prop='mass_kg', role='particle')],
                 ident='bad-final-source')
    d = revise(tmp_path, store, bad)
    assert d['status'] == 'rejected' and d['code'] == 'last_source'
    assert len(list((store.path/'revisions').iterdir())) == 2


def test_late_member_failure_creates_no_accepted_partial_revision(tmp_path):
    store, root = imported(tmp_path)
    original = files(store.path)
    p = atomic(root, [replace('left', -1e-9, -3e-9),
                      replace('right', -2e-9, -4e-9, prop='mass_kg')])
    d = revise(tmp_path, store, p)
    assert d['status'] == 'rejected'
    assert len(list((store.path/'revisions').iterdir())) == 1
    assert not (store.path/'structural-write.lock').exists()
    for path, value in original.items():
        assert (store.path/path).read_bytes() == value
    attempts = list((store.path/'proposals').glob('*/decision.json'))
    assert len(attempts) == 1
    assert json.loads(attempts[0].read_text())['status'] == 'rejected'


@pytest.mark.parametrize('number', [0, 1, 5])
def test_member_count_fails_closed(tmp_path, number):
    store, root = imported(tmp_path)
    p = atomic(root, [add_source('new-' + str(i)) for i in range(number)])
    d = revise(tmp_path, store, p)
    assert d['status'] == 'rejected' and d['code'] == 'unsupported_change'
    assert len(list((store.path/'revisions').iterdir())) == 1


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(proposal_version=True),
    lambda p: p.update(proposal_version=3.0),
    lambda p: p.update(category='structural_change'),
    lambda p: p.update(extra=True),
    lambda p: p['changes'][0].update(extra=True),
    lambda p: p['changes'][0].update(operation='source_replace'),
    lambda p: p['changes'][0].update(expected_role='particle'),
    lambda p: p['changes'][0].update(expected_value=True),
    lambda p: p['changes'][0].update(value=False),
    lambda p: p['changes'][0].update(value=float('nan')),
    lambda p: p['changes'][0]['provenance'].update(origin='computed_result'),
    lambda p: p['changes'][0]['provenance'].update(origin='unknown'),
    lambda p: p['changes'][0].update(property='type'),
    lambda p: p['changes'][0].update(category='boundary_condition'),
    lambda p: p['changes'][0].update(value=-1e-9),
    lambda p: p['changes'][1].update(target_id='left'),
])
def test_invalid_requests_are_rejected_without_partial_descendant(tmp_path, mutation):
    store, root = imported(tmp_path)
    p = atomic(root, [replace('left', -1e-9, -3e-9),
                      replace('right', -2e-9, -4e-9)])
    mutation(p)
    # Nonfinite values cannot be encoded by the author's safe fixture writer.
    if p['changes'][0].get('value') != p['changes'][0].get('value'):
        source = tmp_path/'bad-nonfinite.json'
        source.write_text(json.dumps(p, allow_nan=True))
        # This is malformed JSON under the strict authoring contract, so
        # admission stops before an identifiable proposal attempt is created.
        with pytest.raises(ValueError, match='nonfinite'):
            store.revise(source)
    else:
        d = revise(tmp_path, store, p)
        # A V3 composite cannot be labeled wholly no-op when another member
        # requests a real change. Unlike unchanged V1 single-property edits,
        # a no-op member rejects the entire attempted transaction.
        assert d['status'] == 'rejected'
        if p['changes'][0].get('value') == -1e-9 and p['changes'][0]['operation'] == 'replace_property':
            assert d['code'] == 'no_op_member'
    assert len(list((store.path/'revisions').iterdir())) == 1


def test_identity_reuse_after_removed_ancestor_and_sibling_fails(tmp_path):
    store, root = imported(tmp_path)
    a = revise(tmp_path, store, atomic(root, [add_source('once'), add_particle('body3')], ident='first'))
    assert a['status'] == 'accepted'
    b = revise(tmp_path, store, atomic(a['reference'], [
        remove(store, a['reference'], 'once', 'source'),
        remove(store, a['reference'], 'body3', 'particle')], ident='second'))
    assert b['status'] == 'accepted'
    for parent, ident in ((root, 'sibling'), (b['reference'], 'descendant')):
        d = revise(tmp_path, store, atomic(parent, [add_source('once'), add_particle('body4')], ident=ident))
        assert d['code'] == 'identity_conflict'
    assert len(list((store.path/'revisions').iterdir())) == 3


def test_gravity_new_particle_default_and_source_mass_change(tmp_path):
    scene = base_scene()
    scene['kind'] = 'gravity'
    for source in scene['sources']:
        source.pop('charge_C')
        source['mass_kg'] = 2e9
    scene['particles'][0].pop('charge_C')
    store, root = imported(tmp_path, scene)
    particle = add_particle('new-gravity')
    particle['particle'].pop('charge_C')
    d = revise(tmp_path, store, atomic(root, [
        replace('left', 2e9, 2.5e9, prop='mass_kg'), particle]))
    assert d['status'] == 'accepted'
    rev = store.read(d['reference'])[0]
    assert rev['particle_order'] == ['probe', 'new-gravity']
    assert rev['entities']['new-gravity']['properties']['charge_C'] == 0
    assert rev['entities']['new-gravity']['provenance']['charge_C']['origin'] == 'source_convention'


def test_computed_input_dependency_refusal_and_staleness(tmp_path):
    def dependencies(spec):
        spec['computed_inputs'] = [{
            'target_id': 'probe', 'property': 'velocity_m_s',
            'provenance': {'origin': 'computed_result',
                           'reason': 'Explicit calculation', 'evidence': 'Test receipt'},
            'receipt': computed_receipt(),
        }]
    store, root = imported(tmp_path, mutate=dependencies)
    original = store.read(root)[1]
    refused = revise(tmp_path, store, atomic(root, [
        remove(store, root, 'left', 'source'), add_source('new')], ident='dependent'))
    assert refused['code'] == 'dependent_source'
    changed = revise(tmp_path, store, atomic(root, [
        replace('left', -1e-9, -3e-9),
        replace('right', -2e-9, -4e-9)], ident='changed'))
    assert changed['status'] == 'accepted'
    result = store.read(changed['reference'])[0]
    assert result['stale_dependencies'] == [{'target_id': 'probe', 'property': 'velocity_m_s'}]
    static, _ = execute(tmp_path, store, changed['reference'], mode='static', name='static-valid')
    dynamic, _ = execute(tmp_path, store, changed['reference'], mode='trajectory', name='motion-refused')
    assert static['execution_complete'] and dynamic['code'] == 'stale_computation'
    assert store.read(root)[1] == original


def test_source_membership_invalidates_all_surviving_computed_receipts(tmp_path):
    def dependencies(spec):
        spec['computed_inputs'] = [{
            'target_id': 'probe', 'property': 'velocity_m_s',
            'provenance': {'origin': 'computed_result',
                           'reason': 'Explicit calculation', 'evidence': 'Test receipt'},
            'receipt': computed_receipt(),
        }]
    store, root = imported(tmp_path, mutate=dependencies)
    d = revise(tmp_path, store, atomic(root, [
        add_source('new-field'), add_particle('second')]))
    assert d['status'] == 'accepted'
    assert store.read(d['reference'])[0]['stale_dependencies'] == [
        {'target_id': 'probe', 'property': 'velocity_m_s'}]


def test_particle_only_membership_keeps_unrelated_computation_current(tmp_path):
    def dependencies(spec):
        spec['computed_inputs'] = [{
            'target_id': 'probe', 'property': 'velocity_m_s',
            'provenance': {'origin': 'computed_result',
                           'reason': 'Explicit calculation', 'evidence': 'Test receipt'},
            'receipt': computed_receipt(),
        }]
    store, root = imported(tmp_path, mutate=dependencies)
    d = revise(tmp_path, store, atomic(root, [
        add_particle('second'), add_particle('third')]))
    assert d['status'] == 'accepted'
    assert store.read(d['reference'])[0]['stale_dependencies'] == []


def test_v1_v2_remain_independent_and_no_cross_revision_reuse(tmp_path):
    store, root = imported(tmp_path)
    a = revise(tmp_path, store, v1(root, ident='v1', rev='v1'))
    b = revise(tmp_path, store, v2_source(root, ident='v2', target='v2source'))
    c = revise(tmp_path, store, v2_particle(root, ident='v2particle', target='v2body'))
    assert all(d['status'] == 'accepted' for d in (a, b, c))
    assert len(list((store.path/'revisions').iterdir())) == 4
    p = atomic(root, [add_source('v2source'), add_particle('fresh')])
    d = revise(tmp_path, store, p)
    assert d['code'] == 'identity_conflict'


def test_four_member_transaction_reindexes_named_body_and_refuses_old_request(tmp_path):
    store, root = imported(tmp_path)
    old = store.read(root)[0]
    children = [
        replace('right', -2e-9, -4e-9),
        remove(store, root, 'probe', 'particle'),
        add_source('added-field'),
        add_particle('replacement-body'),
    ]
    d = revise(tmp_path, store, atomic(root, children))
    assert d['status'] == 'accepted'
    rev = store.read(d['reference'])[0]
    assert rev['particle_order'] == ['replacement-body']
    assert rev['source_order'] == ['left', 'right', 'added-field']
    assert rev['entities']['left'] == old['entities']['left']
    # A stale investigation referencing removed probe is never redirected.
    old_request, _ = execute(tmp_path, store, d['reference'], name='old-body')
    assert old_request['status'] == 'rejected' and old_request['code'] == 'wrong_role'
    def new_request(inv, ana, pres):
        inv['observations'][-1]['particle_id'] = 'replacement-body'
        pres['entity_order'] = ['left', 'right', 'added-field', 'replacement-body']
    fresh, out = execute(tmp_path, store, d['reference'], change=new_request, name='new-body')
    assert fresh['execution_complete']
    assert json.loads((out/'mapping.json').read_text())['particles'] == {'replacement-body':0}
    model_runs.inspect_run(out, expected_reference=d['reference'])


def test_removal_of_computed_dependent_and_its_source_leaves_no_dangling_receipt(tmp_path):
    def dependencies(spec):
        spec['computed_inputs'] = [{
            'target_id': 'probe', 'property': 'velocity_m_s',
            'provenance': {'origin': 'computed_result',
                           'reason': 'Explicit calculation', 'evidence': 'Test receipt'},
            'receipt': computed_receipt(),
        }]
    store, root = imported(tmp_path, mutate=dependencies)
    original = store.read(root)[1]
    d = revise(tmp_path, store, atomic(root, [
        remove(store, root, 'probe', 'particle'),
        remove(store, root, 'left', 'source'),
    ]))
    assert d['status'] == 'accepted'
    child = store.read(d['reference'])[0]
    assert child['source_order'] == ['right'] and child['particle_order'] == []
    assert child['stale_dependencies'] == []
    assert store.read(root)[1] == original


def test_atomic_lock_and_incomplete_history_fail_closed(tmp_path):
    store, root = imported(tmp_path)
    p = atomic(root, [add_source('new'), add_particle('newbody')])
    lock = store.path/'structural-write.lock'
    lock.write_text('other writer')
    refused = revise(tmp_path, store, p)
    assert refused['status'] == 'rejected' and refused['code'] == 'store_busy'
    assert lock.read_text() == 'other writer'
    lock.unlink()
    # An interrupted revision directory blocks subsequent atomic identity admission.
    incomplete = store._directory('interrupted')
    incomplete.mkdir()
    next_p = atomic(root, [add_source('second'), add_particle('secondbody')], ident='another')
    blocked = revise(tmp_path, store, next_p)
    assert blocked['code'] == 'incomplete_history'
    assert incomplete.exists()
    assert len(list((store.path/'revisions').glob('*/reference.json'))) == 1


def test_duplicate_target_and_stale_parent_preserve_original_bytes(tmp_path):
    store, root = imported(tmp_path)
    baseline = files(store.path)
    repeated = atomic(root, [
        replace('left', -1e-9, -3e-9),
        replace('left', -1e-9, -4e-9, prop='charge_C')])
    first = revise(tmp_path, store, repeated)
    assert first['code'] == 'duplicate_target'
    stale = atomic(root, [add_source('external'), add_particle('external-body')], ident='stale')
    stale['parent']['sha256'] = '0'*64
    second = revise(tmp_path, store, stale)
    assert second['code'] == 'stale_parent'
    assert len(list((store.path/'revisions').iterdir())) == 1
    for name, raw in baseline.items():
        assert (store.path/name).read_bytes() == raw
