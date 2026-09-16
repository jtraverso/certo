"""ideal: a polynomial system with no solution, and the algebra that proves it.

The system says a point is on the unit circle, on the line x = y, and has
x + y = 3. The first two force x = y = +-1/sqrt(2), so x + y is at most
sqrt(2) < 3. There is no common root -- not over the reals, and not over the
complex numbers either.

The certificate is cofactors h_i with

    1 = h_1 g_1 + h_2 g_2 + h_3 g_3

Finding them is a Groebner basis computation. Checking them is expanding the
product and comparing coefficients, in exact rationals: no solver, no algebra
system, nothing to take on trust.

    certo ideal examples/ideal_inconsistent.py --cert out/ideal.json
    certo verify out/ideal.json
"""
import z3

from certo import IdealSpec


def spec():
    x, y = z3.Reals("x y")
    return IdealSpec(
        title="x^2+y^2=1, x=y, x+y=3",
        variables=["x", "y"],
        equations=[x * x + y * y - 1, x - y, x + y - 3],
        claim=None,                     # None: is the system inconsistent?
    )
