"""order: does this term decay in n, or is it Theta(1)?

The term is one a user actually had. They substituted magnitudes by hand --
`d` about n^2, `C` about n, `|W|` about n^2 -- and asked whether it decays.
It does not: it is Theta(1).

That bug was invisible to BOTH Lean and `certo prove`, for the same reason.
It is not an infeasibility. It is a feasibility that does not improve with n,
so a solver asked "is this satisfiable" says yes forever, correctly, while
the bound it sits in never gets better.

    certo order examples/order_decay.py --cert out/order.json
    certo order examples/order_decay.py --expect decays    # REFUTED
"""
import z3

from certo import OrderSpec

k, W, C, u, d, p = z3.Reals("k W C u d p")


def spec():
    return OrderSpec(
        title="5|k| W C^2 / (u^3 d^2 p^10)",
        expression=5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10),
        orders={"k": 0, "W": 2, "C": 1, "u": 0, "d": 2, "p": 0},
        var="n",
    )
