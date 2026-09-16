"""prove / core: a non-linear inequality over the reals.

The `noise` hypothesis is deliberately irrelevant: it is there to show that
`core` drops it on its own. That is what "simplify a proof" means here.

    certo prove examples/amgm.py
    certo core  examples/amgm.py
"""
import z3

from certo import Spec


def spec():
    a, b, c, t = z3.Reals("a b c t")
    s = Spec(title="AM-GM in three variables")
    s.assume("a_pos", a > 0)
    s.assume("b_pos", b > 0)
    s.assume("c_pos", c > 0)
    s.assume("noise", t == 42)  # irrelevant on purpose
    s.claim((a + b) * (b + c) * (a + c) >= 8 * a * b * c)
    return s
