"""Reviewer F1: author-token underflow and nonzero SI measurement refusal."""
import json
import math

import pytest

from emfeeld.capacitor_lesson import CapacitorState, load_lesson, measure


@pytest.mark.parametrize('token', ('1e-400', '-1e-400', '1e-10000', '-1e-10000'))
def test_nonzero_raw_json_underflow_is_refused_before_zero_conversion(tmp_path, token):
    baseline = json.dumps(CapacitorState().to_dict())
    assert '"charge_C": 1e-09' in baseline
    f = tmp_path / 'input.json'
    f.write_text(baseline.replace('"charge_C": 1e-09', '"charge_C": ' + token))
    with pytest.raises(ValueError, match='not representable as float64'):
        load_lesson(f)


@pytest.mark.parametrize('token', ('0.0', '-0.0', '0e-9999', '-0e-9999'))
def test_exact_zero_json_remains_valid(tmp_path, token):
    baseline = json.dumps(CapacitorState().to_dict())
    f = tmp_path / 'input.json'
    f.write_text(baseline.replace('"charge_C": 1e-09', '"charge_C": ' + token))
    s = load_lesson(f)
    assert measure(s)['stored_field_energy_J'] == 0
    assert measure(s)['free_lower_plate_charge_C'] == 0


@pytest.mark.parametrize('q', (1e-170, -1e-170, 5e-324, -5e-324, 1e-19, -1e-19))
def test_subnormal_or_too_small_nonzero_controlling_charge_is_refused(q):
    with pytest.raises(ValueError, match='zero or 1e-18'):
        CapacitorState(charge_C=q)


@pytest.mark.parametrize('v', (5e-324, -5e-324, 1e-170, -1e-170, 1e-13, -1e-13))
def test_subnormal_or_too_small_nonzero_controlling_voltage_is_refused(v):
    with pytest.raises(ValueError, match='zero or 1e-12'):
        CapacitorState(mode='battery_voltage', charge_C=None, voltage_V=v)


def test_derived_voltage_below_bounded_contract_is_refused():
    # This q by itself passes its lower bound, but a very high C would make
    # its *derived* voltage fall below the safe admitted SI teaching range.
    with pytest.raises(ValueError, match='underflow or below teaching bounds'):
        CapacitorState(area_m2=0.25, gap_m=1e-5,
                       relative_permittivity=10, charge_C=1e-18)


def test_derived_free_charge_below_bounded_contract_is_refused():
    # Explicit nonzero V is individually valid; derived Q would not be.
    with pytest.raises(ValueError, match='underflow or below teaching bounds'):
        CapacitorState(area_m2=1e-5, gap_m=2e-4, relative_permittivity=1,
                       mode='battery_voltage', charge_C=None, voltage_V=1e-12)


@pytest.mark.parametrize('mode,polarity', [('isolated_charge', -1), ('isolated_charge', 1),
                                            ('battery_voltage', -1), ('battery_voltage', 1)])
def test_valid_small_nonzero_report_remains_signed_nonzero(mode, polarity):
    state = (CapacitorState(charge_C=polarity*1e-18, relative_permittivity=4)
             if mode == 'isolated_charge' else
             CapacitorState(mode=mode, charge_C=None,
                            voltage_V=polarity*1e-6, relative_permittivity=4))
    m = measure(state)
    for key in ('free_lower_plate_charge_C', 'potential_lower_minus_upper_V',
                'field_z_between_N_C', 'free_surface_density_lower_C_m2',
                'polarization_z_C_m2'):
        assert math.isfinite(m[key]) and m[key] != 0
        assert math.copysign(1, m[key]) == polarity
    assert m['stored_field_energy_J'] > 0


def test_nonzero_underflow_guard_in_measure_defensive_against_bypassed_state_validation():
    # A frozen dataclass can still be abused by object.__setattr__. This is
    # not an admitted public input, but measure must never publish a zero U
    # for a physically nonzero Q/V state even under such a misuse.
    state = CapacitorState()
    object.__setattr__(state, 'charge_C', 1e-170)
    with pytest.raises(ValueError, match='underflow or below teaching bounds'):
        measure(state)
