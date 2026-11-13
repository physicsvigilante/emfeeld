"""R1: mathematical boundaries, resolved controls, and conservative uncertainty.

Expectations use authored integer geometry and analytic values, not the private
classification helpers. This is numerical testing, not arbitrary-range proof.
"""
import numpy as np
import pytest
from numpy.testing import assert_allclose
from emfeeld import (DomainError, InfiniteLine, InfinitePlane, SphericalShell,
                     Particle, integrate, line_contributions)
from emfeeld.fields import K, G
from emfeeld.viewer import sample_values

KINDS = [('electric', K * 1e-9), ('gravity', -G * 1e-9)]
SCALES = [2.0**-30, 1.0, 2.0**30]
CENTERS = [(0, 0, 0), (3, -5, 7)]


@pytest.mark.parametrize('kind,c', KINDS)
@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('center', CENTERS)
def test_oblique_line_boundaries_and_resolved_values(kind, c, scale, center):
    center = scale * np.array(center)
    for axis in (np.array([1., 1., 1.]), np.array([1., 2., 3.])):
        source = InfiniteLine(kind, 1e-9, center=center, direction=axis,
                              reference_radius=scale)
        for t in (-7, 0, 3):
            point = center + t * scale * axis
            for fn in (source.field, source.potential):
                with pytest.raises(DomainError, match='numerically unresolved'):
                    fn(point)
        # Exactly perpendicular, with an independently known squared length.
        u = np.array([axis[1], -axis[0], 0.])
        for offset in (1., 2.0**-12):
            perpendicular = scale * offset * u
            rho2 = scale**2 * offset**2 * np.dot(u, u)
            points = np.array([center + t * scale * axis + perpendicular
                               for t in (-7, 0, 3)])
            expected = np.broadcast_to(2 * c * perpendicular / rho2, points.shape)
            assert_allclose(source.field(points), expected, rtol=2e-10,
                            atol=abs(c / scale / offset) * 2e-10)
            assert_allclose(source.potential(points),
                            -2 * c * np.log(offset * np.sqrt(np.dot(u, u))),
                            rtol=2e-10, atol=abs(c) * 2e-10)


@pytest.mark.parametrize('kind,c', KINDS)
@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('center', CENTERS)
def test_oblique_plane_boundaries_and_resolved_sides(kind, c, scale, center):
    center = scale * np.array(center)
    n = np.array([1., 3., 7.])
    tangent = np.array([7., 0., -1.])
    source = InfinitePlane(kind, 1e-9, center=center, normal=n)
    for t in (-7, 0, 3):
        boundary = center + t * scale * tangent
        with pytest.raises(DomainError):
            source.field(boundary)
        assert np.isfinite(source.potential(boundary))
        for side in (-1, 1):
            distance_factor = scale * side * 2.0**-12
            point = boundary + distance_factor * n
            assert_allclose(source.field(point), side * 2 * np.pi * c * n / np.sqrt(59),
                            rtol=2e-14, atol=0)
            assert_allclose(source.potential(point),
                            -2 * np.pi * c * abs(distance_factor) * np.sqrt(59),
                            rtol=2e-10, atol=0)


@pytest.mark.parametrize('kind,c', KINDS)
@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('center', CENTERS)
def test_shell_oblique_surface_and_resolved_sides(kind, c, scale, center):
    center = scale * np.array(center)
    source = SphericalShell(kind, 1e-9, center=center, radius=7 * scale)
    radial = scale * np.array([2., 3., 6.])  # Length exactly 7 * scale.
    with pytest.raises(DomainError):
        source.field(center + radial)
    assert_allclose(source.potential(center + radial), c / (7 * scale), rtol=2e-15)
    inside = center + (1 - 2.0**-20) * radial
    outside = center + (1 + 2.0**-20) * radial
    assert_allclose(source.field(inside), [0, 0, 0], atol=0)
    r_out = 7 * scale * (1 + 2.0**-20)
    assert_allclose(source.field(outside), c * (outside - center) / r_out**3,
                    rtol=3e-14, atol=0)
    assert_allclose(source.potential(inside), c / (7 * scale), rtol=2e-15)
    assert_allclose(source.potential(outside), c / r_out, rtol=2e-15)


@pytest.mark.parametrize('kind,c', KINDS)
def test_nonzero_but_unresolved_offsets_rejected_not_softened(kind, c):
    cases = [
        (InfiniteLine(kind, 1e-9, direction=(1, 1, 1)),
         [1, 1, np.nextafter(1., 2.)]),
        (InfinitePlane(kind, 1e-9, normal=(1, 3, 7)),
         [np.nextafter(7., 8.), 0, -1]),
        (SphericalShell(kind, 1e-9), [np.nextafter(1., 2.), 0, 0]),
    ]
    for source, point in cases:
        with pytest.raises(DomainError, match='numerically unresolved'):
            source.field(point)
        if isinstance(source, InfiniteLine):
            with pytest.raises(DomainError):
                source.potential(point)
        else:
            assert np.isfinite(source.potential(point))


@pytest.mark.parametrize('kind,c', KINDS)
def test_no_fixed_physical_cutoff_or_tangential_coordinate_cutoff(kind, c):
    # These tiny offsets are fully resolved: large unrelated coordinates must
    # not produce an artificial exclusion tube/slab of fixed physical thickness.
    line = InfiniteLine(kind, 1e-9)
    assert_allclose(line.field([1e-20, 0, 1e8]), [2*c/1e-20, 0, 0], rtol=2e-15)
    plane = InfinitePlane(kind, 1e-9)
    assert_allclose(plane.field([1e8, -1e8, 1e-20]), [0, 0, 2*np.pi*c], rtol=2e-15)
    shell = SphericalShell(kind, 1e-9, radius=1e-20)
    assert_allclose(shell.field([2e-20, 0, 0]), [c/(2e-20)**2, 0, 0], rtol=2e-15)


@pytest.mark.parametrize('kind,c', KINDS)
def test_large_translation_exposes_coordinate_uncertainty(kind, c):
    center = np.array([2.0**40, 2.0**40, 0])
    line = InfiniteLine(kind, 1e-9, center=center)
    with pytest.raises(DomainError):
        line.field(center + [2.0**-11, 0, 1])
    assert_allclose(line.field(center + [16, 0, 1]), [c/8, 0, 0], rtol=2e-15)


@pytest.mark.parametrize('kind,c', KINDS)
def test_direction_scaling_sign_and_vectorized_evaluation(kind, c):
    points = np.array([[[4., 5., 6.], [2., -1., 1.]],
                       [[-4., 3., 1.], [0., -2., 7.]]])
    for factory, parameter in ((InfiniteLine, 'direction'), (InfinitePlane, 'normal')):
        original = factory(kind, 1e-9, **{parameter: (1, 3, 7)})
        for multiplier in (-2.0**20, 2.0**-20):
            changed = factory(kind, 1e-9, **{parameter: multiplier*np.array([1, 3, 7])})
            assert_allclose(changed.field(points), original.field(points), rtol=1e-13, atol=0)
            assert_allclose(changed.potential(points), original.potential(points), rtol=1e-13, atol=0)
        assert original.field(np.empty((0, 3))).shape == (0, 3)
        assert original.potential(np.empty((0, 3))).shape == (0,)


@pytest.mark.parametrize('kind,c', KINDS)
def test_zero_strength_exemption_and_viewer_holes(kind, c):
    cases = [
        (InfiniteLine, {'direction': (1, 1, 1)}, [1, 1, 1], [1, -1, 0]),
        (InfinitePlane, {'normal': (1, 3, 7)}, [7, 0, -1], [1, 1, 1]),
        (SphericalShell, {}, [1, 0, 0], [2, 0, 0]),
    ]
    for factory, kwargs, boundary, valid in cases:
        points = np.array([boundary, valid], dtype=float)
        zero = factory(kind, 0, **kwargs)
        assert_allclose(zero.field(points), np.zeros((2, 3)), atol=0)
        assert_allclose(zero.potential(points), np.zeros(2), atol=0)
        source = factory(kind, 1e-9, **kwargs)
        with pytest.raises(DomainError):
            source.field(points)
        samples = sample_values(source, points)
        assert np.isnan(samples[0]).all()
        assert_allclose(samples[1], source.field(valid), rtol=2e-15)
        potentials = sample_values(source, points, potential=True)
        if factory is InfiniteLine:
            assert np.isnan(potentials[0])
        else:
            assert np.isfinite(potentials).all()


@pytest.mark.parametrize('kind,c', KINDS)
def test_oblique_field_remains_negative_potential_gradient(kind, c):
    point = np.array([2., -1., 4.])
    for source in (InfiniteLine(kind, 1e-9, direction=(1, 3, 7)),
                   InfinitePlane(kind, 1e-9, normal=(1, 3, 7)),
                   SphericalShell(kind, 1e-9)):
        h = 1e-5
        gradient = np.array([(source.potential(point+h*a)-source.potential(point-h*a))/(2*h)
                             for a in np.eye(3)])
        assert_allclose(-gradient, source.field(point), rtol=2e-8, atol=abs(c)*1e-9)


def test_downstream_motion_and_integral_do_not_hide_axis_errors():
    source = InfiniteLine('electric', 1e-9, direction=(1, 1, 1))
    with pytest.raises(DomainError):
        integrate(source, Particle(1, (1, 1, 1), (0, 0, 0), 1e-6), [0, 1])
    with pytest.raises(DomainError):
        line_contributions(source, [[0, 1, 2], [2, 1, 0]])
