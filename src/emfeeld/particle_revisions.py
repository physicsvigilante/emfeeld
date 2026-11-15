"""Bounded structural insertion/removal of independent test particles.

Reuses the exact named-model store, source structural history/lock, and unchanged
scene parser. Does not integrate, re-run native observations, or invent coupling.
"""
from __future__ import annotations

from copy import deepcopy

from .model_revisions import (INTENTS, RevisionError, _origin, encode,
                              exact_keys, identifier, validate_snapshot)
from .structural_revisions import _known_identities, _structural_writer


def _candidate(parent, proposal, reference, known):
    operation = proposal.get('operation')
    if operation not in ('add_particle', 'remove_particle'):
        raise RevisionError('unsupported_change',
            'particle structural V1 supports only add_particle and remove_particle')
    payload = 'particle' if operation == 'add_particle' else 'expected_particle'
    exact_keys(proposal, ('proposal_version', 'proposal_id', 'parent', 'revision_id',
        'category', 'operation', 'target_id', 'expected_role', 'scenario_intent',
        'provenance', payload))
    if type(proposal['proposal_version']) is not int or proposal['proposal_version'] != 2:
        raise ValueError('particle structural revisions require proposal_version 2')
    for key in ('proposal_id', 'revision_id', 'target_id'):
        identifier(proposal[key])
    if proposal['category'] != 'structural_change' or proposal['expected_role'] != 'particle':
        raise RevisionError('unsupported_change',
            'only explicitly named test-particle structural operations are supported')
    if proposal['parent'] != reference:
        raise RevisionError('stale_parent', 'particle proposal must pin its exact parent')
    if proposal['revision_id'] == parent['revision_id']:
        raise RevisionError('identity_conflict', 'a revision cannot replace its parent')
    if proposal['scenario_intent'] not in INTENTS:
        raise ValueError('unknown scenario intent')
    origin = _origin(proposal['provenance'])
    if origin['origin'] in ('computed_result', 'unknown'):
        raise RevisionError('unsupported_provenance',
            'new particle properties must be explicit, not unknown or unchecked computed inputs')

    result = deepcopy(parent)
    result.update(revision_id=proposal['revision_id'], parent=deepcopy(reference),
                  operation=deepcopy(proposal))
    result['interpretation']['scenario_intent'] = proposal['scenario_intent']
    target = proposal['target_id']
    if operation == 'add_particle':
        if target in known:
            raise RevisionError('identity_conflict',
                'particle ID was used by a source or particle in an accepted ancestor or sibling')
        props = deepcopy(proposal['particle'])
        required = ('mass_kg', 'position_m', 'velocity_m_s')
        # Electric charge is an explicit physical condition, never an implicit
        # neutral-particle assumption in the electric regime.
        if parent['kind'] == 'electric':
            exact_keys(props, (*required, 'charge_C'))
        else:
            exact_keys(props, required, ('charge_C',))
            if 'charge_C' in props and props['charge_C'] != 0:
                raise RevisionError('unsupported_physics',
                    'charge on a gravitational test body is ignored, not electric/gravity coupling')
        provenance = {key: deepcopy(origin) for key in props}
        if parent['kind'] == 'gravity' and 'charge_C' not in props:
            props['charge_C'] = 0.
            provenance['charge_C'] = {'origin': 'source_convention',
                'reason': 'Expanded existing gravity test-particle default; no electric coupling',
                'evidence': 'scene-v1 Particle.charge_C default 0'}
        result['entities'][target] = {'role': 'particle', 'properties': props,
                                      'provenance': provenance}
        result['particle_order'].append(target)
    else:
        if target not in parent['entities']:
            raise RevisionError('unknown_target', 'particle does not exist in the pinned parent')
        row = parent['entities'][target]
        if row['role'] != 'particle':
            raise RevisionError('wrong_role', 'particle removal cannot remove a source')
        if encode(proposal['expected_particle']) != encode(row['properties']):
            raise RevisionError('old_value_mismatch',
                'expected_particle must exactly match complete canonical parent properties')
        dependents = []
        for key, entity in parent['entities'].items():
            if key == target:
                continue
            for field, record in entity['provenance'].items():
                if ('computation' in record and any(dep['target_id'] == target
                    for dep in record['computation']['receipt']['inputs'])):
                    dependents.append(f'{key}.{field}')
        if dependents:
            raise RevisionError('dependent_particle',
                f'removal would leave dangling computation inputs: {sorted(dependents)}')
        del result['entities'][target]
        result['particle_order'].remove(target)
        # Remove only stale flags that belonged to the removed particle.
        # Test bodies do not backreact on sources or unrelated test bodies.
        result['stale_dependencies'] = [deepcopy(x) for x in parent['stale_dependencies']
                                        if x['target_id'] != target]

    # Source set, every unaffected physical value, and all surviving receipts
    # stay unchanged. Validation is the authoritative existing scene parser;
    # it does not certify any requested numerical trajectory.
    validate_snapshot(result)
    return result


def publish(store, parent, proposal, reference):
    """Use the same identity scan and local lock as source structural edits."""
    with _structural_writer(store):
        return store._publish(_candidate(parent, proposal, reference,
                                         _known_identities(store)))
