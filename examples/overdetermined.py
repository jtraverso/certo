"""Two equations defining the same quantity, and their compatibility condition.

A first moment fixes `A m = P6 t^4` and a second fixes `A^2 m = P11 t^6`: two
equations for one `A`. Whether they are compatible, and why, is a question
people answer by hand -- and it is a RESULTANT. Eliminating the shared
quantity IS the compatibility condition.

    $ certo eliminate examples/overdetermined.py
    SATISFIABLE  [sat]
      eliminated A. A common root exists only where this vanishes:
      m*P6^2*t^8 - m^2*P11*t^6

which factors as `m t^6 (P6^2 t^2 - m P11)`, so away from `m = 0` and `t = 0`
the condition is `P6^2 / P11 = m / t^2`. That is the identity the doubling
argument produces, recovered rather than assumed.

WHAT TRAVELS is the Bezout identity, not the number: `Res = A*f + B*g`, so
checking it is expanding two products and subtracting. No solver, and `A` is
gone from all three.

EXACTLY TWO EQUATIONS, because that is what a resultant is. Three definitions
of the same quantity is an ideal membership question, and `certo ideal` is the
command for it -- iterating resultants pairwise introduces extraneous factors
that nothing here could certify away.
"""
import z3

from certo import EliminateSpec


def spec():
    A, m, P6, P11, t = z3.Reals("A m P6 P11 t")
    return EliminateSpec(
        variables=["A", "m", "P6", "P11", "t"],
        equations=[A * m - P6 * t**4, A * A * m - P11 * t**6],
        eliminate="A",
        title="two moments defining the same A: when do they agree?")
