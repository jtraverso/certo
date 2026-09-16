"""farkas --nonlinear: the nlinarith certificate.

`nlinarith` is `linarith` plus a preprocessing step: multiply pairs of
hypotheses, add some squares, treat each monomial as a fresh variable. That is
a degree-2 Positivstellensatz, and it is a heuristic rather than a decision
procedure -- which products to add is a guess.

Here: a^2 + b^2 >= 2ab, which is (a - b)^2 >= 0 and therefore falls out of the
squares the preprocessing adds.

    certo farkas examples/farkas_nonlinear.py --nonlinear

If it finds nothing, that does not mean the statement is false -- it means the
heuristic missed. `certo prove` uses Z3's nlsat, which is complete.
"""
import z3

from certo import Spec


def spec():
    a, b = z3.Reals("a b")
    s = Spec(title="a^2 + b^2 >= 2ab")
    s.claim(a * a + b * b >= 2 * a * b)
    return s
