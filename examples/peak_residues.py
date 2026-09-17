"""The best whole number, for every n at once -- and why there are three of them.

A value function on a family peaks somewhere, and if the thing being chosen is
a count -- a clique size, a block count, a number of parts -- the answer has to
be a whole number. On the reals that is one line. Over the integers a write-up
reaches it like this:

    complete the square, observe the objective is an integer at integer
    argument, conclude the maximum is the FLOOR of the continuous peak, and
    attain it at the integer nearest the real vertex

and every step of that is right. None of them is a finite object a reader can
check, because the floor of a parametric expression is not a polynomial: there
is nothing to expand and nothing to read signs off.

The family here is

    F(n, x) = x (2n + 1 - 3x) / 2

whose real vertex sits at `x = (2n+1)/6`. Which integer is nearest depends on
`n` modulo 3, so the family SPLITS -- and the split is the answer, not an
inconvenience on the way to it.

    $ certo peak examples/peak_residues.py
    PROVED  [unsat]
      for all m >= 0, no integer beats m, where the value is 3/2*m^2 + 1/2*m
      certificate: integer_peak (no solver needed)
      and that is every integer choice with m >= 0 -- not a sample of them

That is the class `n = 3m`, where `3/2*m^2 + 1/2*m` is `m(3m+1)/2`. The other
two are `residue_one()` and `residue_two()` below, giving `3m(m+1)/2` and
`(m+1)(3m+2)/2`. Between them they cover every `n`, and together they are the
closed form a source states by residue class -- without a floor appearing
anywhere.

THE CRITERION, and why it is polynomial. Move the origin to the claimed
maximiser `x*`. For any integer step `t`,

    F(x* + t) - F(x*)  =  A t^2 + F'(x*) t

with `A` the leading coefficient. When `A < 0` that is `<= 0` for every
non-zero integer `t` exactly when

    A  <=  F'(x*)  <=  -A.

Two polynomial inequalities in the parameters. Here `A = -3/2`, so the test is
`|F'(x*)| <= 3/2`, and `F'(x*) = 3((2n+1)/6 - x*)` -- so the test says exactly
"`x*` is within half a step of the real vertex", written so that it expands.

    class      x*      F'(x*)     slack
    n = 3m     m        1/2       comfortable
    n = 3m+1   m        3/2       EXACTLY at the boundary
    n = 3m+2   m+1     -1/2       comfortable

The middle row is worth a second look. `3/2` meets the criterion with nothing
to spare, and that is not a near miss -- it is the TIE. When `n = 3m+1` the
vertex falls halfway between `m` and `m+1`, both attain the maximum, and the
criterion is tight at both. A certificate that had slack there would be
describing a different problem.

WHY THE CLAIM IS TIGHT, not just valid. `x*` is an integer, so `F(n, x*)` is
attained. The certificate therefore says two things at once: no integer does
better, and this integer does that well. That is why `certo` refuses a
maximiser with non-integer coefficients rather than accepting "it is an integer
really" -- an argument about a point that does not exist proves nothing.

WHAT IT DOES NOT DO. It does not search for `x*`. Round the real vertex and
hand it over; checking one is arithmetic, and that split is the same one
`parametric` makes with its dual and `farkas` makes with its multipliers.
"""
from fractions import Fraction

from certo import PeakSpec
from certo.polynomials import Poly


def _family(offset, argmax_shift):
    """`n = 3m + offset`, with the maximiser `m + argmax_shift`.

    One function because the program is one program: only the residue and the
    integer nearest the vertex change between the classes.
    """
    ring = ("m", "x")
    m, x = Poly.var(ring, "m"), Poly.var(ring, "x")

    def K(c):
        return Poly.const(ring, c)

    # n = 3m + offset, so 2n + 1 = 6m + 2*offset + 1
    two_n_plus_one = m * K(6) + K(2 * offset + 1)
    objective = x * (two_n_plus_one - x * K(3)) * K(Fraction(1, 2))

    return PeakSpec(
        parameters={"m": 0},
        variable="x",
        objective=objective,
        argmax=Poly.var(("m",), "m") + Poly.const(("m",), argmax_shift),
        title="n = 3m + {}: the best integer count".format(offset),
    )


def spec():
    """`n = 3m`: the vertex sits at `m + 1/6`, so the nearest integer is `m`."""
    return _family(0, 0)


def residue_one():
    """`n = 3m + 1`: the vertex is at `m + 1/2` and BOTH neighbours attain it.

    `m + 1` works as well and certifies the same value; the criterion is tight
    at both, which is what a tie looks like from here.
    """
    return _family(1, 0)


def residue_two():
    """`n = 3m + 2`: the vertex is at `m + 5/6`, so the nearest integer is `m + 1`."""
    return _family(2, 1)
