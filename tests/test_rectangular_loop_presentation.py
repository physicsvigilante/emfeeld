"""Read-only physical sample vectors and presentation arrow boundaries."""
import numpy as np
import pytest

from emfeeld.rectangular_loop_torque import RectangularLoopState, calculate
from emfeeld.rectangular_loop_presentation import prepare


def test_readonly_fields_and_deep_immutable_report():
    s=RectangularLoopState(centre_m=(1, 2, 3), tilt_deg=50)
    p=prepare(s)
    fields=("loop_corners_m", "side_midpoints_m", "edge_vectors_m",
            "normal_unit", "field_B_T", "magnetic_moment_A_m2",
            "torque_N_m", "segment_forces_N", "loop_display_xyz",
            "side_force_vectors_display_xyz", "field_B_direction_display_xyz",
            "magnetic_moment_display_xyz", "torque_direction_display_xyz")
    for name in fields:
        arr=getattr(p,name)
        assert not arr.flags.writeable
        with pytest.raises(ValueError):
            arr.reshape(-1)[0]=999
    with pytest.raises(TypeError):
        p.report["orientation_potential_J"]=999
    for name in ("field_B_xyz_T", "moment_xyz_A_m2", "torque_xyz_N_m",
                 "net_force_xyz_N", "segment_torque_xyz_N_m"):
        assert isinstance(p.report[name], tuple)
        with pytest.raises(TypeError):
            p.report[name][0]=999
    original, _=calculate(s)
    assert p.loop_corners_m==pytest.approx(original["loop_corners_m"])
    assert p.segment_forces_N==pytest.approx(original["forces_N"])


def test_distinct_display_reference_not_used_for_si_forces():
    s=RectangularLoopState(width_m=.4,height_m=.2,tilt_deg=55)
    p=prepare(s,reference_length_m=.4)
    q=prepare(s,reference_length_m=1.)
    assert p.report==q.report
    assert np.array_equal(p.segment_forces_N,q.segment_forces_N)
    assert np.max(np.abs(p.loop_display_xyz))>np.max(np.abs(q.loop_display_xyz))
    assert p.reference_length_m==pytest.approx(.4)
    assert q.reference_length_m==pytest.approx(1.)
    assert np.linalg.norm(p.field_B_direction_display_xyz)==pytest.approx(.85)
    assert np.linalg.norm(p.magnetic_moment_display_xyz)==pytest.approx(.68)
    assert np.linalg.norm(p.torque_direction_display_xyz)==pytest.approx(.73)


def test_signed_glyphs_reversal_zero_and_fixed_positive_normal():
    positive=prepare(RectangularLoopState(tilt_deg=90))
    negative=prepare(RectangularLoopState(tilt_deg=90,current_A=-3))
    reverse_B=prepare(RectangularLoopState(tilt_deg=90,field_strength_T=-.2))
    assert np.array_equal(positive.positive_normal_display_xyz,
                          negative.positive_normal_display_xyz)
    assert np.array_equal(positive.positive_normal_display_xyz,
                          reverse_B.positive_normal_display_xyz)
    assert negative.current_direction_display_xyz==pytest.approx(
        -positive.current_direction_display_xyz)
    assert negative.magnetic_moment_display_xyz==pytest.approx(-positive.magnetic_moment_display_xyz)
    assert negative.torque_direction_display_xyz==pytest.approx(
        -positive.torque_direction_display_xyz)
    assert reverse_B.field_B_direction_display_xyz==pytest.approx(
        -positive.field_B_direction_display_xyz)
    assert reverse_B.magnetic_moment_display_xyz==pytest.approx(positive.magnetic_moment_display_xyz)
    assert reverse_B.torque_direction_display_xyz==pytest.approx(
        -positive.torque_direction_display_xyz)
    for state in (RectangularLoopState(current_A=0),
                  RectangularLoopState(field_strength_T=0)):
        p=prepare(state)
        assert not np.any(p.torque_direction_display_xyz)
        assert not np.any(p.side_force_vectors_display_xyz)
    assert not np.any(prepare(RectangularLoopState(current_A=0)).magnetic_moment_display_xyz)
    assert not np.any(prepare(RectangularLoopState(field_strength_T=0)).field_B_direction_display_xyz)


@pytest.mark.parametrize("bad",[True,"1",-1,0.00001,1000,float("inf")])
def test_invalid_display_reference_refused(bad):
    with pytest.raises(ValueError):
        prepare(RectangularLoopState(),reference_length_m=bad)


def test_tiny_nonzero_torque_direction_does_not_numerically_underflow():
    s=RectangularLoopState(tilt_deg=1e-200, current_A=3, field_strength_T=.2)
    p=prepare(s)
    assert p.report["torque_magnitude_N_m"]>0
    assert np.linalg.norm(p.torque_direction_display_xyz)==pytest.approx(.73)


def test_default_reference_is_valid_and_derived_from_initial_dimensions():
    s=RectangularLoopState(width_m=.6,height_m=.4)
    assert prepare(s,reference_length_m=None).reference_length_m==pytest.approx(.6)
