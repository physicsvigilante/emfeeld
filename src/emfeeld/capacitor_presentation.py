"""Renderer-neutral, detached, immutable capacitor drawing data. No PyVista or VTK."""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
import numpy as np

from .capacitor_lesson import CapacitorState, measure


def _readonly(values):
    a=np.ascontiguousarray(values,dtype=float)
    return np.frombuffer(a.tobytes(),dtype=a.dtype).reshape(a.shape)


@dataclass(frozen=True,eq=False)
class CapacitorPresentation:
    state: CapacitorState
    measurements: MappingProxyType
    lower_plate_xyz: np.ndarray
    upper_plate_xyz: np.ndarray
    arrow_origins_xyz: np.ndarray
    field_arrows_xyz: np.ndarray
    field_sample_positions_m: np.ndarray
    field_samples_N_C: np.ndarray
    display_gap_exaggeration: float
    dielectric_visible: bool


def prepare(state):
    """Physical SI samples and display-only normalized geometry kept distinct.

    Scene x/y scale is sqrt(A); scene z scale is d. This exaggerates the gap
    by sqrt(A)/d; it is EXPLICITLY schematic and has no role in the physics.
    """
    if not isinstance(state,CapacitorState):
        raise ValueError('prepare requires a CapacitorState')
    m=measure(state)
    side=math.sqrt(state.area_m2)
    grid=(-.32,0.,.32)
    xyz=np.array([(x,y,z) for x in grid for y in grid for z in (-.24,.24)])
    pos_m=np.array([[x*side,y*side,z*state.gap_m] for x,y,z in xyz])
    e=m['field_z_between_N_C']
    vectors=np.tile([0.,0.,e],(len(xyz),1))
    if e:
        arrows=xyz.copy()
        # Direction-only glyphs. Their length is intentionally not E magnitude.
        arrows[:,2]= .40 if e < 0 else -.40
        arr_vec=np.tile([0.,0.,(-.25 if e<0 else .25)],(len(arrows),1))
    else:
        arrows=np.empty((0,3));arr_vec=np.empty((0,3))
    xy=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
    return CapacitorPresentation(state,MappingProxyType(m),
         _readonly(np.column_stack((xy,np.full(4,-.5)))),
         _readonly(np.column_stack((xy,np.full(4,.5)))),
         _readonly(arrows),_readonly(arr_vec),
         _readonly(pos_m),_readonly(vectors),
         side/state.gap_m,state.relative_permittivity>1)
