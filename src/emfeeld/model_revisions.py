"""Immutable named physical models above the unchanged scene-v1 interface.

No field evaluation, integrations, arbitrary expressions, or implicit latest refs.
Files are append-only by API policy, not signed or protected against an attacker.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .observations import ID_PATTERN, packet_from_dict
from .scene import scene_from_dict, source_keys, strict_keys

ORIGINS = ('supplied_fact', 'source_convention', 'adopted_assumption',
           'unit_conversion', 'computed_result', 'illustrative_choice', 'unknown')
INTENTS = ('source_interpretation', 'source_correction', 'teacher_hypothesis',
           'illustrative_exploration')
REQUIREMENTS = ('fixed_prescribed_sources', 'independent_nonrelativistic_test_particles')
DEFAULTS = {'center_m': [0, 0, 0], 'origin_m': [0, 0, 0],
            'normal': [0, 0, 1], 'direction': [0, 0, 1]}
STRENGTHS = ('charge_C', 'mass_kg', 'charge_per_m_C_m', 'mass_per_m_kg_m',
             'charge_per_m2_C_m2', 'mass_per_m2_kg_m2')
PROPERTY_UNITS = {'charge_C':'C', 'mass_kg':'kg', 'radius_m':'m', 'center_m':'m',
                  'origin_m':'m', 'position_m':'m', 'velocity_m_s':'m/s',
                  'direction':'1', 'normal':'1', 'reference_radius_m':'m',
                  'field_N_C':'N/C', 'field_m_s2':'m/s^2', 'charge_per_m_C_m':'C/m',
                  'mass_per_m_kg_m':'kg/m', 'charge_per_m2_C_m2':'C/m^2', 'mass_per_m2_kg_m2':'kg/m^2'}


class RevisionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def decode(raw: bytes) -> Any:
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError(f'duplicate JSON key: {k}')
            d[k] = v
        return d
    def nonfinite(text):
        raise ValueError(f'nonfinite JSON number: {text}')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)


def identifier(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(ID_PATTERN, value) is None:
        raise RevisionError('invalid_identity', 'IDs must use the existing safe observation-ID convention')
    return value


def text(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')


def exact_keys(data, names, optional=()):
    strict_keys(data, (*names, *optional), names)


def put(path: Path, raw: bytes) -> None:
    """Exclusive writes; never truncate an existing attempt or accepted object."""
    with path.open('xb') as f:
        f.write(raw)


def identity(revision: dict, raw: bytes) -> dict:
    return {'model_id': revision['model_id'], 'revision_id': revision['revision_id'],
            'sha256': sha256(raw)}


def check_reference(ref: dict) -> None:
    exact_keys(ref, ('model_id', 'revision_id', 'sha256'))
    identifier(ref['model_id']); identifier(ref['revision_id'])
    if not isinstance(ref['sha256'], str) or re.fullmatch('[0-9a-f]{64}', ref['sha256']) is None:
        raise RevisionError('invalid_reference', 'exact parent SHA256 is required')


def property_value(revision, target, prop):
    try:
        return revision['entities'][target]['properties'][prop]
    except (KeyError, TypeError) as exc:
        raise RevisionError('unknown_target', f'unknown physical property {target}.{prop}') from exc


def scene_data(revision: dict, *, duration_s=1., samples=2,
               bounds_m=(-1, 1, -1, 1, -1, 1)) -> dict:
    """Legacy envelope. Defaults here are validation scaffolding, never an analysis."""
    entities = revision['entities']
    return {'schema_version': 1, 'title': revision['title'], 'kind': revision['kind'],
            'sources': [deepcopy(entities[k]['properties']) for k in revision['source_order']],
            'particles': [deepcopy(entities[k]['properties']) for k in revision['particle_order']],
            'duration_s': duration_s, 'samples': samples, 'bounds_m': list(bounds_m)}


def validate_snapshot(revision: dict) -> None:
    exact_keys(revision, ('model_format', 'model_id', 'revision_id', 'parent', 'title',
                         'kind', 'time_origin_s', 'entities', 'source_order', 'particle_order',
                         'interpretation', 'operation', 'stale_dependencies'))
    if type(revision['model_format']) is not int or revision['model_format'] != 1:
        raise ValueError('only model_format 1 is supported')
    identifier(revision['model_id']); identifier(revision['revision_id']); text(revision['title'], 'title')
    if type(revision['time_origin_s']) not in (int, float) or revision['time_origin_s'] != 0:
        raise ValueError('only the explicit physical time origin 0 s is admitted')
    if revision['parent'] is not None:
        check_reference(revision['parent'])
        if revision['parent']['model_id'] != revision['model_id']:
            raise RevisionError('wrong_model', 'parent must belong to this model')
    ent = revision['entities']
    if not isinstance(ent, dict) or not ent:
        raise ValueError('entities must be a nonempty ID-keyed object')
    ordered = []
    for role in ('source', 'particle'):
        order = revision[role + '_order']
        if not isinstance(order, list):
            raise ValueError('execution ordering must be an array of physical IDs')
        for key in order:
            identifier(key)
            if key not in ent or ent[key].get('role') != role:
                raise RevisionError('wrong_role', 'execution mapping has a missing or wrong-role entity')
        ordered.extend(order)
    if len(ordered) != len(set(ordered)) or set(ordered) != set(ent):
        raise RevisionError('duplicate_identity', 'identities must be unique across sources and particles')
    for key, row in ent.items():
        identifier(key); exact_keys(row, ('role', 'properties', 'provenance'))
        props, provenance = row['properties'], row['provenance']
        if not isinstance(props, dict) or not isinstance(provenance, dict) or set(props) != set(provenance):
            raise ValueError('every physical property requires an origin record')
        for prop, origin in provenance.items():
            exact_keys(origin, ('origin', 'reason', 'evidence'), ('computation',))
            if origin['origin'] not in ORIGINS:
                raise ValueError('unknown value origin')
            text(origin['reason'], 'provenance reason'); text(origin['evidence'], 'provenance evidence')
            if origin['origin'] == 'computed_result' and 'computation' not in origin:
                raise ValueError('computed input requires a retained computation/check receipt')
            if 'computation' in origin:
                _validate_computation(revision, key, prop, origin['computation'], current=False)
    record = revision['interpretation']
    exact_keys(record, ('statement', 'assumptions', 'requirements', 'unresolved', 'scenario_intent'))
    text(record['statement'], 'statement')
    if record['scenario_intent'] not in INTENTS:
        raise ValueError('unknown scenario intent')
    for name in ('assumptions', 'requirements'):
        if not isinstance(record[name], list):
            raise ValueError(f'{name} must be an array')
        for x in record[name]: text(x, name)
    if not isinstance(record['unresolved'], list):
        raise ValueError('unresolved must be an array')
    for unknown in record['unresolved']:
        exact_keys(unknown, ('description', 'affects'))
        text(unknown['description'], 'unknown description')
        if unknown['affects'] not in ('static', 'trajectory', 'all', 'appearance'):
            raise ValueError('unresolved fact must declare affected analysis or appearance')
    if not isinstance(revision['stale_dependencies'], list):
        raise ValueError('stale_dependencies must be an array')
    for stale in revision['stale_dependencies']:
        exact_keys(stale, ('target_id', 'property'))
        property_value(revision, stale['target_id'], stale['property'])
    # Existing numerical schema is authoritative; no field is evaluated here.
    scene_from_dict(scene_data(revision))


def _validate_computation(revision, target, prop, record, *, current):
    exact_keys(record, ('receipt', 'sha256'))
    receipt = record['receipt']
    if sha256(encode(receipt)) != record['sha256']:
        raise RevisionError('evidence_mismatch', 'computation receipt identity mismatch')
    exact_keys(receipt, ('computation_id', 'method', 'unit', 'inputs', 'output', 'check'))
    identifier(receipt['computation_id']); text(receipt['method'], 'method'); text(receipt['unit'], 'unit')
    if prop not in PROPERTY_UNITS or receipt['unit'] != PROPERTY_UNITS[prop]:
        raise RevisionError('evidence_units', 'computed output unit must match the physical property')
    check = receipt['check']
    exact_keys(check, ('passed', 'method', 'evidence'))
    if check['passed'] is not True:
        raise RevisionError('unchecked_computation', 'computed input has no successful recorded check')
    text(check['method'], 'check method'); text(check['evidence'], 'check evidence')
    output = receipt['output']; exact_keys(output, ('target_id', 'property', 'value'))
    if (output['target_id'], output['property'], output['value']) != (target, prop, property_value(revision, target, prop)):
        raise RevisionError('evidence_mismatch', 'computation output is not this physical value')
    if not isinstance(receipt['inputs'], list) or not receipt['inputs']:
        raise ValueError('computed input must identify its dependencies')
    for dep in receipt['inputs']:
        exact_keys(dep, ('target_id', 'property', 'value'))
        value = property_value(revision, dep['target_id'], dep['property'])
        if current and value != dep['value']:
            raise RevisionError('stale_computation', 'computation input no longer matches its recorded value')


def _origin(data, *, computation=None):
    exact_keys(data, ('origin', 'reason', 'evidence'))
    if data['origin'] not in ORIGINS:
        raise ValueError('unknown value origin')
    text(data['reason'], 'reason'); text(data['evidence'], 'evidence')
    row = deepcopy(data)
    if computation is not None:
        if data['origin'] != 'computed_result':
            raise ValueError('a computation cannot be disguised as another value origin')
        row['computation'] = {'receipt': deepcopy(computation), 'sha256': sha256(encode(computation))}
    elif data['origin'] == 'computed_result':
        raise ValueError('computed input requires explicit computation evidence')
    return row


def _changes(old, new):
    return [(key, prop) for key, row in old['entities'].items()
            for prop, value in row['properties'].items()
            if value != new['entities'][key]['properties'][prop]]


def derive(parent: dict, proposal: dict, reference: dict) -> dict:
    exact_keys(proposal, ('proposal_version', 'proposal_id', 'parent', 'revision_id',
                          'category', 'target_id', 'expected_role', 'property', 'expected_value',
                          'value', 'scenario_intent', 'provenance'), ('computation',))
    if type(proposal['proposal_version']) is not int or proposal['proposal_version'] != 1:
        raise ValueError('only proposal_version 1 is supported')
    for key in ('proposal_id', 'revision_id', 'target_id'): identifier(proposal[key])
    if proposal['parent'] != reference:
        raise RevisionError('stale_parent', 'proposal must pin the exact current parent reference')
    if proposal['revision_id'] == parent['revision_id']:
        raise RevisionError('identity_conflict', 'a revision cannot replace its parent')
    target, prop = proposal['target_id'], proposal['property']
    if target not in parent['entities']:
        raise RevisionError('unknown_target', 'physical entity does not exist in this revision')
    row = parent['entities'][target]; role = row['role']
    if role != proposal['expected_role']:
        raise RevisionError('wrong_role', 'physical entity role does not match the proposed edit')
    allowed = {'component_property': set(), 'initial_condition': set(), 'external_input': set()}
    if role == 'source':
        allowed['component_property'] = set(STRENGTHS) | {'radius_m', 'center_m', 'direction', 'normal'}
        allowed['external_input'] = {'field_N_C' if parent['kind'] == 'electric' else 'field_m_s2'}
    else:
        allowed['component_property'] = {'mass_kg'} | ({'charge_C'} if parent['kind'] == 'electric' else set())
        allowed['initial_condition'] = {'position_m', 'velocity_m_s'}
    if (not isinstance(prop, str) or proposal['category'] not in allowed
            or prop not in allowed[proposal['category']] or prop not in row['properties']):
        raise RevisionError('unsupported_change', 'property/category is not qualified for this role/type/domain')
    # Do not allow Python bool==1 to satisfy a numerical old-value precondition.
    if encode(proposal['expected_value']) != encode(row['properties'][prop]):
        # Integers and floats of equal finite numeric value are physical equals.
        def numeric(v):
            return all(numeric(x) for x in v) if isinstance(v, list) else type(v) in (int, float)
        if not numeric(proposal['expected_value']) or proposal['expected_value'] != row['properties'][prop]:
            raise RevisionError('old_value_mismatch', 'expected physical value does not match the pinned parent')
    if proposal['scenario_intent'] not in INTENTS:
        raise ValueError('unknown scenario intent')
    result = deepcopy(parent)
    result.update(revision_id=proposal['revision_id'], parent=deepcopy(reference), operation=deepcopy(proposal))
    result['interpretation']['scenario_intent'] = proposal['scenario_intent']
    result['entities'][target]['properties'][prop] = deepcopy(proposal['value'])
    result['entities'][target]['provenance'][prop] = _origin(proposal['provenance'], computation=proposal.get('computation'))
    validate_snapshot(result)  # also rejects invalid numbers, vectors, mass/radius
    if result['entities'][target]['provenance'][prop]['origin'] == 'computed_result':
        _validate_computation(result, target, prop, result['entities'][target]['provenance'][prop]['computation'], current=True)
    if proposal['value'] == row['properties'][prop]:
        raise RevisionError('no_op', 'unchanged physical property; no new scenario created')
    if _changes(parent, result) != [(target, prop)]:
        raise RevisionError('unexpected_change', 'a proposal must change exactly one complete property')
    stale = {(x['target_id'], x['property']) for x in parent['stale_dependencies']}
    stale.discard((target, prop))
    invalid = {(target, prop)} | stale
    while True:
        previous = set(invalid)
        for key, entity in result['entities'].items():
            for field, origin in entity['provenance'].items():
                if 'computation' in origin and (key, field) != (target, prop):
                    deps = {(x['target_id'], x['property']) for x in origin['computation']['receipt']['inputs']}
                    if deps & invalid:
                        stale.add((key, field)); invalid.add((key, field))
        if previous == invalid: break
    result['stale_dependencies'] = [{'target_id': k, 'property': p} for k, p in sorted(stale)]
    validate_snapshot(result)
    return result


class ModelStore:
    """A local append-only model lineage. Hashed filenames avoid OS ID collisions."""
    def __init__(self, path):
        self.path = Path(path)
        self.info = decode((self.path / 'model.json').read_bytes())
        identifier(self.info['model_id']); check_reference(self.info['root'])

    def _directory(self, ident):
        return self.path / 'revisions' / sha256(identifier(ident).encode())

    def reference(self, revision_id):
        folder = self._directory(revision_id)
        ref = decode((folder / 'reference.json').read_bytes())
        self.read(ref)
        return ref

    def read(self, reference):
        check_reference(reference)
        if reference['model_id'] != self.info['model_id']:
            raise RevisionError('wrong_model', 'reference belongs to another model')
        folder = self._directory(reference['revision_id'])
        raw = (folder / 'revision.json').read_bytes()
        recorded = decode((folder / 'reference.json').read_bytes())
        if reference != recorded or sha256(raw) != reference['sha256']:
            raise RevisionError('stale_parent', 'revision bytes do not match the exact reference')
        value = decode(raw)
        if identity(value, raw) != reference:
            raise RevisionError('identity_conflict', 'revision content has a different identity')
        validate_snapshot(value)
        return value, raw

    def _publish(self, revision):
        raw = encode(revision); reference = identity(revision, raw)
        folder = self._directory(revision['revision_id'])
        folder.mkdir()  # consumes ID even on interrupted writes; never overwrite
        put(folder / 'revision.json', raw)
        put(folder / 'reference.json', encode(reference))  # commit marker written last
        return reference

    @classmethod
    def import_legacy(cls, source, assignment, output):
        """Explicit import pinned to raw source bytes; all prior source data retained."""
        raw = Path(source).read_bytes(); spec_raw = Path(assignment).read_bytes(); spec = decode(spec_raw)
        exact_keys(spec, ('import_version', 'model_id', 'revision_id', 'source_sha256',
                         'source_ids', 'particle_ids', 'default_origin', 'interpretation'),
                   ('computed_inputs',))
        if type(spec['import_version']) is not int or spec['import_version'] != 1:
            raise ValueError('only import_version 1 is supported')
        identifier(spec['model_id']); identifier(spec['revision_id'])
        if spec['source_sha256'] != sha256(raw):
            raise RevisionError('stale_import', 'ID assignment does not match the original source bytes')
        original = decode(raw)
        if 'observation_schema_version' in original:
            packet_from_dict(original); scene = original['scene']
        else:
            scene_from_dict(original); scene = original
        entities = {}
        default_origin = _origin(spec['default_origin'])
        if default_origin['origin'] in ('unknown', 'computed_result'):
            raise ValueError('default input origin must be explicit; computed/unknown values need targeted records')
        for role, rows in (('source', scene['sources']), ('particle', scene.get('particles', []))):
            ids = spec[role + '_ids']
            if not isinstance(ids, list) or len(ids) != len(rows):
                raise ValueError('explicit ID assignment must cover every original entity')
            for i, (key, props) in enumerate(zip(ids, rows)):
                identifier(key)
                if key in entities:
                    raise RevisionError('duplicate_identity', 'duplicate ID across physical entities')
                props = deepcopy(props); prov = {p: {**deepcopy(default_origin),
                    'evidence': f"{default_origin['evidence']}; original sha256={sha256(raw)}; {role}s[{i}].{p}"} for p in props}
                defaults = ({k: DEFAULTS[k] for k in source_keys(scene['kind'], props['type'])[1]}
                            if role == 'source' else {'charge_C': 0.})
                for k, value in defaults.items():
                    if k not in props:
                        props[k] = deepcopy(value)
                        prov[k] = {'origin': 'source_convention', 'reason': 'Expanded explicit legacy parser default, not a source given',
                                   'evidence': f'scene-v1 default for {role}.{k}'}
                entities[key] = {'role': role, 'properties': props, 'provenance': prov}
        revision = {'model_format': 1, 'model_id': spec['model_id'], 'revision_id': spec['revision_id'],
                    'parent': None, 'title': scene['title'], 'kind': scene['kind'], 'time_origin_s': 0.,
                    'entities': entities, 'source_order': list(spec['source_ids']), 'particle_order': list(spec['particle_ids']),
                    'interpretation': deepcopy(spec['interpretation']), 'operation': None, 'stale_dependencies': []}
        for item in spec.get('computed_inputs', []):
            exact_keys(item, ('target_id', 'property', 'provenance', 'receipt'))
            property_value(revision, item['target_id'], item['property'])
            origin = _origin(item['provenance'], computation=item['receipt'])
            revision['entities'][item['target_id']]['provenance'][item['property']] = origin
            _validate_computation(revision, item['target_id'], item['property'], origin['computation'], current=True)
        validate_snapshot(revision)
        output = Path(output); output.mkdir(parents=True, exist_ok=False)
        (output / 'revisions').mkdir(); (output / 'proposals').mkdir()
        put(output / 'original.json', raw); put(output / 'import.json', spec_raw)
        raw_revision = encode(revision); root = identity(revision, raw_revision)
        put(output / 'model.json', encode({'model_id': spec['model_id'], 'root': root,
            'source_sha256': sha256(raw), 'import_sha256': sha256(spec_raw)}))
        store = cls(output); store._publish(revision)
        return store, root

    def revise(self, proposal_path):
        raw = Path(proposal_path).read_bytes(); proposal = decode(raw)
        identifier(proposal.get('proposal_id'))
        directory = self.path / 'proposals' / sha256(proposal['proposal_id'].encode())
        directory.mkdir()  # retain accepted and rejected well-formed attempts
        put(directory / 'proposal.json', raw)
        decision = {'proposal_id': proposal['proposal_id'], 'proposal_sha256': sha256(raw),
                    'status': 'pending', 'numerical_work': 'not_run'}
        put(directory / 'pending.json', encode(decision))
        try:
            parent, _ = self.read(proposal['parent'])
            if self._directory(proposal['revision_id']).exists():
                raise RevisionError('identity_conflict', 'revision ID is already used, including incomplete attempts')
            candidate = derive(parent, proposal, proposal['parent'])
            reference = self._publish(candidate)
            decision.update(status='accepted', reference=reference, qualification='construction_only',
                            plan='rebuild_existing_source_assembly; revalidate_each_analysis; fresh_numerical_results')
        except (ValueError, KeyError, TypeError, FileExistsError, FileNotFoundError) as exc:
            decision.update(status='no_op' if getattr(exc, 'code', '') == 'no_op' else 'rejected',
                            code=getattr(exc, 'code', 'invalid_proposal'), reason=str(exc))
        put(directory / 'decision.json', encode(decision))
        return decision
