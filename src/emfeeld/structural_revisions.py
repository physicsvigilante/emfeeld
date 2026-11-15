"""Bounded source insertion/removal in the existing immutable model store.

No laws, solver, result reuse, hidden observations or implicit source replacement.
Version-2 proposals use the unchanged model-format-1 snapshot and scene parser.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

from .model_revisions import (DEFAULTS, INTENTS, RevisionError, _origin, decode,
    encode, exact_keys, identifier, validate_snapshot)
from .scene import source_from_dict, source_keys


@contextmanager
def _structural_writer(store):
    """Fail closed on concurrent/crashed structural writes, never steal a lock."""
    lock = store.path / 'structural-write.lock'
    try:
        handle = lock.open('xb')
    except FileExistsError as exc:
        raise RevisionError('store_busy',
            'structural write lock exists; inspect an interrupted attempt before recovery') from exc
    try:
        with handle:
            handle.write(b'Structural source edit in progress. Do not remove while writer is active.\n')
        yield
    finally:
        lock.unlink()


def _known_identities(store):
    """Inspect all accepted sibling/ancestor snapshots; IDs are not reusable."""
    revisions = {}
    known = set()
    for folder in sorted((store.path / 'revisions').iterdir()):
        if not folder.is_dir() or not (folder / 'reference.json').is_file():
            raise RevisionError('incomplete_history',
                'incomplete revision history blocks structural admission; preserve and inspect it')
        ref = decode((folder / 'reference.json').read_bytes())
        value, _ = store.read(ref)
        if folder != store._directory(ref['revision_id']):
            raise RevisionError('identity_conflict', 'revision folder does not match its reference')
        revisions[ref['revision_id']] = (ref, value)
        known.update(value['entities'])
    root = store.info['root']
    if root['revision_id'] not in revisions or revisions[root['revision_id']][0] != root:
        raise RevisionError('incomplete_history', 'exact root revision is missing')
    # A disconnected or cyclic history cannot establish whether a source ID is new.
    connected = set()
    for start in revisions:
        visiting = set()
        cursor = start
        while cursor not in connected:
            if cursor in visiting:
                raise RevisionError('incomplete_history', 'cyclic model ancestry')
            visiting.add(cursor)
            ref, value = revisions[cursor]
            parent = value['parent']
            if parent is None:
                if ref != root:
                    raise RevisionError('incomplete_history', 'revision is disconnected from the root')
                break
            if parent['revision_id'] not in revisions or revisions[parent['revision_id']][0] != parent:
                raise RevisionError('incomplete_history', 'missing or mismatched exact ancestor')
            cursor = parent['revision_id']
        connected.update(visiting)
    return known


def _candidate(parent, proposal, reference, known):
    operation = proposal.get('operation')
    if operation not in ('add_source', 'remove_source'):
        raise RevisionError('unsupported_change', 'structural V1 supports only add_source and remove_source')
    payload = 'source' if operation == 'add_source' else 'expected_source'
    exact_keys(proposal, ('proposal_version', 'proposal_id', 'parent', 'revision_id',
        'category', 'operation', 'target_id', 'expected_role', 'scenario_intent', 'provenance', payload))
    if type(proposal['proposal_version']) is not int or proposal['proposal_version'] != 2:
        raise ValueError('structural source operations require proposal_version 2')
    for key in ('proposal_id', 'revision_id', 'target_id'):
        identifier(proposal[key])
    if proposal['category'] != 'structural_change' or proposal['expected_role'] != 'source':
        raise RevisionError('unsupported_change', 'only explicit structural source changes are supported')
    if proposal['parent'] != reference:
        raise RevisionError('stale_parent', 'structural proposal must pin its exact parent')
    if proposal['revision_id'] == parent['revision_id']:
        raise RevisionError('identity_conflict', 'a revision cannot replace its parent')
    if proposal['scenario_intent'] not in INTENTS:
        raise ValueError('unknown scenario intent')
    origin = _origin(proposal['provenance'])
    if origin['origin'] in ('computed_result', 'unknown'):
        raise RevisionError('unsupported_provenance',
            'structural V1 requires explicit literal source data, not unknown or unverified computed inputs')
    result = deepcopy(parent)
    result.update(revision_id=proposal['revision_id'], parent=deepcopy(reference), operation=deepcopy(proposal))
    result['interpretation']['scenario_intent'] = proposal['scenario_intent']
    target = proposal['target_id']
    if operation == 'add_source':
        if target in known:
            raise RevisionError('identity_conflict',
                'source ID was already used in this model store, including removed entities and siblings')
        props = deepcopy(proposal['source'])
        source_from_dict(parent['kind'], props)  # inherited units/domain/geometry rules
        provenance = {key: deepcopy(origin) for key in props}
        for key in source_keys(parent['kind'], props['type'])[1]:
            if key not in props:
                props[key] = deepcopy(DEFAULTS[key])
                provenance[key] = {'origin': 'source_convention',
                    'reason': 'Expanded existing scene-v1 parser default, not a source given',
                    'evidence': f'scene-v1 default for source.{key}'}
        result['entities'][target] = {'role': 'source', 'properties': props, 'provenance': provenance}
        result['source_order'].append(target)
    else:
        if target not in parent['entities']:
            raise RevisionError('unknown_target', 'source does not exist in the pinned parent')
        row = parent['entities'][target]
        if row['role'] != 'source':
            raise RevisionError('wrong_role', 'source removal cannot remove a particle')
        if encode(proposal['expected_source']) != encode(row['properties']):
            raise RevisionError('old_value_mismatch', 'expected_source must exactly match canonical parent properties')
        if len(parent['source_order']) == 1:
            raise RevisionError('last_source', 'removing the last source is outside the existing scene contract')
        dependents = []
        for key, entity in parent['entities'].items():
            if key == target:
                continue
            for field, record in entity['provenance'].items():
                if 'computation' in record and any(d['target_id'] == target
                        for d in record['computation']['receipt']['inputs']):
                    dependents.append(f'{key}.{field}')
        if dependents:
            raise RevisionError('dependent_source',
                f'removal would leave dangling computation inputs: {sorted(dependents)}; no automatic rebinding')
        del result['entities'][target]
        result['source_order'].remove(target)
    # Old receipts describe named scalar dependencies, not source-set membership.
    # Conservatively invalidate ALL retained computed properties, without altering
    # a recorded value/receipt or claiming automatic recomputation.
    stale = {(x['target_id'], x['property']) for x in parent['stale_dependencies']
             if x['target_id'] in result['entities']}
    stale.update((key, field) for key, entity in result['entities'].items()
                 for field, record in entity['provenance'].items() if 'computation' in record)
    result['stale_dependencies'] = [{'target_id': key, 'property': field}
                                    for key, field in sorted(stale)]
    validate_snapshot(result)  # entire assembly; construction != execution pass
    return result


def publish(store, parent, proposal, reference):
    """Called by native ModelStore.revise; its existing attempt log owns errors."""
    with _structural_writer(store):
        candidate = _candidate(parent, proposal, reference, _known_identities(store))
        return store._publish(candidate)
