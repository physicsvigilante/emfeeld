"""Boundary arithmetic tests; no new field law, tolerance, or solver behavior."""
import numpy as np
import pytest

from emfeeld.fields import SolidSphere, SphericalShell, K, G
from emfeeld.observations import run_packet


@pytest.mark.parametrize('kind,strength,coefficient', [
    ('electric', 1e-9, K*1e-9),
    ('gravity', 2., -G*2.),
    ('electric', 0., 0.),
])
def test_sphere_exterior_does_not_compute_overflowing_unused_interior(kind, strength, coefficient):
    source = SolidSphere(kind, strength, radius=1e-160)
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        value = source.potential([1e10, 0., 0.])
    assert float(value) == pytest.approx(coefficient/1e10, rel=2e-15, abs=0)


def test_sphere_mixed_inside_and_outside_samples_remain_analytic():
    source = SolidSphere('electric', 1e-9, radius=1e-150)
    points = [[0.,0.,0.],[1e-150,0.,0.],[1e10,0.,0.]]
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        values = source.potential(points)
    expected = [1.5*K*1e-9/1e-150,K*1e-9/1e-150,K*1e-9/1e10]
    np.testing.assert_allclose(values, expected, rtol=2e-15, atol=0)


def test_captured_unresolvable_time_grid_is_an_honest_failure_not_a_crash(monkeypatch):
    import emfeeld.trajectory_samples as samples
    monkeypatch.setattr(samples, 'integrate', lambda *a, **kw: pytest.fail('an already invalid grid reached the solver'))
    packet = {
        'observation_schema_version':1,
        'scene':{'schema_version':1,'title':'Subnormal-grid admission test','kind':'gravity',
                 'sources':[{'type':'uniform','field_m_s2':[0,0,0]}],
                 'particles':[{'mass_kg':1,'position_m':[0,0,0],'velocity_m_s':[0,0,0]}],
                 'duration_s':5e-324,'samples':3,'bounds_m':[-1,1,-1,1,-1,1]},
        'observations':[{'id':'position','type':'trajectory_sample','quantity':'position',
                         'particle_index':0,'sample_index':0}],
    }
    capture={}
    report=run_packet(packet,capture=capture)
    assert report['status']=='failed'
    assert report['results'][0]['status']=='numerical_error'
    assert report['results'][0]['error']['code']=='unresolvable_time_grid'
    assert capture['trajectories']==(None,)
    recorded=report['trajectory_runs']['0']
    assert recorded['status']=='numerical_error'
    assert recorded['integration_attempted'] is False


@pytest.mark.parametrize('source_type', [SolidSphere, SphericalShell])
def test_zero_strength_tiny_sphere_field_is_exactly_zero_without_unused_division(source_type):
    source = source_type('electric', 0., radius=1e-160)
    points = [[0., 0., 0.], [5e-161, 0., 0.], [1., 0., 0.]]
    with np.errstate(over='raise', divide='raise', invalid='raise', under='ignore'):
        result = source.field(points)
    np.testing.assert_array_equal(result, np.zeros((3, 3)))
