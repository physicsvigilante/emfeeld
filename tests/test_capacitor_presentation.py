import numpy as np
import pytest

from emfeeld.capacitor_lesson import CapacitorState, measure
from emfeeld.capacitor_presentation import prepare


def test_prepared_data_finite_detached_immutable():
    s=CapacitorState(relative_permittivity=4.)
    p=prepare(s)
    assert dict(p.measurements)==measure(s)
    assert p.display_gap_exaggeration==20
    assert p.dielectric_visible
    assert p.lower_plate_xyz.shape==(4,3)
    assert np.all(p.lower_plate_xyz[:,2]==-.5)
    assert np.all(p.upper_plate_xyz[:,2]==.5)
    assert np.all(p.field_samples_N_C[:,2] == measure(s)['field_z_between_N_C'])
    assert np.all((p.field_sample_positions_m[:,2] <s.gap_m/2)
                 & (p.field_sample_positions_m[:,2]>-s.gap_m/2))
    for a in (p.lower_plate_xyz,p.upper_plate_xyz,p.arrow_origins_xyz,
              p.field_arrows_xyz,p.field_sample_positions_m,p.field_samples_N_C):
        assert not a.flags.writeable
        with pytest.raises(ValueError):a.setflags(write=True)
        with pytest.raises(ValueError):a.flat[0]=9
    with pytest.raises(TypeError):p.measurements['capacitance_F']=5


def test_nonzero_arrows_are_schematic_and_signed():
    pos=prepare(CapacitorState())
    neg=prepare(CapacitorState(charge_C=-1e-9))
    zero=prepare(CapacitorState(charge_C=0.))
    assert np.all(pos.field_arrows_xyz[:,2]>.0)
    assert np.all(neg.field_arrows_xyz[:,2]<.0)
    assert zero.field_arrows_xyz.shape==(0,3)
    assert not pos.dielectric_visible
    assert pos.field_arrows_xyz.shape==(18,3)


def test_new_state_creates_separate_arrays():
    p=prepare(CapacitorState())
    q=prepare(CapacitorState(relative_permittivity=5.))
    assert p.state != q.state
    assert p.lower_plate_xyz is not q.lower_plate_xyz
    assert p.measurements['capacitance_F'] != q.measurements['capacitance_F']
