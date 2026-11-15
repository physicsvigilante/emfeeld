"""Atomic, bounded model-format-1 physical changes; no new laws or solver.

V3 accepts 2-4 disjoint V1/V2-compatible edits against one exact parent,
checks the complete final snapshot, and publishes one immutable descendant.
An accepted construction is never a certified numerical run.
"""
from __future__ import annotations

from copy import deepcopy

from .model_revisions import (DEFAULTS, INTENTS, STRENGTHS, RevisionError,
    _origin, encode, exact_keys, identifier, validate_snapshot)
from .scene import source_from_dict, source_keys
from .structural_revisions import _known_identities, _structural_writer


# No source-type replacement, multiple changes to one named entity, or formulas.
_OPERATIONS = {
    'replace_property': ('property', 'expected_value', 'value'),
    'add_source': ('source',),
    'remove_source': ('expected_source',),
    'add_particle': ('particle',),
    'remove_particle': ('expected_particle',),
}
_LITERAL_ORIGINS = frozenset((
    'supplied_fact', 'source_convention', 'adopted_assumption',
    'unit_conversion', 'illustrative_choice',
))


def _same_physical_value(expected, current):
    """V1 precondition semantics: finite numeric JSON old values can differ
    in int/float representation, but boolean must not compare equal to 1.
    """
    if encode(expected) == encode(current):
        return True

    def numeric(value):
        if isinstance(value, list):
            return all(numeric(item) for item in value)
        return type(value) in (int, float)

    return numeric(expected) and expected == current


def _property(parent, member, origin, result):
    target = member['target_id']
    if target not in parent['entities']:
        raise RevisionError('unknown_target', 'property target does not exist in the pinned parent')
    row = parent['entities'][target]
    role = row['role']
    if member['expected_role'] != role:
        raise RevisionError('wrong_role', 'property target has a different role')
    allowed = {'component_property': set(), 'initial_condition': set(), 'external_input': set()}
    if role == 'source':
        allowed['component_property'] = set(STRENGTHS) | {'radius_m', 'center_m', 'direction', 'normal'}
        allowed['external_input'] = {'field_N_C' if parent['kind'] == 'electric' else 'field_m_s2'}
    else:
        allowed['component_property'] = {'mass_kg'} | ({'charge_C'} if parent['kind'] == 'electric' else set())
        allowed['initial_condition'] = {'position_m', 'velocity_m_s'}
    prop = member['property']
    category = member['category']
    if (not isinstance(prop, str) or not isinstance(category, str)
            or category not in allowed or prop not in allowed[category]
            or prop not in row['properties']):
        raise RevisionError('unsupported_change', 'property/category is not qualified for this role/type/domain')
    if not _same_physical_value(member['expected_value'], row['properties'][prop]):
        raise RevisionError('old_value_mismatch', 'expected value differs from the exact parent')
    if member['value'] == row['properties'][prop]:
        raise RevisionError('no_op', 'a property member must change its complete physical value')
    result['entities'][target]['properties'][prop] = deepcopy(member['value'])
    result['entities'][target]['provenance'][prop] = deepcopy(origin)
    return (target, prop)


def _structural(parent, member, origin, result, known):
    operation, target = member['operation'], member['target_id']
    role = 'source' if operation.endswith('source') else 'particle'
    if member['category'] != 'structural_change' or member['expected_role'] != role:
        raise RevisionError('unsupported_change', 'structural operation requires its exact role and category')
    if operation.startswith('add_'):
        if target in known:
            raise RevisionError('identity_conflict',
                'physical ID was already used in an accepted ancestor or sibling')
        if role == 'source':
            props = deepcopy(member['source'])
            source_from_dict(parent['kind'], props)
            provenance = {key: deepcopy(origin) for key in props}
            for key in source_keys(parent['kind'], props['type'])[1]:
                if key not in props:
                    props[key] = deepcopy(DEFAULTS[key])
                    provenance[key] = {
                        'origin': 'source_convention',
                        'reason': 'Expanded existing scene-v1 parser default, not a source given',
                        'evidence': f'scene-v1 default for source.{key}',
                    }
        else:
            props = deepcopy(member['particle'])
            required = ('mass_kg', 'position_m', 'velocity_m_s')
            if parent['kind'] == 'electric':
                exact_keys(props, (*required, 'charge_C'))
            else:
                exact_keys(props, required, ('charge_C',))
                if 'charge_C' in props and props['charge_C'] != 0:
                    raise RevisionError('unsupported_physics',
                        'gravitational charge is not electric/gravity coupling')
            provenance = {key: deepcopy(origin) for key in props}
            if parent['kind'] == 'gravity' and 'charge_C' not in props:
                props['charge_C'] = 0.
                provenance['charge_C'] = {
                    'origin': 'source_convention',
                    'reason': 'Expanded existing gravity test-particle default; no electric coupling',
                    'evidence': 'scene-v1 Particle.charge_C default 0',
                }
        result['entities'][target] = {
            'role': role, 'properties': props, 'provenance': provenance,
        }
        result[role + '_order'].append(target)
    else:
        if target not in parent['entities']:
            raise RevisionError('unknown_target', 'removal target is absent from the pinned parent')
        row = parent['entities'][target]
        if row['role'] != role:
            raise RevisionError('wrong_role', 'removal target has a different role')
        if encode(member['expected_' + role]) != encode(row['properties']):
            raise RevisionError('old_value_mismatch',
                'removal must name complete canonical properties of the pinned parent')
        del result['entities'][target]
        result[role + '_order'].remove(target)
    return role


def _candidate(parent, proposal, reference, known):
    exact_keys(proposal, (
        'proposal_version', 'proposal_id', 'revision_id', 'parent',
        'category', 'scenario_intent', 'changes',
    ))
    if type(proposal['proposal_version']) is not int or proposal['proposal_version'] != 3:
        raise ValueError('atomic scenario revisions require proposal_version 3')
    identifier(proposal['proposal_id'])
    identifier(proposal['revision_id'])
    if proposal['parent'] != reference:
        raise RevisionError('stale_parent', 'transaction must pin its exact parent')
    if proposal['revision_id'] == parent['revision_id']:
        raise RevisionError('identity_conflict', 'revision cannot replace its parent')
    if proposal['category'] != 'atomic_change':
        raise RevisionError('unsupported_change', 'transaction category must be atomic_change')
    if proposal['scenario_intent'] not in INTENTS:
        raise ValueError('unknown scenario intent')
    members = proposal['changes']
    if not isinstance(members, list) or not 2 <= len(members) <= 4:
        raise RevisionError('unsupported_change', 'an atomic scenario requires 2-4 members')

    # Check all member identities/grammar against one parent before modifying
    # a private candidate; no intermediate snapshot can become accepted.
    seen = set()
    validated = []
    for member in members:
        if not isinstance(member, dict):
            raise ValueError('atomic change member must be a JSON object')
        operation = member.get('operation')
        if not isinstance(operation, str) or operation not in _OPERATIONS:
            raise RevisionError('unsupported_change', 'unsupported atomic member operation')
        extras = _OPERATIONS[operation]
        exact_keys(member, (
            'operation', 'category', 'target_id', 'expected_role', 'provenance', *extras,
        ))
        target = identifier(member['target_id'])
        if target in seen:
            raise RevisionError('duplicate_target',
                'one physical entity can appear in only one atomic member')
        seen.add(target)
        origin = _origin(member['provenance'])
        if origin['origin'] not in _LITERAL_ORIGINS:
            raise RevisionError('unsupported_provenance',
                'atomic V1 requires explicit literal origins; no computed or unknown input')
        validated.append((member, origin))

    result = deepcopy(parent)
    result.update(
        revision_id=proposal['revision_id'], parent=deepcopy(reference),
        operation=deepcopy(proposal),
    )
    result['interpretation']['scenario_intent'] = proposal['scenario_intent']
    changed_properties = set()
    removed = {}
    source_membership_changed = False
    for member, origin in validated:
        operation = member['operation']
        if operation == 'replace_property':
            changed_properties.add(_property(parent, member, origin, result))
        else:
            role = _structural(parent, member, origin, result, known)
            source_membership_changed |= (role == 'source')
            if operation.startswith('remove_'):
                removed[member['target_id']] = role

    if not result['source_order']:
        raise RevisionError('last_source', 'the final physical snapshot must retain a source')

    # Surviving computed receipts may not point at deleted entities. A
    # simultaneously removed dependent or an overwritten literal property
    # has no surviving receipt and therefore does not block the transaction.
    computed = {}
    for key, entity in result['entities'].items():
        for prop, provenance in entity['provenance'].items():
            if 'computation' not in provenance:
                continue
            inputs = provenance['computation']['receipt']['inputs']
            for dep in inputs:
                dep_id = dep['target_id']
                if dep_id in removed:
                    raise RevisionError('dependent_' + removed[dep_id],
                        f'removal leaves a surviving computed input {key}.{prop} depending on {dep_id}')
            computed[(key, prop)] = {
                (dep['target_id'], dep['property']) for dep in inputs
            }

    stale = {
        (row['target_id'], row['property'])
        for row in parent['stale_dependencies']
        if row['target_id'] in result['entities']
    }
    stale.difference_update(changed_properties)
    if source_membership_changed:
        stale.update(computed)
    invalid = set(stale) | changed_properties
    while True:
        before = len(invalid)
        for key, dependencies in computed.items():
            if dependencies & invalid:
                stale.add(key)
                invalid.add(key)
        if len(invalid) == before:
            break
    result['stale_dependencies'] = [
        {'target_id': target, 'property': prop} for target, prop in sorted(stale)
    ]

    # Existing model-format-1 scene parsing remains the authoritative check,
    # but only after the entire proposed system has been assembled.
    validate_snapshot(result)
    for key, entity in parent['entities'].items():
        if key not in seen and result['entities'].get(key) != entity:
            raise RevisionError('unexpected_change',
                'an unaffected named physical entity must be unchanged')
    return result


def publish(store, parent, proposal, reference):
    """The native proposal attempt log owns all errors and final decisions."""
    with _structural_writer(store):
        # The original parent read by ModelStore.revise preceded this lock.
        # Recheck the exact pinned bytes while holding the structural lock.
        locked_parent, _ = store.read(reference)
        if locked_parent != parent:
            raise RevisionError('stale_parent', 'parent changed between validated reads')
        known = _known_identities(store)
        candidate = _candidate(locked_parent, proposal, reference, known)
        return store._publish(candidate)
