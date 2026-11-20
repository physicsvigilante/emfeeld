"""No-graphics, immutable SI 3D data and genuine physical/dispay separation."""
import json
import subprocess
import sys

import numpy as np
import pytest
from scipy.constants import mu_0
from emfeeld.wire_magnetism import WireState, measure, magnetic_field
from emfeeld.wire_presentation import prepare


def test_import_presentation_does_not_import_pyvista_or_vtk():
    p=subprocess.run([sys.executable,'-c',
      'import sys, emfeeld.wire_presentation; assert not any(x.startswith(("pyvista","vtk")) for x in sys.modules)'],
      capture_output=True,text=True,check=True)
    assert p.returncode==0


@pytest.mark.parametrize('axis',((0,0,1),(1,0,0),(1,2,3)))
@pytest.mark.parametrize('I',(-10,0,10))
def test_snapshot_arrays_physical_consistency_detached_readonly(axis,I):
    s=WireState(axis_direction=axis,current_A=I,origin_m=(2,-1,4),loop_radius_m=.38)
    d=prepare(s)
    for array in [d.loop_positions_m,d.tangent_unit,d.magnetic_field_T,
                  d.arc_weights_m,d.loop_display_xyz,d.arrow_display_origins_xyz,
                  d.arrow_display_vectors,d.wire_display_endpoints_xyz]:
        assert not array.flags.writeable
        with pytest.raises(ValueError):array.setflags(write=True)
        with pytest.raises(ValueError):array.flat[0]=0
    with pytest.raises(TypeError):d.report['field_magnitude_T']=99
    assert np.allclose(d.magnetic_field_T,magnetic_field(s,d.loop_positions_m))
    assert np.allclose(d.report['sampled_ampere_circulation_T_m'],
                       np.sum(np.einsum('ij,ij->i',d.magnetic_field_T,d.tangent_unit)*d.arc_weights_m))
    assert d.report['expected_mu0_I_T_m']==mu_0*I
    assert np.allclose(d.loop_display_xyz,(d.loop_positions_m-s.origin_m)/s.loop_radius_m)
    assert np.allclose(np.linalg.norm(d.loop_display_xyz,axis=1),1,rtol=1e-12)
    assert np.allclose(d.wire_display_endpoints_xyz[0],-d.wire_display_endpoints_xyz[1])
    assert d.arrow_display_vectors.shape[0]==d.arrow_display_origins_xyz.shape[0]
    assert np.allclose(np.linalg.norm(d.arrow_display_vectors,axis=1),.42 if I else 0,atol=1e-13)
    assert d.report['field_magnitude_T']==pytest.approx(measure(s)['field_magnitude_T'])


def test_write_is_not_mutable_across_independent_preparations():
    s=WireState(current_A=10)
    a=prepare(s);b=prepare(s)
    assert a is not b
    assert not np.shares_memory(a.magnetic_field_T,b.magnetic_field_T)
    assert np.array_equal(a.magnetic_field_T,b.magnetic_field_T)


def test_loop_signed_integral_is_not_renderer_glyph_length():
    small=prepare(WireState(current_A=5,loop_radius_m=.1))
    large=prepare(WireState(current_A=5,loop_radius_m=.2))
    assert large.report['field_magnitude_T']==pytest.approx(small.report['field_magnitude_T']/2)
    assert small.report['sampled_ampere_circulation_T_m']==pytest.approx(large.report['sampled_ampere_circulation_T_m'])
    assert np.allclose(np.linalg.norm(small.arrow_display_vectors,axis=1),
                       np.linalg.norm(large.arrow_display_vectors,axis=1))
