"""Generate a versioned authoring catalogue from shared parser keys and adapters.

This is discovery data, not a second validator or a natural-language solver.
Use the runtime packet validator after authoring. No physics is evaluated here.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .fields import KINDS
from .scene import REGISTRY, SCENE_REQUIRED, SCENE_OPTIONAL, source_keys, source_from_dict
from .observations import TYPES, ID_PATTERN
from .trajectory_samples import QUANTITIES, SOLVER_SETTINGS
from .plane_events import DIRECTIONS
from .radial_events import DIRECTIONS as RADIAL_DIRECTIONS
from .turning_events import EXTREMA, TurningCondition
from .rest_turning_events import POLICY
from .event_core import UNITS

# Observation enums come from adapters; structural descriptions below are tested
# against runtime validation (required/unknown fields, selectors and units).
# They do not replace that validator or modify its established behaviour.
SAMPLE_REQUIRED = ("id", "type", "particle_index", "quantity")
SAMPLE_OPTIONAL = ("sample_index", "time_s", "time_selection", "max_time_error_s", "expectation")
EVENT_REQUIRED = {
    "plane": ("id", "type", "particle_index", "condition", "occurrence", "max_step_s", "min_normal_speed_m_s", "accuracy"),
    "radial": ("id", "type", "particle_index", "condition", "occurrence", "max_step_s", "min_radial_speed_m_s", "accuracy"),
    "radial_turning": ("id", "type", "particle_index", "condition", "occurrence", "max_step_s", "min_distance_m", "min_radial_acceleration_m_s2", "accuracy"),
}
CONDITION_REQUIRED = {
    "plane": ("type", "point_m", "normal", "direction"),
    "radial": ("type", "center_m", "radius_m", "direction"),
    "radial_turning": ("type", "center_m", "extremum"),
}
EVENT_ACCURACY_KEYS = ("time_atol_s", "position_atol_m", "velocity_atol_m_s", "rtol")
TURNING_ACCURACY_KEYS = ("time_atol_s", "position_atol_m", "velocity_atol_m_s", "radial_speed_atol_m_s", "rtol")


def static_request_keys(kind, typ):
    position = ("from_m", "to_m") if typ == "potential_difference" else ("position_m",)
    coupling = (("test_charge_C" if kind == "electric" else "test_mass_kg"),) if typ == "force" else ()
    return ("id", "type", *position, *coupling)


_UNITS = {
    'charge_C': 'C', 'mass_kg': 'kg', 'radius_m': 'm', 'center_m': 'm', 'origin_m': 'm',
    'direction': '1', 'normal': '1', 'reference_radius_m': 'm',
    'charge_per_m_C_m': 'C/m', 'mass_per_m_kg_m': 'kg/m',
    'charge_per_m2_C_m2': 'C/m^2', 'mass_per_m2_kg_m2': 'kg/m^2',
    'field_N_C': 'N/C', 'field_m_s2': 'm/s^2',
}
_VECTOR_KEYS = ('center_m', 'origin_m', 'normal', 'direction', 'field_N_C', 'field_m_s2')
_GEOMETRY_DEFAULTS = {'center_m': [0, 0, 0], 'origin_m': [0, 0, 0],
                      'direction': [0, 0, 1], 'normal': [0, 0, 1]}
_SOURCE_MEANING = {
    'point': 'Fixed point source; centre is singular for nonzero strength.',
    'solid_sphere': 'Prescribed uniform volume density, penetrable; not a polarizable conductor or collision surface.',
    'shell': 'Prescribed uniform infinitesimally thin shell; potential continuous, field undefined at shell surface.',
    'line': 'Prescribed infinite uniform line; axis is singular for nonzero strength.',
    'plane': 'Prescribed infinite uniform sheet; potential continuous, field undefined on the sheet.',
    'uniform': 'Prescribed constant vector field; no localized source geometry.',
}
_REFERENCE = {
    'point': 'zero at infinity', 'solid_sphere': 'zero at infinity', 'shell': 'zero at infinity',
    'line': 'zero at the explicitly supplied finite reference_radius_m',
    'plane': 'zero on the plane', 'uniform': 'zero at origin_m',
}


def _source(kind, typ):
    required, optional = source_keys(kind, typ)
    params = {}
    for key in (*required, *optional):
        if key == 'type':
            continue
        item = {'unit': _UNITS[key], 'shape': [3] if key in _VECTOR_KEYS else []}
        if key in _VECTOR_KEYS:
            item['constraint'] = 'three finite JSON numbers'
            if key in ('normal', 'direction'):
                item['constraint'] += '; nonzero representable length, normalized by the source'
        else:
            item['constraint'] = ('finite and strictly positive' if key in ('radius_m', 'reference_radius_m')
                                  else 'finite and nonnegative' if kind == 'gravity' else 'finite, signed or zero')
        if key in optional:
            item['default'] = list(_GEOMETRY_DEFAULTS[key])
        params[key] = item
    example = {'type': typ}
    for key in required:
        if key == 'type':
            continue
        example[key] = ([0, 0, 1] if key in _VECTOR_KEYS else
                        1.0 if key in ('radius_m', 'reference_radius_m') else
                        1e-9 if kind == 'electric' else 1e6)
    # Construction only: query the actual adapter flag, never evaluate a field.
    model = source_from_dict(kind, example)
    return {'required': list(required), 'optional': list(optional), 'parameters': params,
            'semantics': _SOURCE_MEANING[typ], 'potential_reference': _REFERENCE[typ],
            'trajectory_supported': bool(model.trajectory_safe),
            'motion_caveat': ('Only away from physical singularities; convergence is not certified globally.'
                             if model.trajectory_safe else
                             'Any composition containing this source rejects trajectories, including zero strength.'),
            'example_source': example}


def _static(kind, typ):
    required = static_request_keys(kind, typ)
    request = {'id': typ+'_probe', 'type': typ}
    if typ == 'potential_difference':
        request.update(from_m=[2, 0, 0], to_m=[3, 0, 0])
    else:
        request['position_m'] = [2, 0, 0]
    if typ == 'force':
        request['test_charge_C' if kind == 'electric' else 'test_mass_kg'] = 1e-6 if kind == 'electric' else 1
    vector = typ in ('field', 'force')
    return {'required': list(required), 'optional': ['expectation'],
            'coordinate_shape': [3], 'coordinate_unit': 'm',
            'result_shape': [3] if vector else [],
            'result_unit': ('N' if typ == 'force' else
                            ('N/C' if kind == 'electric' else 'm/s^2') if typ == 'field' else
                            ('V' if kind == 'electric' else 'J/kg')),
            'semantics': ('potential(to_m) - potential(from_m)' if typ == 'potential_difference' else
                          'independent test force: qE or mg; no feedback/self-force' if typ == 'force' else
                          'analytic source evaluation'),
            'coupling_rule': ('test_mass_kg > 0; test_charge_C may be signed or zero' if typ == 'force' else None),
            'example_request': request}


def _event(typ):
    keys = TURNING_ACCURACY_KEYS if typ == 'radial_turning' else EVENT_ACCURACY_KEYS
    request = {'id': typ+'_measurement', 'type': 'trajectory_event', 'particle_index': 0,
               'condition': {'type': typ}, 'occurrence': 'first', 'max_step_s': 0.01,
               'accuracy': {k: 1e-6 if k != 'rtol' else 1e-7 for k in keys}}
    if typ == 'plane':
        request['condition'].update(point_m=[1, 0, 0], normal=[1, 0, 0], direction='negative')
        request['min_normal_speed_m_s'] = 1e-6
        options = {'direction': list(DIRECTIONS)}
    elif typ == 'radial':
        request['condition'].update(center_m=[0, 0, 0], radius_m=1, direction='inward')
        request['min_radial_speed_m_s'] = 1e-6
        options = {'direction': list(RADIAL_DIRECTIONS)}
    else:
        request['condition'].update(center_m=[0, 0, 0], extremum='minimum')
        request.update(min_distance_m=1e-7, min_radial_acceleration_m_s2=1e-6)
        options = {'extremum': list(EXTREMA)}
    result = {
        'required': list(EVENT_REQUIRED[typ]),
        'optional': ['initial_policy'] if typ == 'radial_turning' else [],
        'condition_required': list(CONDITION_REQUIRED[typ]), 'condition_options': options,
        'accuracy_required': list(keys),
        'accuracy_constraints': 'absolute tolerances strictly positive in named SI units; rtol >= 0',
        'accuracy_meaning': 'Agreement between two native runs, not solver settings or a certified error bound.',
        'max_step_s': 'duration_s/10000 <= max_step_s <= duration_s; max_step_s/2 must be positive and representable',
        'measurement_thresholds': 'strictly positive SI values; reject unresolved results, never soften forces',
        'occurrence': 'first detected qualifying positive-time event, not proven mathematically first',
        'initial_policy_default': ('reject initial radial stationarity, centre or unresolved geometry'
                                   if typ == 'radial_turning' else
                                   'reject launch on or numerically unresolved relative to the observation surface'),
        'example_request': request,
    }
    if typ == 'radial_turning':
        result['rest_launch_option'] = {
            'initial_policy': POLICY,
            'requires': ['exactly zero initial velocity', 'resolved nonzero initial distance',
                         'resolved nonzero initial radial acceleration'],
            'excludes': 'Only the launch root, algebraically; no altered initial state or skipped time interval.',
            'limits': 'No nonzero-speed apsidal starts, equilibrium starts, centre roots or degenerate extrema.',
        }
    return result


def get_capabilities() -> dict:
    """Return a fresh, JSON-serializable discovery document. Never run a simulation."""
    source_types = (*REGISTRY, 'uniform')
    return {
        'catalogue_version': 1,
        'format': 'emfeeld.capability_catalogue; descriptive discovery data, not JSON Schema',
        'authority': 'Runtime validation is authoritative. Source keys and observation enums are shared; observation structures and restrictions are checked against it by tests.',
        'commands': {
            'catalogue': 'python -m emfeeld capabilities',
            'save_catalogue': 'python -m emfeeld capabilities --output capabilities.json',
            'validate_packet': 'python -m emfeeld.observations PACKET.json --validate-only',
            'execute_packet': 'python -m emfeeld.observations PACKET.json --output RESULT.json',
            'view_scene': 'python -m emfeeld view SCENE.json',
            'view_packet_note': 'Extract packet.scene as a standalone scene first; view does not accept observation packets.',
            'verify': 'python tools/replay_packets.py MANIFEST.json --output NEW_OUTPUT_DIRECTORY',
        },
        'packet': {'observation_schema_version': 1,
                   'required': ['observation_schema_version', 'scene', 'observations'], 'optional': ['notes'],
                   'scene': 'embedded scene object, never an external path or executable code',
                   'observations': 'nonempty array with unique ids', 'id_pattern': ID_PATTERN,
                   'numbers': 'finite JSON numbers only, no bool/string coercion or implicit unit conversion',
                   'unknown_keys': 'rejected', 'notes': 'string, if supplied'},
        'scene': {'schema_version': 1, 'required': list(SCENE_REQUIRED), 'optional': list(SCENE_OPTIONAL),
                  'title': 'nonempty string', 'kinds': list(KINDS), 'sources': 'nonempty flat JSON array',
                  'bounds_m': '[xmin,xmax,ymin,ymax,zmin,zmax], finite, each min < max; display bounds only',
                  'duration_s': 'finite positive; required if particles is nonempty, otherwise default 1',
                  'samples': {'default': 401, 'minimum': 2, 'maximum': 100000, 'type': 'integer'},
                  'particle': {'required': ['mass_kg', 'position_m', 'velocity_m_s'],
                               'additional_required_electric': ['charge_C'],
                               'mass_kg': 'strictly positive', 'charge_C': 'finite, signed or zero',
                               'position_m': '3-vector, m', 'velocity_m_s': '3-vector, m/s',
                               'gravity_charge_C': 'optional metadata, ignored by gravitational dynamics; not mixed coupling'}},
        'sources_by_kind': {kind: {typ: _source(kind, typ) for typ in source_types} for kind in KINDS},
        'composition': {'same_kind_only': True, 'mixed_electric_gravity': False,
                        'json_nested_groups': False, 'python_nested_superposition': True,
                        'semantics': 'Prescribed fixed sources add fields and potentials; particles never become sources.'},
        'static_observations_by_kind': {kind: {typ: _static(kind, typ) for typ in TYPES} for kind in KINDS},
        'trajectory_sample': {
            'required': list(SAMPLE_REQUIRED), 'optional_union': list(SAMPLE_OPTIONAL),
            'particle_index': 'zero-based integer referring to scene.particles',
            'quantities': {name: {'unit': unit, 'shape': list(shape)} for name, (unit, shape) in QUANTITIES.items()},
            'selectors': {
                'index': {'required': ['sample_index'], 'range': '0 <= index < scene.samples'},
                'exact': {'required': ['time_s', 'time_selection'], 'time_selection': 'exact'},
                'nearest': {'required': ['time_s', 'time_selection', 'max_time_error_s'], 'time_selection': 'nearest'},
            },
            'selection_rules': 'Exactly one selector; time within [0,duration]; exact float64 equality or explicit nearest allowance; no hidden snapping/clamping/interpolation. Ties choose earlier sample.',
            'max_time_error_s': 'finite nonnegative, nearest mode only',
            'solver': {'method': 'DOP853', **SOLVER_SETTINGS, 'max_step_s': 'duration_s/200'},
            'reuse': 'one solve per requested particle per packet, including failures; full horizon must succeed',
        },
        'trajectory_event': {
            'conditions': {typ: _event(typ) for typ in EVENT_REQUIRED},
            'units': dict(UNITS),
            'extra_turning_units': dict(TurningCondition.extra_units),
            'reuse': 'two terminal native searches per distinct request; packet-local duplicate cache, separate from saved states',
            'expectation': 'not accepted; check native event states with a separate verification manifest',
            'limits': ['multiple roots within a step can be missed', 'refinement is not proof of completeness',
                       'no_event is no numerical detection, not proof of no intersection',
                       'local turning point is not global closest approach', 'observation surfaces are not collisions'],
        },
        'expectation': {'available_for': [*TYPES, 'trajectory_sample'], 'required': ['value', 'atol', 'rtol'],
                        'value': 'same shape as the requested value, no broadcasting',
                        'tolerances': 'finite nonnegative; atol in result units, rtol dimensionless',
                        'meaning': 'authored reference check, not independent correctness or solver accuracy'},
        'result_handling': {
            'aggregate': ['ok', 'partial', 'failed'],
            'static_statuses': ['ok', 'domain_error', 'numerical_error'],
            'sample_statuses': ['ok', 'selection_error', 'unsupported_trajectory', 'domain_error', 'numerical_error', 'integration_error'],
            'event_statuses': ['ok', 'no_event', 'initial_condition_error', 'ambiguous_event', 'convergence_error', 'unsupported_trajectory', 'domain_error', 'numerical_error', 'integration_error'],
            'exit_codes': {'0': 'aggregate ok (can contain no_event), or schema-only success',
                           '1': 'local failures/failed expectations; detailed report retained',
                           '2': 'schema, input or I/O error'},
            'must_inspect': 'Check each requested observation, its status, units, shape and value/state; exit 0 alone does not answer an event question.',
        },
        'unsupported': ['conductor polarization/image-charge response', 'moving/self-consistent sources or particle backreaction',
                        'simultaneous electric-plus-gravity coupling', 'relativity and radiation',
                        'shell/plane-source trajectories', 'material collision response',
                        'native inverse/symbolic solving', 'global closest approach/minimum launch speed',
                        'rings/disks/finite rods/nonuniform radial density sources',
                        'arbitrary executable spatial/time-dependent field expressions', 'flux/line-integral observation requests'],
        'python_only_integrals': 'line_contributions and sphere_flux exist in Python; they are not packet observations, and singular-surface flux is not qualified.',
        'authoring_rules': ['Separate supplied, converted, author-derived and illustrative values.',
                            'Do not substitute a prescribed sphere for conductor polarization.',
                            'State restricted field-equivalence domains; do not animate beyond qualified physics.',
                            'Validate the full packet before execution; schema validity does not prove physical interpretation.',
                            'Keep study reference answers separate; compare native results without replacement outputs.'],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='save the same generated JSON printed to stdout')
    args = parser.parse_args(argv)
    try:
        text = json.dumps(get_capabilities(), indent=2, allow_nan=False) + '\n'
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                        dir=args.output.parent, prefix='.emfeeld-', suffix='.json', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(text)
                os.replace(temporary, args.output)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        print(text, end='')
    except (OSError, ValueError) as exc:
        print(f'emfeeld capabilities: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
