"""JEE ideal parallel-plate capacitor, homogeneous full-gap linear dielectric.

The plates look finite in illustrations, but the physics assumes a uniform
interior field and no edge/fringing correction. This is *not* an exact finite-
plate boundary-value solution or a time-dependent battery/charging model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
from pathlib import Path

from scipy.constants import epsilon_0

SCHEMA_VERSION = 1
MODES = ('isolated_charge', 'battery_voltage')
_KEYS = {'lesson_version', 'lesson_type', 'area_m2', 'gap_m',
         'relative_permittivity', 'mode', 'charge_C', 'voltage_V'}


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f'{name} must be a finite real JSON number (not bool/string)')
    try:
        ans = float(value)
    except (TypeError, OverflowError, ValueError) as exc:
        raise ValueError(f'{name} must be representable as finite float64') from exc
    if not math.isfinite(ans):
        raise ValueError(f'{name} must be finite')
    return ans


@dataclass(frozen=True)
class CapacitorState:
    area_m2: float = 0.01
    gap_m: float = 0.005
    relative_permittivity: float = 1.0
    mode: str = 'isolated_charge'
    charge_C: float | None = 1e-9
    voltage_V: float | None = None

    def __post_init__(self):
        for name in ('area_m2', 'gap_m', 'relative_permittivity'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if not 1e-5 <= self.area_m2 <= 0.25:
            raise ValueError('area_m2 must be 1e-5..0.25 m2')
        if not 1e-5 <= self.gap_m <= 0.02:
            raise ValueError('gap_m must be 1e-5..0.02 m')
        if self.gap_m/math.sqrt(self.area_m2) > 0.1:
            raise ValueError('require gap / plate-side <= 0.1: edge effects are excluded')
        if not 1 <= self.relative_permittivity <= 10:
            raise ValueError('relative_permittivity must be 1..10')
        if type(self.mode) is not str or self.mode not in MODES:
            raise ValueError('mode must explicitly be isolated_charge or battery_voltage')
        if self.mode == 'isolated_charge':
            if self.voltage_V is not None or self.charge_C is None:
                raise ValueError('isolated charge requires charge_C only (voltage_V absent)')
            q = _number(self.charge_C, 'charge_C')
            if abs(q) > 1e-4:
                raise ValueError('|charge_C| must be <= 1e-4 C')
            object.__setattr__(self, 'charge_C', q)
        else:
            if self.charge_C is not None or self.voltage_V is None:
                raise ValueError('battery mode requires voltage_V only (charge_C absent)')
            voltage = _number(self.voltage_V, 'voltage_V')
            if abs(voltage) > 1e5:
                raise ValueError('|voltage_V| must be <= 1e5 V')
            object.__setattr__(self, 'voltage_V', voltage)
        # Refuse physics that cannot be represented or falls outside teaching bounds.
        measure(self)

    def to_dict(self):
        result = {'lesson_version': SCHEMA_VERSION,
                  'lesson_type': 'ideal_parallel_plate_capacitor',
                  'area_m2': self.area_m2, 'gap_m': self.gap_m,
                  'relative_permittivity': self.relative_permittivity,
                  'mode': self.mode}
        result['charge_C' if self.mode == 'isolated_charge' else 'voltage_V'] = (
            self.charge_C if self.mode == 'isolated_charge' else self.voltage_V)
        return result


def measure(state):
    """Closed-form electrostatics; +Q lower plate at z=-d/2, -Q upper.

    Signed voltage V = V_lower - V_upper. All output units are SI. A full,
    uniform dielectric has bound charge -P at its lower face, +P at upper.
    Stored *field* energy is not net work performed by a battery.
    """
    if not isinstance(state, CapacitorState):
        raise ValueError('measure requires a CapacitorState')
    cap = epsilon_0 * state.relative_permittivity * state.area_m2 / state.gap_m
    if state.mode == 'isolated_charge':
        q = state.charge_C
        v = q/cap
    else:
        v = state.voltage_V
        q = cap*v
    e = v/state.gap_m
    energy = 0.5*q*v
    polarization = epsilon_0*(state.relative_permittivity-1)*e
    if (not all(math.isfinite(x) for x in (cap,q,v,e,energy,polarization))
            or cap <= 0 or energy < 0 or abs(e) > 1e9):
        raise ValueError('ideal capacitor measurement outside finite bounded range')
    return {
        'capacitance_F': cap,
        'free_lower_plate_charge_C': q,
        'free_upper_plate_charge_C': -q,
        'potential_lower_minus_upper_V': v,
        'field_z_between_N_C': e,
        'stored_field_energy_J': energy,
        'free_surface_density_lower_C_m2': q/state.area_m2,
        'free_surface_density_upper_C_m2': -q/state.area_m2,
        'polarization_z_C_m2': polarization,
        'bound_surface_density_lower_C_m2': -polarization,
        'bound_surface_density_upper_C_m2': polarization,
        'ideal_field_outside_N_C': 0.0,
        'ideal_gap_homogeneous': True,
        'finite_plate_fringing_ignored': True,
        'battery_and_mechanical_work_not_calculated': True,
    }


def field_at_z(state, z_m):
    """One-sided ideal field; plate interfaces deliberately undefined."""
    z = _number(z_m, 'z_m')
    if abs(z) == state.gap_m/2:
        raise ValueError('electric field at an ideal charged plate is one-sided')
    return measure(state)['field_z_between_N_C'] if abs(z) < state.gap_m/2 else 0.0


def potential_at_z(state, z_m):
    """Idealized potential anchored to V_upper=0; continuous at plates."""
    z = _number(z_m, 'z_m')
    data = measure(state)
    e = data['field_z_between_N_C']
    return e * max(0., min(state.gap_m, state.gap_m/2-z))


def from_dict(data):
    if type(data) is not dict or (set(data) - _KEYS):
        raise ValueError('capacitor lesson requires an object with no unknown keys')
    if data.get('lesson_version') != SCHEMA_VERSION or type(data.get('lesson_version')) is not int:
        raise ValueError('unsupported capacitor lesson_version')
    if data.get('lesson_type') != 'ideal_parallel_plate_capacitor':
        raise ValueError('unsupported capacitor lesson_type')
    required = {'lesson_version','lesson_type','area_m2','gap_m','relative_permittivity','mode'}
    if not required.issubset(data):
        raise ValueError('missing required capacitor fields')
    mode = data['mode']
    if mode not in MODES or type(mode) is not str:
        raise ValueError('invalid capacitor mode')
    key = 'charge_C' if mode == 'isolated_charge' else 'voltage_V'
    other = 'voltage_V' if mode == 'isolated_charge' else 'charge_C'
    if key not in data or other in data:
        raise ValueError('exactly one mode-appropriate controlling electrical value required')
    return CapacitorState(area_m2=data['area_m2'], gap_m=data['gap_m'],
             relative_permittivity=data['relative_permittivity'], mode=mode,
             charge_C=data[key] if mode == 'isolated_charge' else None,
             voltage_V=data[key] if mode == 'battery_voltage' else None)


def load_lesson(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError('duplicate capacitor key '+k)
            d[k]=v
        return d
    def nonfinite(value):
        raise ValueError('nonfinite JSON capacitor number: '+value)
    data=json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique,
                    parse_constant=nonfinite)
    return from_dict(data)


def teaching_case(initial, key):
    """Four teacher-created independent equilibria, *not* dynamic transitions."""
    if type(key) is not str or key not in ('1','2','3','4'):
        raise ValueError('unsupported teaching case')
    original = measure(initial)
    mode = 'isolated_charge' if key in ('1','2') else 'battery_voltage'
    return CapacitorState(area_m2=initial.area_m2,gap_m=initial.gap_m,
             relative_permittivity=1. if key in ('1','3') else 4.,
             mode=mode,
             charge_C=original['free_lower_plate_charge_C'] if mode=='isolated_charge' else None,
             voltage_V=original['potential_lower_minus_upper_V'] if mode=='battery_voltage' else None)
