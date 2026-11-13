"""Nonrelativistic test particles in one static prescribed field."""
from dataclasses import dataclass
import numpy as np
from scipy.integrate import solve_ivp
from .fields import Field, scalar, vector


@dataclass(frozen=True)
class Particle:
    mass_kg: float
    position_m: tuple
    velocity_m_s: tuple
    charge_C: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "mass_kg", scalar(self.mass_kg, "mass_kg", positive=True))
        object.__setattr__(self, "charge_C", scalar(self.charge_C, "charge_C"))
        object.__setattr__(self, "position_m", vector(self.position_m, "position_m"))
        object.__setattr__(self, "velocity_m_s", vector(self.velocity_m_s, "velocity_m_s"))


@dataclass(frozen=True)
class Trajectory:
    time_s: np.ndarray
    position_m: np.ndarray
    velocity_m_s: np.ndarray
    kinetic_J: np.ndarray
    potential_J: np.ndarray
    evaluations: int

    @property
    def energy_J(self):
        return self.kinetic_J + self.potential_J

    @property
    def max_energy_drift_J(self):
        return float(np.max(np.abs(self.energy_J - self.energy_J[0])))

    @property
    def normalized_energy_drift(self):
        # Not a guaranteed global error bound; depends on the potential reference.
        scale = max(abs(self.energy_J[0]), self.kinetic_J[0],
                    abs(self.potential_J[0]), np.finfo(float).tiny)
        return self.max_energy_drift_J / scale


def integrate(model: Field, particle: Particle, times, *, rtol=1e-10,
              position_atol_m=1e-9, velocity_atol_m_s=1e-9, max_step_s=np.inf):
    """DOP853. No collisions, backreaction, softening, or discontinuity handling.

    Point/line singularities raise DomainError when evaluated; close encounters
    require convergence tests. Shell/plane dynamics are deliberately not admitted
    until surface-crossing events have been qualified. Fields remain available.
    """
    if not model.trajectory_safe:
        raise ValueError("shell/plane trajectory crossings are not yet qualified")
    t = np.asarray(times, dtype=float)
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("times must be at least two finite, strictly increasing values")
    rtol = scalar(rtol, "rtol", positive=True)
    atol = [scalar(position_atol_m, "position_atol_m", positive=True)] * 3
    atol += [scalar(velocity_atol_m_s, "velocity_atol_m_s", positive=True)] * 3
    if max_step_s != np.inf:
        max_step_s = scalar(max_step_s, "max_step_s", positive=True)
    coupling = particle.charge_C if model.kind == "electric" else particle.mass_kg
    acceleration_factor = coupling / particle.mass_kg
    initial = np.array((*particle.position_m, *particle.velocity_m_s))
    model.field(initial[:3])
    model.potential(initial[:3])

    def rhs(_t, state):
        return np.concatenate((state[3:], acceleration_factor * model.field(state[:3])))

    solution = solve_ivp(rhs, (t[0], t[-1]), initial, t_eval=t, method="DOP853",
                         rtol=rtol, atol=atol, max_step=max_step_s)
    if not solution.success:
        raise RuntimeError(f"trajectory integration failed: {solution.message}")
    if not np.isfinite(solution.y).all():
        raise RuntimeError("trajectory integration produced nonfinite state values")
    r, v = solution.y[:3].T, solution.y[3:].T
    kinetic = 0.5 * particle.mass_kg * np.sum(v * v, axis=1)
    potential = coupling * model.potential(r)
    if not np.isfinite(kinetic).all() or not np.isfinite(potential).all():
        raise RuntimeError("trajectory energies are nonfinite; check units and parameter scales")
    return Trajectory(solution.t, r, v, kinetic, potential, solution.nfev)
