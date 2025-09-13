from mpmath import mp, mpf, sqrt, findroot, nstr, e

# Set desired precision (increase mp.dps to print more correct digits)
mp.dps = 120

# Given numerical data
t0_for_a = mpf('1.39492')
a = -2/(mpf('3') * t0_for_a) + mpf('1e-4')
b = mpf(-7) / mpf(13)

# Fixed points
Qx = mp.sqrt(5)
Qy = mp.mpf('1') + mp.e**(mp.mpf('1')/mp.mpf('3'))
Rx = mp.mpf('1')/mp.mpf('2')
Ry = -mp.mpf('1')/mp.mpf('3')
Sx = mp.e
Sy = mp.mpf('0.2')

# Auxiliary circle radius
s = sqrt((Rx - Sx)**2 + (Ry - Sy)**2)

# Linear relation coefficients
dxQ = Qx - Rx
dyQ = Qy - Ry

# K constant as in derivation
K = Rx**2 + Ry**2 - Qx**2 - Qy**2 - s**2

# Solve for x_C algebraically
den = dxQ + a * dyQ
if abs(den) < mp.mpf('1e-60'):
    raise RuntimeError("Denominator too small; check parameters or increase precision.")
xC = ( -K/2 - b * dyQ ) / den
yC = a * xC + b

# Tangency scalar function F(t)
def F_scalar(t):
    t = mp.mpf(t)
    if abs(t) == 0:
        # avoid division by zero
        return mp.mpf('1e30')
    yP = mp.mpf('3')/mp.mpf('4') * t**2
    return yC - yP + (mp.mpf('2')/(mp.mpf('3')*t)) * (xC - t)

# Use several initial guesses; prefer near 1.39492
initial_guesses = [mp.mpf('1.39492'), mp.mpf('1.3'), mp.mpf('1.5'), mp.mpf('0.8'), mp.mpf('2.0'), mp.mpf('-1.0')]

t_sol = None
best = None
for guess in initial_guesses:
    try:
        root = findroot(F_scalar, guess, tol=mp.mpf('1e-80'), maxsteps=300)
        # Accept only nearly real roots
        if abs(mp.im(root)) < mp.mpf('1e-40'):
            root = mp.re(root)
            res = abs(F_scalar(root))
            if res < mp.mpf('1e-30'):
                t_sol = mp.mpf(root)
                break
            if best is None or res < best[1]:
                best = (mp.mpf(root), res)
    except Exception:
        continue

if t_sol is None:
    if best is not None:
        t_sol = best[0]
    else:
        raise RuntimeError("Failed to find a root for t. Try increasing precision or changing initial guesses.")

# Compute plaque radius r
r_sol = sqrt((xC - Qx)**2 + (yC - Qy)**2)

# Compute residuals to verify constraints
yP = mp.mpf('3')/mp.mpf('4') * t_sol**2
eq_tangency = yC - yP + (mp.mpf('2')/(mp.mpf('3')*t_sol)) * (xC - t_sol)
eq_through_Q = (xC - Qx)**2 + (yC - Qy)**2 - r_sol**2
eq_orthogonality = (xC - Rx)**2 + (yC - Ry)**2 - (r_sol**2 + s**2)
max_res = max(abs(eq_tangency), abs(eq_through_Q), abs(eq_orthogonality))

# Print results
print("mp.dps =", mp.dps)
print()
print("Given constants:")
print(" a =", nstr(a, 30))
print(" b =", nstr(b, 30))
print()
print("Computed plaque center C:")
print(" x_C =", nstr(xC, 50))
print(" y_C =", nstr(yC, 50))
print()
print("Solved tangency abscissa t:")
print(" t   =", nstr(t_sol, 50))
print()
print("Plaque radius r (high precision):")
print(" r   =", nstr(r_sol, 60))
print()
print("Residuals (should be ≪ 1):")
print(" tangency eq =", nstr(eq_tangency, 30))
print(" through Q eq =", nstr(eq_through_Q, 30))
print(" orthogonality eq =", nstr(eq_orthogonality, 30))
print(" max residual =", nstr(max_res, 30))
print()
print("Auxiliary data:")
print(" Q =", (nstr(Qx, 30), nstr(Qy, 40)))
print(" R =", (nstr(Rx, 20), nstr(Ry, 20)))
print(" S =", (nstr(Sx, 30), nstr(Sy, 10)))
print(" s =", nstr(s, 40))
