"""Exponents derived from the relations, instead of assigned by hand.

`OrderSpec` asks for the exponent of every symbol. On a real term that is six
numbers somebody worked out mentally from `|E| <= Lmass`, `C >= n`,
`d' >= C(n,2)` -- and if one is wrong the answer comes back clean and false,
which is exactly the shape of an error nothing downstream catches.

    $ certo order examples/order_relations.py
    REFUTED  [sat]
      REFUTED: you claimed it decays, and it is Theta(1) -- the leading
      exponent in n is 0

Same verdict as writing `{Lmass: 2, C: 1, dp: 2}` by hand, and nobody had to
be right about three numbers to get it. Every relation is LINEAR in the
exponents -- `E ~ n**2` is `exp(E) = 2`, `Lmass ~ E * tC` is
`exp(Lmass) = exp(E) + exp(tC)` -- so the system is a linear program, solved
exactly.

IT REFUSES RATHER THAN GUESSES. `order`'s core is exact Laurent arithmetic and
needs a NUMBER per symbol; an interval is not one. `too_weak()` leaves `Lmass`
bounded only from below, and the refusal names the symbol and the interval
that is left, because "Lmass in [1, +inf)" says which bound is missing and
"cannot infer" does not.

WHAT IT DOES NOT ESTABLISH. That the relations are true -- they are the spec's
claim, the way a group is for `reduce`. And the exponent is not the constant.
"""
import z3

from certo import OrderSpec

RELATIONS = ["E ~ n**2", "tC ~ 1", "Lmass ~ E * tC", "C ~ n", "dp ~ C**2"]


def spec():
    Lmass, C, dp = z3.Reals("Lmass C dp")
    return OrderSpec(
        expression=5 * Lmass * C * C / (dp * dp),
        orders={},                       # nothing assigned by hand
        relations=RELATIONS,
        expect="decays",
        title="the exponents come from the relations")


def too_weak():
    """One-sided on a numerator: refused, with the gap named."""
    Lmass, C = z3.Reals("Lmass C")
    return OrderSpec(
        expression=Lmass * C, orders={},
        relations=["C ~ n", "Lmass >= C"],
        title="the relations do not pin every exponent")
