"""bisect: the sharp constant in (a+b)^2 <= c*(a^2+b^2).

The exact answer is c = 2, with equality at a = b. Bisection brackets it from
both sides and the certificate carries:
  - good side: the unsat core of the negation, i.e. the proof
  - bad side:  the concrete counterexample (a, b) that breaks it

This is the "improve a constant" pattern: the result is not a bare number, it
is a number with both halves of its justification.

    certo bisect examples/bisect_constant.py --trace
"""
import z3

from certo import BisectSpec, Spec


def build(c):
    a, b = z3.Reals("a b")
    s = Spec(title="(a+b)^2 <= {}*(a^2+b^2)".format(c))
    s.claim((a + b) * (a + b) <= z3.RealVal(c) * (a * a + b * b))
    return s


def spec():
    return BisectSpec(build=build, lo=0.0, hi=10.0, direction="min_true",
                      tol=1e-6, title="sharp constant")
