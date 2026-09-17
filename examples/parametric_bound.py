"""A bound for every `p`, not for the ones somebody had time to run.

This is the shape of a real research instance, and the reason the command
exists. Somebody had a symmetrised linear program whose data depend on a
parameter `p`, solved it exactly for `p = 5..12` with a hand-written rational
simplex, read a pattern off the answers, and wrote "and similarly for larger
p". That sentence is where the work actually is.

What their answers looked like:

    p = 6            optimum 9            one dual vertex
    p = 7, 8, 9      11, 13, 16           a different one, the same for all three
    p = 10, 11, 12   58/3, 68/3, 79/3     a third one, again constant

Piecewise-constant duals with thresholds. So on `p >= 10` there is ONE `y`,
and weak duality says `opt(p) <= b(p).y` for every `p` at once -- provided
`A(p)^T y >= c(p)` holds on the whole ray, which is a finite set of polynomial
inequalities in `p`.

The model below is a small stand-in with that structure: a cap whose size
grows quadratically in `p`, one that grows linearly, and one that does not
grow at all. It runs in a millisecond and reads in one sitting.

    $ certo parametric examples/parametric_bound.py
    PROVED  [unsat]
      for all p >= 10, the optimum is at most 1/6*p^2 + 1/6*p - 2/3
      and that is every value with p >= 10 -- not a sample of them

And it is not a loose bound. Solving the LP outright at several values:

    p = 10   bound 53/3    optimum 53/3
    p = 11   bound 64/3    optimum 64/3
    p = 15   bound 118/3   optimum 118/3
    p = 30   bound 463/3   optimum 463/3

One dual, read off ONE solved instance at `p = 10`, gives the exact optimum
for every `p` above it.

THE DIVISION OF LABOUR is the point. `certo` does not search for `y` here --
`certo opt` on a single instance hands you one, and any other solver would do.
What this checks is that the `y` you already have works for the whole family,
and that check is arithmetic: substitute `p = 10 + u`, expand, and read the
signs off the coefficients. All non-negative means the polynomial is
non-negative on the ray, because `u` and its powers are.

That test is SUFFICIENT AND NOT NECESSARY, and the command says so rather than
implying otherwise: `p^2 - 3p + 3` is positive everywhere and fails it. A
failure means "not established by this route", never "false", and no
certificate is emitted for one.

What the certificate does NOT say, and `verify` repeats every time: it bounds
the LP relaxation, it says nothing below the floor, and it says nothing about
an integer optimum.
"""
from fractions import Fraction

from certo import ParametricSpec
from certo.polynomials import Poly

RING = ("p",)
P = Poly.var(RING, "p")


def K(c):
    return Poly.const(RING, c)


def spec():
    # Three triangle-ish classes. `big` has a quadratic capacity, the way an
    # edge count on a growing vertex set does; `mid` grows linearly; `small`
    # does not grow at all.
    big = P * (P - K(1)) * K(Fraction(1, 2))       # p(p-1)/2
    mid = P - K(5)                                  # p - 5
    small = K(3)

    return ParametricSpec(
        parameters={"p": 10},
        sense="max",
        objective={"x_big": K(1), "x_mid": K(1), "x_small": K(1)},
        constraints=[
            ("cap_big", {"x_big": K(3), "x_mid": K(1)}, "<=", big),
            ("cap_mid", {"x_mid": K(2), "x_small": K(1)}, "<=", mid),
            ("cap_small", {"x_small": K(2)}, "<=", small),
        ],
        # Read off a single solved instance. Checking it is this command's job;
        # finding it was `opt`'s.
        dual={"cap_big": Fraction(1, 3),
              "cap_mid": Fraction(1, 3),
              "cap_small": Fraction(1, 3)},
        title="a bound for every p >= 10, from one dual",
    )
