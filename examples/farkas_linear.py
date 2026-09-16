"""farkas: the linarith certificate, in exact rationals.

`linarith` does not decide anything clever: it looks for a NON-NEGATIVE
combination of the hypotheses plus the negated goal that sums to a
contradiction. Those multipliers are the whole proof, and finding them is a
linear program.

Here: from x >= 1 and y >= 1, conclude x + y >= 2. The certificate is
(1, 1, 1) -- add the three rows and everything cancels to 0 < 0.

    certo farkas examples/farkas_linear.py
"""
import z3

from certo import Spec


def spec():
    x, y, z = z3.Reals("x y z")
    s = Spec(title="x + y >= 2 from x >= 1 and y >= 1")
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise", z <= 100)      # irrelevant: its multiplier comes out 0
    s.claim(x + y >= 2)
    return s
