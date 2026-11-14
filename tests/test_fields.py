import numpy as np
import pytest
from numpy.testing import assert_allclose
from emfeeld import (PointSource, SolidSphere, SphericalShell, InfiniteLine,
                     InfinitePlane, UniformField, Superposition, DomainError)
from emfeeld.fields import K, G

FACTORIES = [PointSource, SolidSphere, SphericalShell, InfiniteLine, InfinitePlane]


@pytest.mark.parametrize('kind,c', [('electric', K), ('gravity', -G)])
@pytest.mark.parametrize('factory', FACTORIES)
def test_exact_field_and_potential(factory, kind, c):
    source = factory(kind, 2)
    if factory is PointSource:
        p, e, v = [2,0,0], [c/2,0,0], c
    elif factory is SolidSphere:
        p, e, v = [0.5,0,0], [c,0,0], 2.75*c
    elif factory is SphericalShell:
        p, e, v = [0.5,0,0], [0,0,0], 2*c
    elif factory is InfiniteLine:
        p, e, v = [2,0,3], [2*c,0,0], -4*c*np.log(2)
    else:
        p, e, v = [1,2,-3], [0,0,-4*np.pi*c], -12*np.pi*c
    assert_allclose(source.field(p), e, rtol=1e-14, atol=0)
    assert_allclose(source.potential(p), v, rtol=1e-14, atol=0)


@pytest.mark.parametrize('kind', ['electric', 'gravity'])
@pytest.mark.parametrize('factory', FACTORIES)
def test_negative_potential_gradient(factory, kind):
    source = factory(kind, 1, center=(0.2,-0.3,0.4))
    for p in [np.array([2.,3.,4.]), np.array([0.4,0.1,0.5])]:
        h = 1e-5
        gradient = np.array([(source.potential(p+h*a)-source.potential(p-h*a))/(2*h)
                             for a in np.eye(3)])
        assert_allclose(-gradient, source.field(p), rtol=1e-7, atol=abs(source.coefficient)*1e-9)


@pytest.mark.parametrize('factory', FACTORIES)
def test_vectorization_translation_zero_strength(factory):
    a = factory('electric', 1)
    shift = np.array([2.,3.,4.])
    b = factory('electric', 1, center=shift)
    p = np.array([[[2.,0.,2.],[0.,3.,3.]],[[4.,0.,4.],[5.,0.,5.]]])
    assert a.field(p).shape == p.shape
    assert a.potential(p).shape == (2,2)
    assert_allclose(a.field(p), b.field(p+shift))
    assert_allclose(a.potential(p), b.potential(p+shift))
    zero = factory('electric', 0)
    assert_allclose(zero.field([0,0,0]), [0,0,0])
    assert zero.potential([0,0,0]) == 0
    assert zero.field(np.empty((0,3))).shape == (0,3)


def test_sphere_shell_inside_outside_boundary():
    sphere, shell, point = SolidSphere('electric', 1), SphericalShell('electric', 1), PointSource('electric', 1)
    assert_allclose(sphere.field([0,0,0]), [0,0,0])
    assert sphere.potential([0,0,0]) == pytest.approx(1.5*K)
    assert shell.potential([0,0,0]) == K
    assert_allclose(sphere.field([1,0,0]), [K,0,0])
    assert_allclose(sphere.potential([1,0,0]), K)
    assert_allclose(shell.potential([1,0,0]), K)
    with pytest.raises(DomainError):
        shell.field([1,0,0])
    for source in (sphere, shell):
        assert_allclose(source.field([2,3,4]), point.field([2,3,4]))
        assert_allclose(source.potential([2,3,4]), point.potential([2,3,4]))


def test_singularities_and_plane_limits():
    for source in (PointSource('electric', 1), InfiniteLine('gravity', 1)):
        for fn in (source.field, source.potential):
            with pytest.raises(DomainError):
                fn([0,0,0])
    plane = InfinitePlane('electric', 1)
    assert plane.potential([0,0,0]) == 0
    with pytest.raises(DomainError):
        plane.field([0,0,0])
    assert_allclose(plane.field([0,0,1]), -plane.field([0,0,-1]))


def test_direction_rotation_and_reference():
    line = InfiniteLine('electric', 1, direction=(2,0,0), reference_radius=2)
    assert line.potential([4,2,0]) == 0
    assert_allclose(line.field([4,2,0]), [0,K,0])
    plane = InfinitePlane('electric', 1, normal=(5,0,0))
    assert_allclose(plane.field([2,4,0]), [2*np.pi*K,0,0])
    uniform = UniformField('gravity', (1,2,3), (4,5,6))
    assert uniform.potential([4,5,6]) == 0
    assert_allclose(uniform.potential([5,6,7]), -6)
    assert_allclose(uniform.field([[1,2,3],[4,5,6]]), [[1,2,3],[1,2,3]])


def test_arbitrary_nested_superposition():
    sources = tuple(SolidSphere('electric', (-1)**i*(i+1)*1e-9, center=(i,0,0), radius=0.2)
                    for i in range(9))
    nested = Superposition((Superposition(sources[:4]), Superposition(sources[4:])))
    p = np.array([[0.1,0.2,0.3],[4,5,6]])
    assert_allclose(nested.field(p), sum(s.field(p) for s in sources))
    assert_allclose(nested.potential(p), sum(s.potential(p) for s in sources))
    assert nested.trajectory_safe
    assert not Superposition((sources[0], InfinitePlane('electric', 1))).trajectory_safe
    with pytest.raises(ValueError):
        Superposition(())
    with pytest.raises(ValueError):
        Superposition((sources[0], PointSource('gravity', 1)))


@pytest.mark.parametrize('kwargs', [dict(kind='other',strength=1),dict(kind='gravity',strength=-1),
                                   dict(kind='electric',strength=np.nan),dict(kind='electric',strength=True),
                                   dict(kind='electric',strength=1,center=[0,1])])
def test_invalid_source(kwargs):
    with pytest.raises(ValueError):
        PointSource(**kwargs)


@pytest.mark.parametrize('factory,kwargs', [(SolidSphere,{'radius':0}), (SphericalShell,{'radius':-1}),
    (InfiniteLine,{'direction':(0,0,0)}), (InfiniteLine,{'reference_radius':0}),
    (InfinitePlane,{'normal':(0,0,0)})])
def test_invalid_geometry(factory, kwargs):
    with pytest.raises(ValueError):
        factory('electric',1,**kwargs)


@pytest.mark.parametrize('p', [[1,2], 1, [0,np.nan,0], [[1,2,3],[4,np.inf,6]]])
def test_invalid_observation_points(p):
    with pytest.raises(ValueError):
        PointSource('electric',1).field(p)
