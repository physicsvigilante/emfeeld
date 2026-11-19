"""Synthetic conceptual questions, not independently solved exam originals."""
import numpy as np
import pytest
from scipy.constants import epsilon_0
from emfeeld.gauss_lesson import GaussState, GaussianCube, GaussianSphere, HeldCharge, measure
from emfeeld.gauss_presentation import build_presentation
from emfeeld.gauss_teaching import CASES, teaching_state


@pytest.mark.parametrize('surface', [GaussianCube(), GaussianSphere(),
    GaussianCube((3., 2., 1.), 4., ((0., -1., 0.), (1., 0., 0.), (0., 0., 1.)))])
@pytest.mark.parametrize('q', [1e-9, -2e-9])
def test_questions_have_computed_not_hardcoded_results(surface, q):
    initial = GaussState(surface, (HeldCharge(q, surface.center_m),))
    before = initial.to_dict()
    data = {case.key: build_presentation(teaching_state(initial, case.key), resolution=6) for case in CASES}
    assert initial.to_dict() == before
    for key in ('center', 'offcenter'):
        assert data[key].report['exact_total_N_m2_per_C'] == q / epsilon_0
    for key in ('outside', 'zero_net'):
        assert data[key].report['exact_total_N_m2_per_C'] == 0
        assert np.max(np.abs(data[key].field_N_C)) > 0
        assert np.min(data[key].normal_field_N_C) < 0 < np.max(data[key].normal_field_N_C)
    if isinstance(surface, GaussianCube):
        np.testing.assert_allclose(data['center'].report['face_flux_N_m2_per_C'], q/epsilon_0/6)
        face = np.asarray(data['offcenter'].report['face_flux_N_m2_per_C'])
        assert np.ptp(face) > abs(q/epsilon_0)*.1
        assert abs(sum(face)-q/epsilon_0) < abs(q/epsilon_0)*1e-13
        assert data['outside'].report['face_flux_N_m2_per_C'][0] * q < 0


def test_preset_refusals_do_not_silently_change_zero_charge():
    with pytest.raises(ValueError): teaching_state(GaussState(), 'invented')
    with pytest.raises(ValueError): teaching_state(GaussState(charges=(HeldCharge(0, (0,0,0)),)), 'center')


def test_sphere_prompts_do_not_invent_cube_faces():
    for case in CASES:
        assert 'face' not in case.question_for(GaussianSphere())
    assert 'six cube-face' in CASES[0].question_for(GaussianCube())
