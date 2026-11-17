"""Independent R2-01/02/03 numerical limits; preserve the original source law.

The reviewer demonstrated that finite physics values were rejected or mislabeled
at extreme but float64-representable radii. These are *real* science regressions,
not exceptions to hide by relaxing tolerances or changing stored evidence.
"""
import math
from copy import deepcopy

import numpy as np
import pytest

from emfeeld.fields import DomainError, G, K, SolidSphere, SphericalShell
from emfeeld.observations import evaluate_observations, run_packet


@pytest.mark.parametrize('points', [[0, 0, 0], [[0, 0, 0], [0, 0, 0]]])
def test_r2_01_large_but_finite_sphere_centre_has_finite_potential(points):
    source = SolidSphere('electric', 1e298, radius=10)
    expected = (source.coefficient / 10) * 1.5
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        value = source.potential(points)
    np.testing.assert_allclose(value, expected, rtol=2e-15)
    row = evaluate_observations(source, [{'id':'interior','type':'potential','position_m':[0,0,0]}])[0]
    assert row['status'] == 'ok'
    assert row['value'] == pytest.approx(expected, rel=2e-15)


@pytest.mark.parametrize('cls', [SolidSphere, SphericalShell])
@pytest.mark.parametrize('kind, strength, base', [
    ('electric', 1e-180, K),
    ('gravity', 1e-300, -G),
])
def test_r2_02_representable_exterior_has_true_potential_and_field(cls,kind,strength,base):
    source = cls(kind, strength, radius=1e-200)
    d = 1e-170
    expected_potential = base * (strength/d)
    expected_field = expected_potential/d
    # Scalar, array, and mixed inside/outside probes must all have correct shape.
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        v = source.potential([d, 0., 0.])
        e = source.field([d, 0., 0.])
        values = source.potential([[0,0,0], [d,0,0], [2*d,0,0]])
        fields = source.field([[0,0,0], [d,0,0], [2*d,0,0]])
    assert math.isclose(float(v), expected_potential, rel_tol=2e-15)
    np.testing.assert_allclose(e, [expected_field,0,0], rtol=2e-15)
    assert values.shape==(3,) and fields.shape==(3,3)
    assert values[1] == pytest.approx(expected_potential, rel=2e-15)
    assert values[2] == pytest.approx(expected_potential/2, rel=2e-15)
    np.testing.assert_allclose(fields[1], [expected_field,0,0], rtol=2e-15)
    np.testing.assert_allclose(fields[2], [expected_field/4,0,0], rtol=2e-15)
    native = evaluate_observations(source, [
        {'id':'V','type':'potential','position_m':[d,0,0]},
        {'id':'E','type':'field','position_m':[d,0,0]},
    ])
    assert [row['status'] for row in native] == ['ok','ok']
    assert native[0]['value'] == pytest.approx(expected_potential, rel=2e-15)
    np.testing.assert_allclose(native[1]['value'],[expected_field,0,0],rtol=2e-15)


@pytest.mark.parametrize('cls', [SolidSphere, SphericalShell])
def test_r2_02_coeff_underflows_but_physics_potential_is_finite(cls):
    # In a plain float64 expression, (-G * 1e-315) underflows to zero.
    # The true potential and field remain representable at this distance.
    source=cls('gravity',1e-315,radius=1e-200)
    d=1e-170
    expected_v=-G*(1e-315/d)
    expected_field=expected_v/d
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        assert float(source.potential([d,0,0]))==pytest.approx(expected_v,rel=2e-15)
        np.testing.assert_allclose(source.field([d,0,0]),[expected_field,0,0],rtol=2e-15)


def test_r2_01_true_overflow_does_not_fabricate_finite_answer():
    source=SolidSphere('electric',1e298,radius=1e-200)
    row=evaluate_observations(source,[{'id':'overflow','type':'potential','position_m':[0,0,0]}])[0]
    assert row['status']=='numerical_error' and row['value'] is None
    assert row['error']['code']=='nonfinite_or_invalid_result'
    with np.errstate(over='raise', divide='raise',invalid='raise'):
        with pytest.raises((FloatingPointError, OverflowError)):
            source.field([1e-201,0,0])


def test_r2_02_shell_surface_remains_undefined_and_zero_source_remains_zero():
    source=SphericalShell('electric',1e-180,radius=1e-200)
    with pytest.raises(DomainError,match='surface'):
        source.field([1e-200,0.,0.])
    for cls in (SphericalShell,SolidSphere):
        zero=cls('electric',0.,radius=1e-200)
        with np.errstate(over='raise',divide='raise',invalid='raise'):
            np.testing.assert_array_equal(zero.field([[0,0,0],[1e-170,0,0]]),np.zeros((2,3)))
            np.testing.assert_array_equal(zero.potential([[0,0,0],[1e-170,0,0]]),np.zeros(2))


def _invalid_grid_packet(duration,samples):
    return {
      'observation_schema_version':1,
      'scene': {'schema_version':1,'title':'R2 invalid float64 time grid',
                'kind':'gravity','sources':[{'type':'uniform','field_m_s2':[0,0,0]}],
                'particles':[{'mass_kg':1,'position_m':[0,0,0],'velocity_m_s':[0,0,0]},
                             {'mass_kg':2,'position_m':[0,0,0],'velocity_m_s':[0,0,0]}],
                'duration_s':duration,'samples':samples,'bounds_m':[-1,1,-1,1,-1,1]},
      'observations':[{'id':f'r{i}','type':'trajectory_sample','quantity':'position',
                       'particle_index':i,'sample_index':0} for i in range(2)],
    }


@pytest.mark.parametrize('duration,samples',[(2e-323,31),(5e-324,2)])
def test_r2_03_requested_and_capture_invalid_grid_record_exact_no_attempt(monkeypatch,duration,samples):
    import emfeeld.trajectory_samples as ts
    def forbidden(*a,**kw):
        pytest.fail('integration was invoked despite already rejected saved-time grid')
    monkeypatch.setattr(ts,'integrate',forbidden)
    packet=_invalid_grid_packet(duration,samples)
    unchanged=deepcopy(packet)
    request_only=run_packet(packet)
    capture={}
    with_capture=run_packet(packet,capture=capture)
    assert packet==unchanged
    assert request_only['status']=='failed' and with_capture['status']=='failed'
    assert request_only['counts']['numerical_errors']==2
    assert with_capture['counts']['numerical_errors']==2
    for report in (request_only,with_capture):
        assert list(report['trajectory_runs']) == ['0','1']
        assert [row['error']['code'] for row in report['results']] == ['unresolvable_time_grid']*2
        for index in range(2):
            row=report['trajectory_runs'][str(index)]
            assert row['particle_index']==index
            assert row['status']=='numerical_error'
            assert row['error']['code']=='unresolvable_time_grid'
            assert row['integration_attempted'] is False
            assert report['results'][index]['diagnostics_key']==str(index)
    assert capture['trajectories']==(None,None)
    assert request_only['trajectory_runs'] == with_capture['trajectory_runs']


def test_r2_03_selection_only_rejections_still_never_create_false_run_record(monkeypatch):
    import emfeeld.trajectory_samples as ts
    monkeypatch.setattr(ts,'integrate',lambda *a,**kw: pytest.fail('selector rejected'))
    p=_invalid_grid_packet(1,11)
    p['observations']=[{'id':'off_grid','type':'trajectory_sample','quantity':'position',
                         'particle_index':0,'time_s':0.35,'time_selection':'exact'}]
    report=run_packet(p)
    assert report['results'][0]['error']['code']=='time_not_saved'
    assert report['trajectory_runs']=={}
