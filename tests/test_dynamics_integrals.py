import numpy as np
import pytest
from numpy.testing import assert_allclose
from emfeeld import (PointSource, SolidSphere, SphericalShell, InfinitePlane, UniformField,
                     Superposition, Particle, integrate, sphere_flux, line_contributions)
from emfeeld.fields import G, K, epsilon_0


@pytest.mark.parametrize('kind', ['gravity','electric'])
def test_uniform_acceleration(kind):
    model = UniformField(kind, (1,-2,0.5))
    particle = Particle(2, (0,1,2), (3,2,1), charge_C=-6)
    times = np.linspace(0,3,61)
    result = integrate(model,particle,times)
    a = np.array(model.value) * (-3 if kind == 'electric' else 1)
    assert_allclose(result.position_m, particle.position_m + times[:,None]*particle.velocity_m_s
                    + times[:,None]**2*a/2, atol=1e-10)
    assert_allclose(result.velocity_m_s, particle.velocity_m_s + times[:,None]*a, atol=1e-10)
    assert result.normalized_energy_drift < 1e-12


def test_circular_orbit_closure_energy_angular_momentum():
    model = PointSource('gravity', 1/G)
    times = np.linspace(0,2*np.pi,501)
    result = integrate(model,Particle(1,(1,0,0),(0,1,0)),times,max_step_s=0.05)
    expected = np.column_stack((np.cos(times),np.sin(times),np.zeros_like(times)))
    assert_allclose(result.position_m,expected,atol=1e-9)
    assert_allclose(np.cross(result.position_m,result.velocity_m_s),
                    np.tile([0,0,1],(len(times),1)),atol=1e-10)
    assert result.normalized_energy_drift < 1e-10


def test_solid_sphere_interior_harmonic_motion():
    model = SolidSphere('gravity', 1/G, radius=1)
    times = np.linspace(0,2*np.pi,301)
    result = integrate(model,Particle(1,(0.5,0,0),(0,0,0)),times,max_step_s=0.05)
    assert_allclose(result.position_m[:,0],0.5*np.cos(times),atol=1e-9)
    assert_allclose(result.velocity_m_s[:,0],-0.5*np.sin(times),atol=1e-9)


def test_superposed_forces_and_gravitational_mass_independence():
    sources = (UniformField('gravity',(1,0,0)),UniformField('gravity',(0,2,0)))
    model = Superposition(sources)
    times = np.linspace(0,2,21)
    a=integrate(model,Particle(1,(0,0,0),(0,0,0)),times)
    b=integrate(model,Particle(20,(0,0,0),(0,0,0)),times)
    assert_allclose(a.position_m,b.position_m)
    assert_allclose(a.position_m[-1],[2,4,0],atol=1e-10)


@pytest.mark.parametrize('model', [SphericalShell('electric',1),InfinitePlane('gravity',1)])
def test_discontinuous_dynamics_rejected(model):
    with pytest.raises(ValueError,match='not yet qualified'):
        integrate(model,Particle(1,(2,0,0),(0,0,0),1),[0,1])


@pytest.mark.parametrize('times', [[0],[0,0],[1,0],[0,np.nan],[[0,1]]])
def test_bad_times(times):
    with pytest.raises(ValueError):
        integrate(UniformField('gravity',(0,0,0)),Particle(1,(0,0,0),(0,0,0)),times)


@pytest.mark.parametrize('kwargs', [{'mass_kg':0},{'mass_kg':-1},{'mass_kg':1,'charge_C':np.inf},
                                    {'mass_kg':1,'position_m':[0,1]}])
def test_bad_particle(kwargs):
    options=dict(mass_kg=1,position_m=(0,0,0),velocity_m_s=(0,0,0))
    options.update(kwargs)
    with pytest.raises(ValueError):
        Particle(**options)


@pytest.mark.parametrize('kind,strength,expected', [('electric',1e-9,1e-9/epsilon_0),('gravity',2,-8*np.pi*G)])
def test_gaussian_flux_and_area(kind,strength,expected):
    for source in [PointSource(kind,strength),SolidSphere(kind,strength),SphericalShell(kind,strength)]:
        result=sphere_flux(source,(0,0,0),2)
        assert_allclose(result.total,expected,rtol=2e-14)
        assert_allclose(result.area_weights_m2.sum(),16*np.pi,rtol=1e-14)
    interior=sphere_flux(SolidSphere(kind,strength),(0,0,0),0.5)
    assert_allclose(interior.total,expected/8,rtol=1e-14)
    assert sphere_flux(SphericalShell(kind,strength),(0,0,0),0.5).total == 0


def test_offcenter_enclosed_charge_and_external_charge_flux():
    inner=PointSource('electric',1e-9,center=(0.2,0.1,0.3))
    outer=PointSource('electric',-2e-9,center=(4,0,0))
    result=sphere_flux(Superposition((inner,outer)),(0,0,0),1)
    assert_allclose(result.total,1e-9/epsilon_0,rtol=1e-10)
    external=sphere_flux(outer,(0,0,0),1)
    assert abs(external.total) < 1e-10
    assert np.any(external.contributions>0) and np.any(external.contributions<0)


def test_line_integral_convergence_and_path_independence():
    field=PointSource('electric',1/K)
    errors=[]
    for n in (20,40,80):
        vertices=np.column_stack((np.linspace(1,2,n+1),np.zeros(n+1),np.zeros(n+1)))
        errors.append(abs(line_contributions(field,vertices).sum()-0.5))
    assert errors[1] < errors[0]/3.9 and errors[2] < errors[1]/3.9
    theta=np.linspace(0,np.pi/2,1001)
    arc=np.column_stack((np.cos(theta),np.sin(theta),np.zeros_like(theta)))
    assert abs(line_contributions(field,arc).sum()) < 1e-12
    straight=np.column_stack((np.linspace(1,0,1001),np.linspace(0,1,1001),np.zeros(1001)))
    assert abs(line_contributions(field,straight).sum()) < 1e-12


def test_integral_validation():
    model=UniformField('electric',(1,2,3))
    for n in [0,1,2.5,True]:
        with pytest.raises(ValueError):
            sphere_flux(model,(0,0,0),1,n_polar=n)
    with pytest.raises(ValueError):
        line_contributions(model,[[0,0,0]])
