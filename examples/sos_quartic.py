"""sos: a quartic certified non-negative, exactly.

x^4 + y^4 - x^2 y^2 is non-negative everywhere, and the reason is a sum of
squares. The search runs in floating point; the certificate is rational and is
checked by squaring the forms and adding them up.

Try the Motzkin polynomial to see the honest failure:

    x**4 * y**2 + x**2 * y**4 - 3 * x**2 * y**2 + 1

It is non-negative everywhere and provably NOT a sum of squares, so `sos`
comes back `unknown_solver` -- which means "this search found nothing", never
"the polynomial goes negative".

    certo sos examples/sos_quartic.py --cert out/sos.json
    certo verify out/sos.json
"""
import z3

from certo import SOSSpec


def spec():
    x, y = z3.Reals("x y")
    return SOSSpec(
        title="x^4 + y^4 - x^2 y^2 >= 0",
        variables=["x", "y"],
        poly=x * x * x * x + y * y * y * y - x * x * y * y,
    )
