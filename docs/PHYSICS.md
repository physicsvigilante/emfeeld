# Initial physics and authoring contract

**2026-11-13 correction:** line/plane boundary classification now conservatively rejects numerically unresolved locations, and shell classification uses the same policy. Resolved values retain the ideal-source formulas below; there is no physical cutoff or softening. Nested source geometry is traversed recursively, with unsupported geometry explicitly disclosed. See [the R1/R2 correction contract and validation](CORRECTION_R1_R2.md). Desktop rendering and independent review remain pending.

All positions and radii are metres, time seconds, mass kilograms, and charge coulombs. Electric field is N/C and potential V. Gravitational field is acceleration in m/s^2 and potential is J/kg. Constants come from `scipy.constants`; run outputs record the installed SciPy version and actual values of G and epsilon_0.

## Shared analytic convention

For compact sources let `c = k Q` (electric) or `c = -G M` (gravity), with `k = 1/(4 pi epsilon_0)`, displacement `d`, and `r = |d|`. In both domains `field = -gradient(potential)`.

| Source | Potential | Field |
|---|---|---|
| Point | c/r | c d/r^3 |
| Uniform solid sphere, r <= R | c (3 - r^2/R^2)/(2R) | c d/R^3 |
| Uniform solid sphere, r >= R | c/r | c d/r^3 |
| Thin spherical shell, r < R | c/R | zero |
| Thin spherical shell, r > R | c/r | c d/r^3 |

The sphere expressions agree at R. Shell potential is continuous; shell field is not assigned at exactly R. At a point-source center, both potential and field raise `DomainError`. A zero-strength source returns zero, including at its otherwise singular location. No finite softening parameter is introduced.

For an infinite line, c uses linear charge/mass density, rho is perpendicular distance to its axis, and `V = -2c log(rho/rho_ref)`, `field = 2c d_perp/rho^2`. A finite positive `rho_ref` is mandatory in JSON. The axis is singular. Directions are normalized.

For an infinite plane, c uses surface charge/mass density, n is its normalized normal, and `s = (position-center) dot n`: `V = -2 pi c |s|`, `field = 2 pi c sign(s) n`. Potential is zero on the plane; field on the ideal sheet is not assigned.

A uniform field f has `V = -f dot (position-origin)`, zero at the chosen origin. Compact source potentials are zero at infinity. Infinite line/plane potentials cannot use that convention. The superposed potential retains the sum of these explicit choices.

Electric strengths may be signed. Negative gravitational source masses/densities are rejected. Coordinates, parameters and input arrays must be finite. This initial double-precision implementation is not certified for arbitrary extreme magnitudes or near-singular encounters.

## Composition and trajectories

`Superposition` adds prescribed source fields/potentials of the same physical kind; nested Python compositions are allowed. Arbitrary translated/oriented supported sources need not have combined Gauss-law symmetry. This is not a solver for an unknown charge distribution. Ideal conducting spheres/planes responding to nearby charges require separate boundary-condition-aware models.

A particle accelerates by `(q/m) E` or `g`; its potential energy is `q V` or `m Phi`. Source distributions are fixed. Particles have no feedback on sources or on each other. A solid sphere has no implied mechanical contact surface. A nonrelativistic assumption is required; no relativistic solver or automatic speed certification is supplied.

DOP853 evaluates the analytic source directly, never the viewer grid. The API exposes rtol, separate position/velocity absolute tolerances and max_step. CLI examples use rtol=1e-10, position atol=1e-9 m, velocity atol=1e-9 m/s and max_step=duration/200. Sampling density is for output/playback, not the force calculation.

No collision or stop-surface event model is implemented. Nonzero shell/plane fields are discontinuous; this slice conservatively rejects *all* trajectories containing shell/plane sources, even if an intended trajectory would not cross them. Point/line sources are usable away from singularities, but fail if the integrator evaluates a singular point. Close encounters need separate convergence checks. This restriction is explicit rather than disguised as successful collision handling.

Energy diagnostics include max absolute drift and a normalized drift divided by `max(|E_initial|, K_initial, |U_initial|, smallest_positive_normal_float)`. The normalization depends on the potential reference. It is an observation, not a rigorous global trajectory-error bound. Angular-momentum conservation is tested only for the central-force orbit, not asserted for arbitrary fields.

## Integral computations

`line_contributions` evaluates midpoint sums of `field dot dl` along an explicitly supplied polyline. The negative sum approximates endpoint potential difference. Refine the polyline to test convergence; sampling a singularity raises.

`sphere_flux` uses Gauss-Legendre quadrature in cos(theta) and a periodic midpoint rule in phi. It returns positions, outward normals, positive area *weights*, and signed contributions. Weights are not actual mesh-patch areas. This does not certify surfaces that intersect singular sources. No invalid quadrature point is silently removed. An external source can have positive and negative contributions while its net flux is zero.

## Display contract

The initial optional PyVista preview uses equal-length arrows for direction, a potential-coloured central z slice, source geometry, precomputed trajectory curves and a nearest-sample time slider. It does not yet provide field lines, equipotential surfaces, animation playback, or integral visualizations. Undefined field/potential samples become NaN holes, not zero fields. Geometry for infinite lines/planes is truncated only for display. Point and particle marker sizes are schematic.

The display backend is not a physics dependency. Real Linux/PyVista offscreen captures and programmatic time events are now verified for the recorded scenes and environment; see `VIEWER_QUALIFICATION.md`. Camera margins and legend placement are display-only. Time-label updates preserve authored axis bounds and formatting. Windows mouse interaction remains untested; no independent review is implied.

## Implementation references

- SciPy constants: https://docs.scipy.org/doc/scipy/reference/constants.html
- SciPy DOP853: https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.DOP853.html
- PyVista mesh plotting: https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_mesh
- PyVista slider callbacks: https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_slider_widget

These are implementation references, not evidence that the viewer ran.
