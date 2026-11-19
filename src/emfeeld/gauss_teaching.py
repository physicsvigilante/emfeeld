"""Explicit synthetic conceptual examples, not original examination questions.

Presets use the initial surface's center/scale/orientation and first signed charge.
They replace the charge list intentionally. Reset restores the original authored
state. No preset encodes an answer: all readouts come from gauss_lesson.measure.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .gauss_lesson import GaussState, GaussianCube, GaussianSphere, HeldCharge


@dataclass(frozen=True)
class TeachingCase:
    key: str
    title: str
    question: str

    def question_for(self, surface):
        if isinstance(surface, GaussianSphere):
            return {'center': 'Is local E dot n uniform over this centered sphere?',
                    'offcenter': 'Is local E dot n uniform? Does the total change?'}.get(self.key, self.question)
        return self.question


CASES = (
    TeachingCase('center', '1 / Centered charge', 'Are all six cube-face fluxes equal?'),
    TeachingCase('offcenter', '2 / Same charge, moved inside', 'Which face gains flux? Does the total change?'),
    TeachingCase('outside', '3 / Charge outside', 'Can zero total flux coexist with a nonzero field?'),
    TeachingCase('zero_net', '4 / Equal and opposite inside', 'Does zero enclosed net charge imply zero field?'),
)


def teaching_state(initial, key):
    if not isinstance(initial, GaussState):
        raise ValueError('requires a validated GaussState')
    if key not in {case.key for case in CASES}:
        raise ValueError('unknown teaching case')
    q = initial.charges[0].charge_C
    if q == 0:
        raise ValueError('teaching cases require a nonzero first charge; use the supplied example')
    s = initial.surface
    rotation = np.asarray(s.rotation) if isinstance(s, GaussianCube) else np.eye(3)
    offsets = {'center': [(0., 0., 0.)], 'offcenter': [(.6, .2, 0.)],
               'outside': [(2., 0., 0.)], 'zero_net': [(.4, .1, 0.), (-.4, -.1, 0.)]}[key]
    charges = tuple(HeldCharge(q if i == 0 else -q,
                    tuple(np.asarray(s.center_m) + initial.scale_m * (rotation @ np.asarray(p))))
                    for i, p in enumerate(offsets))
    return GaussState(s, charges)
