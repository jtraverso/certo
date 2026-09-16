"""core over several goals: the hypothesis-by-goal table.

Running `core` once per goal already tells you which hypotheses that goal
needs. What the table adds is the COMPARISON, and that is what decides how
small a downstream interface can be.

Here the same three range conditions face three different goals:

  identity    a polynomial identity -- true for every real, needs nothing
  positivity  a lower bound -- needs the range
  ordering    d <= r -- needs exactly the hypothesis that says so

A hypothesis irrelevant to the identity but necessary for positivity is
invisible when the goals are checked one at a time.

    certo core examples/core_matrix.py
"""
import z3

from certo import MultiSpec


def spec():
    r, d = z3.Reals("r d")

    s = MultiSpec(title="range conditions against three goals")
    s.assume("r_ge_3", r >= 3)
    s.assume("d_ge_1", d >= 1)
    s.assume("d_le_r", d <= r)

    # Holds for every real: no hypothesis is needed.
    s.claim("identity", (d - 1) * (d - 2) + r * (r + 1) - d * (d + 1)
            - 4 * (r - d) == (r - 1) * (r - 2))
    # Needs the range to keep the product non-negative.
    s.claim("positivity", (r - 1) * (r - 2) >= 0)
    # Needs exactly the hypothesis that states it.
    s.claim("ordering", r - d >= 0)
    return s
