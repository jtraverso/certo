"""The expected number of bad events is below one, so a good object exists.

The probabilistic method in one line, and the line is a sum of rationals.
Colour the edges of K_n at random; if the EXPECTED number of monochromatic
K_k is below one, some colouring has none, so a Ramsey lower bound follows.
The whole argument is arithmetic, which is why it is usually done on the back
of an envelope -- and why it is usually done in floating point.

`0.9999999` and `1.0000001` have both been written down as "less than one".

    $ certo moment examples/first_moment.py
    PROVED  [unsat]
      E[X] = 15/32 < 1, so SOME OUTCOME HAS NONE of them: an object avoiding
      every one of these 15 events exists
      exists: True
      expectation: 15/32
      certificate: first_moment (no solver needed)

LINEARITY IS WHY THIS WORKS AT ALL, and it is worth saying out loud: the
expected count is the sum of the probabilities WITHOUT any independence
between the events. The fifteen monochromatic-K4 events on six vertices
overlap constantly -- two copies of K4 in K6 share four of their six edges --
and it does not matter. certo checks each value is a probability, adds them
exactly, and compares.

WHAT THE CONCLUSION NEEDS. "`E[X] < 1` implies some outcome has `X = 0`" is
true because `X` COUNTS something -- non-negative and integer-valued. A
quantity that could be one half everywhere has a mean below one with no
outcome at zero. So `counts=True` is what buys the existence statement, and
without it what comes back is a bound on a mean and says nothing exists.
`bound_only()` below is that, on purpose.

THE OTHER SHAPE is a distribution given by its tails, `P(X >= 1)`,
`P(X >= 2)`, ... The masses are the successive differences and `E[X]` is the
sum of the tails. What gets checked there is that the differences are
non-negative -- a tail sequence that goes back up is not a distribution, and
the mass it implies is negative. `by_tails()` below, and `not_a_distribution()`
is the one that is caught.

    $ certo verify out/first_moment.json
    VALID  first_moment certificate (by re-adding exact rationals and
                                     comparing, no solver)
      [ok] every value is a probability  (15 values; out of range: -)
      [ok] the expectation is the sum of the terms, re-added  (15/32)
      [ok] the comparison holds, in exact rationals  (15/32 < 1)
      [ok] the existence conclusion is drawn exactly when it is earned
           (a count, a mean strictly below one: some outcome has none)
      WARNING: the probabilities are the spec's claim [...]

That last warning is the real boundary. certo checks the values are
probabilities, that the sum is the sum, and that the comparison holds. It does
not check that they describe the experiment you meant -- and that is where the
mistakes in this method actually live.
"""
from fractions import Fraction
from math import comb

from certo import MomentSpec

#: Two colours, K4 monochromatic: 2 / 2^6 of the colourings of its six edges.
N, K = 6, 4


def spec():
    """A Ramsey lower bound from one expectation: R(4,4) > 6.

    C(6,4) = 15 copies of K4, each monochromatic with probability
    `2^(1 - C(4,2))` = 2^-5. The expected count is 15/32, below one, so some
    2-colouring of K6 has no monochromatic K4.

    IT IS A WEAK BOUND AND THAT IS THE HONEST HEADLINE. R(4,4) is 18, so this
    gets 6 out of 18 -- the plain union bound stops paying at n = 7, where the
    expectation is 35/32 and already above one. The method is cheap, the
    certificate is a sum of rationals, and what it buys is a floor rather than
    the answer. Anything sharper needs deletion, the local lemma, or a
    construction, and none of those is this command.
    """
    copies = comb(N, K)
    each = Fraction(2, 2 ** comb(K, 2))
    return MomentSpec(
        events=[("mono_K4_copy_{}".format(i), each) for i in range(copies)],
        counts=True,
        title="an expected count of monochromatic K4 on six vertices",
    )


def by_tails():
    """The same arithmetic from a distribution given by `P(X >= k)`."""
    return MomentSpec(
        tails=[Fraction(1, 2), Fraction(1, 8), Fraction(1, 64)],
        counts=True,
        title="a distribution by its tails, and its mean",
    )


def bound_only():
    """Not declared a count, so nothing is claimed to exist."""
    return MomentSpec(
        events=[("half", Fraction(1, 2)), ("quarter", Fraction(1, 4))],
        counts=False,
        title="a bound on a mean, and only that",
    )


def not_a_distribution():
    """Tails that go back up. The mass between them is negative."""
    return MomentSpec(
        tails=[Fraction(1, 4), Fraction(1, 2)],
        counts=True,
        title="a tail sequence that is not one",
    )
