"""Display caution is not a new flux rule or a numerical acceptance tolerance."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest
from scipy.constants import epsilon_0

from emfeeld.gauss_lesson import GaussState, GaussianSphere, HeldCharge, measure
from emfeeld.gauss_view import _sampling_caution


@pytest.mark.parametrize('q', [1e-18, -1e-18, 1e-9, -1e-9, 1e-3, -1e-3])
@pytest.mark.parametrize('x,warn', [(0., False), (.6, False), (.9999, True),
                                   (1.0001, True), (2., False)])
def test_caution_for_inside_outside_both_signs_and_charge_scales(q, x, warn):
    state = GaussState(surface=GaussianSphere(), charges=(HeldCharge(q, (x, 0, 0)),))
    report = measure(state)
    original = deepcopy(report)
    advice = _sampling_caution(state, report)
    assert advice['large_discrepancy'] is warn
    assert advice['charge_flux_scale_N_m2_per_C'] == abs(q) / epsilon_0
    assert advice['absolute_discrepancy_N_m2_per_C'] == abs(report['sampling_error_N_m2_per_C'])
    assert advice['is_accuracy_certificate'] is False
    assert report == original == measure(state)
    assert report['unrenormalized'] is True


@pytest.mark.parametrize('second_position,warn', [((0, 0, 0), True), ((-.9999, 0, 0), False)])
def test_zero_net_charge_does_not_divide_by_exact_flux_or_certify_cancellation(second_position, warn):
    state = GaussState(surface=GaussianSphere(), charges=(
        HeldCharge(1e-9, (.9999, 0, 0)), HeldCharge(-1e-9, second_position)))
    report = measure(state)
    assert report['exact_total_N_m2_per_C'] == 0
    advice = _sampling_caution(state, report)
    assert advice['large_discrepancy'] is warn
    assert advice['charge_flux_scale_N_m2_per_C'] == 2e-9 / epsilon_0
    # Symmetric quadrature errors may cancel; no banner does not certify sampling.
    assert advice['is_accuracy_certificate'] is False


def test_all_zero_sources_have_zero_scale_without_zero_division():
    state = GaussState(surface=GaussianSphere(), charges=(HeldCharge(0, (0, 0, 0)),))
    advice = _sampling_caution(state, measure(state))
    assert not advice['large_discrepancy']
    assert advice['charge_flux_scale_N_m2_per_C'] == 0
    assert advice['attention_threshold_N_m2_per_C'] == 0


@pytest.mark.parametrize('x', [1., 1.+1e-15])
def test_undefined_boundary_has_no_stale_numerical_caution(x):
    state = GaussState(surface=GaussianSphere(), charges=(HeldCharge(1e-9, (x, 0, 0)),))
    report = measure(state)
    assert report['exact_total_N_m2_per_C'] is None
    assert _sampling_caution(state, report) is None


def test_cube_does_not_get_sphere_sampling_advice():
    state = GaussState()
    assert _sampling_caution(state, measure(state)) is None


@pytest.mark.parametrize('offset,expected', [(-1, False), (0, False), (1, True)])
def test_attention_threshold_is_strictly_display_only(offset, expected):
    state = GaussState(surface=GaussianSphere())
    report = measure(state)
    threshold = .01 * (1e-9 / epsilon_0)
    # Test the display comparator, not a manufactured physical reference.
    report['sampling_error_N_m2_per_C'] = (
        math.nextafter(threshold, math.inf if offset > 0 else -math.inf)
        if offset else threshold)
    before = deepcopy(report)
    assert _sampling_caution(state, report)['large_discrepancy'] is expected
    assert report == before
