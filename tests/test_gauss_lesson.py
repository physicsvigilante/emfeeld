"""Physical references and boundary refusals for Issue #46 Gaussian flux core."""
from dataclasses import replace
import math

import numpy as np
import pytest
from scipy.constants import epsilon_0

from emfeeld.fields import DomainError
from emfeeld.gauss_lesson import GaussianCube, GaussianSphere, HeldCharge


def test_cube_centre_equal_six_faces_not_constant_field_assumption():
    result = GaussianCube().flux([HeldCharge(1e-9, (0., 0., 0.))])
    np.testing.assert_allclose(result["face_flux_N_m2_per_C"],
                               np.full(6, 1e-9/(6*epsilon_0)), rtol=2e-14)
    assert result["exact_total_N_m2_per_C"] == pytest.approx(1e-9/epsilon_0)
    assert result["sum_faces_N_m2_per_C"] == pytest.approx(result["exact_total_N_m2_per_C"], rel=1e-14)


@pytest.mark.parametrize("q", [1e-9, -2e-9])
@pytest.mark.parametrize("p", [(.4, -.3, .7), (-.85, .8, .65), (0., 0., 0.)])
def test_offcentre_and_sign(q, p):
    flux = GaussianCube().flux([HeldCharge(q, p)])
    assert flux["sum_faces_N_m2_per_C"] == pytest.approx(q/epsilon_0, rel=2e-13, abs=2e-14)
    if p != (0., 0., 0.):
        assert np.ptp(flux["face_flux_N_m2_per_C"]) > 0.01*abs(q/epsilon_0)


@pytest.mark.parametrize("p", [(3., 0., 0.), (1.5, .6, -.4), (-1.3, -1.8, 2.1)])
def test_exterior_face_flux_cancels_without_zero_local_field(p):
    flux = GaussianCube().flux([HeldCharge(1e-9, p)])
    assert flux["exact_total_N_m2_per_C"] == 0
    assert flux["sum_faces_N_m2_per_C"] == pytest.approx(0, abs=2e-13)
    assert min(flux["face_flux_N_m2_per_C"]) < 0 < max(flux["face_flux_N_m2_per_C"])


def test_cube_rigid_motion_covariance():
    rot = ((0., -1., 0.), (1., 0., 0.), (0., 0., 1.))
    original = GaussianCube()
    moved = GaussianCube(center_m=(2, -3, 4), rotation=rot)
    original_position = np.array((.6, -.3, .2))
    transformed = np.asarray((2, -3, 4)) + np.asarray(rot) @ original_position
    a = original.flux([HeldCharge(1e-9, tuple(original_position))])
    b = moved.flux([HeldCharge(1e-9, tuple(transformed))])
    np.testing.assert_allclose(a["face_flux_N_m2_per_C"], b["face_flux_N_m2_per_C"], rtol=1e-14, atol=1e-14)


def test_two_equal_opposite_charges_cancel_total_not_faces():
    result = GaussianCube().flux([HeldCharge(1e-9, (.7, 0, 0)), HeldCharge(-1e-9, (-.7, 0, 0))])
    assert result["exact_total_N_m2_per_C"] == 0
    assert abs(result["sum_faces_N_m2_per_C"]) < 1e-13
    assert max(abs(v) for v in result["face_flux_N_m2_per_C"]) > 1.


@pytest.mark.parametrize("p", [(1., 0., 0.), (1., 1., 0.), (1., 1., 1.),
                                (1.-1e-15, 0., 0.), (-1., .2, -.3)])
def test_cube_charge_on_face_edge_corner_or_unresolved_is_undefined(p):
    with pytest.raises(DomainError):
        GaussianCube().flux([HeldCharge(1e-9, p)])


@pytest.mark.parametrize("p", [(1., 0., 0.), (0., 0., -1.), (1.-1e-15, 0., 0.)])
def test_sphere_boundary_refused(p):
    with pytest.raises(DomainError):
        GaussianSphere().flux([HeldCharge(1e-9, p)])


def test_sphere_central_flux_and_unrenormalized_quadrature():
    q = HeldCharge(1e-9, (0., 0., 0.))
    s = GaussianSphere()
    result = s.flux([q], n_polar=8, n_azimuth=16)
    assert result["exact_total_N_m2_per_C"] == pytest.approx(1e-9/epsilon_0)
    assert result["sampled_total_N_m2_per_C"] == pytest.approx(1e-9/epsilon_0, rel=5e-15)
    assert result["unrenormalized"] is True


def test_sphere_offcentre_refinement_and_outside():
    s = GaussianSphere()
    q = HeldCharge(1e-9, (.6, .1, 0.))
    coarse = s.flux([q], n_polar=8, n_azimuth=16)
    fine = s.flux([q], n_polar=48, n_azimuth=96)
    assert abs(fine["sampling_error_N_m2_per_C"]) < abs(coarse["sampling_error_N_m2_per_C"])
    outside = s.flux([HeldCharge(1e-9, (0, 0, 2))])
    assert outside["exact_total_N_m2_per_C"] == 0
    assert abs(outside["sampled_total_N_m2_per_C"]) < 1e-10


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), 1e-30, 2e-3])
def test_invalid_charge_refusal(bad):
    with pytest.raises(ValueError):
        HeldCharge(bad, (0., 0., 0.))


def test_left_handed_rotation_rejected():
    with pytest.raises(ValueError):
        GaussianCube(rotation=((-1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))


def test_no_material_charge_or_field_rescaling():
    r = GaussianCube().flux([HeldCharge(0., (0., 0., 0.))])
    assert r["sum_faces_N_m2_per_C"] == 0
    assert r["unrenormalized"] is True
