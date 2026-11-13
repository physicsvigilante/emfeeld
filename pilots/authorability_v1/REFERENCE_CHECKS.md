# Analytic reference checks

These are assistant-derived checks of the specified source models, not copied answer-key evidence or an independent reviewer. k = 1/(4 pi epsilon_0), using the recorded SciPy constant. Source givens, choices and page locations remain separate in cases.json. The engine is evaluated first; reference formulas are used only for comparisons.

- **SC-55:** displacement (6,-8,0) m has length 10 m. F = k (50 microC)(2 microC) (6,-8,0)/10^3. The test charge is excluded from its own field.
- **SC-35:** at 0 < z < 3a, contributions are (-sigma,-2sigma,-sigma)/(2 epsilon_0) along z, hence E_z = -2 sigma/epsilon_0.
- **SC-96:** at the centre of the chosen square, V = 0; E = (0,-4 sqrt(2) k q/a^2,0). Opposite potentials cancel while all vertical field contributions add.
- **SC-122:** Q_inner = Q r^2/(r^2+R^2), Q_outer = Q R^2/(r^2+R^2); centre V = k Q(r+R)/(r^2+R^2).
- **MC-33:** V(z) = 4kq/sqrt(a^2+z^2); E_z(z) = 4kqz/(a^2+z^2)^(3/2). Transverse components cancel.
- **SC-158:** enclosed line length is 2 sqrt(R^2-y^2), so analytic total flux is 2 lambda sqrt(R^2-y^2)/epsilon_0. This supplies the reference, not a replacement implementation for the unqualified native quadrature.
- **SC-99:** for negative charge -q in E = -E yhat, acceleration is +qE/m yhat. x = vt, y = qEt^2/(2m), K = mv^2/2 + qEy. Option A describes only a kinetic-energy gain, not total K.
- **SC-28:** release distances to both sources are 2a; distances at O are a. Energy gives speed at O = sqrt(2kQq/(ma)). The observation code extracts speed from saved states rather than reusing this formula as its answer.
- **SOL-26:** V(x,y,0) = kQ/r_plus - 2kQ/r_minus. V = 0 gives (x-5a)^2+y^2 = (4a)^2. V(5a,0,0) = kQ/(4a); crossing V = 0 gives v = sqrt(kQq/(2ma)). Absolute distances are used for the entire x-axis.
- **NUM-31:** at supplied point P, V = rho (3R^2-|P|^2)/(6 epsilon_0) - rho r_c^3/(3 epsilon_0 |P-c|). In the cavity, E = rho c/(3 epsilon_0). The removed charge is proportional to r_c^3, not r_c or r_c^2.
- **ARCH-ADV-MC-05:** in the overlap, E = rho[(r-c1)-(r-c2)]/(3 epsilon_0) = rho(c2-c1)/(3 epsilon_0). It has constant nonzero magnitude/direction; potential differences are -E dot displacement. Distinct radii imply unequal total charge magnitudes.
- **MC-36:** mu = kQq/m. For a,e, pericentre r = a(1-e), speed = sqrt(mu(1+e)/(a(1-e))), and T = 2pi sqrt(a^3/mu). Solve eccentric anomaly u-e sin(u)=nt algebraically; evaluate x=a(cos(u)-e), y=a sqrt(1-e^2) sin(u), and rotate into the authored plane. This analytic trajectory is compared to DOP853 outputs. L = m sqrt(mu a(1-e^2)) times the orbital normal; speed and angular speed vary for e=0.5.

Finite-difference gradient and rigid-coordinate covariance checks supplement these references. They do not prove every singularity or boundary case safe. Crossing estimates use saved r,v and a bracketed interpolation, with a separate finer integration/sample check; they are not exact symbolic event times.
