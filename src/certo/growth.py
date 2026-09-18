"""Magnitude classes on a totally ordered ladder, and the arithmetic on them.

A parameter `delta` goes to zero; write `u = 1/delta`, so everything is a
magnitude in `u` as `u -> infinity`. A class is a pair `(tier, e)`:

    tier 0   ~ u**e              polynomial, `e` any rational
    tier 1   ~ exp(u)**e         beats every polynomial when e > 0
    tier 2   ~ tower(u)**e       beats every exponential when e > 0

`e` carries the sign, so `(0, -1)` is `delta` itself and `(2, -2)` is
`1/tower(u)**2` -- something that vanishes faster than any power of delta.

WHY A LADDER AND NOT A FUNCTION. The question these answer is never "what is
k" but "does this loop close": a user had `k` growing like a Szemeredi tower
in `1/delta` and a constraint `delta <= rho` with `rho <= K/(3k**2)`, and
wanted to know that no positive delta survives. That needs the ORDER of the
composite and nothing finer. Substituting a particular function -- they used
`k >= 1/delta`, because it was what a solver could see -- proves a strictly
weaker statement, and the gap between it and the tower is the part the
argument was carrying by hand.

COMPARISON IS THE WHOLE POINT and it is exact:

    (t, e) vs (t, f)    ->  compare e and f
    (t, e) vs (s, f), t > s  ->  the higher tier decides, by the sign of e

That second line is what makes a tower beat a polynomial without either being
evaluated anywhere.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t

POLY, EXP, TOWER = 0, 1, 2
TIER_NAMES = {POLY: "poly", EXP: "exp", TOWER: "tower"}
NAMED_TIERS = {v: k for k, v in TIER_NAMES.items()}


class NotComparable(ValueError):
    """Raised with what was wrong: a bare failure helps nobody."""


class Class:
    """A magnitude class `(tier, e)`, with exact rational `e`."""

    __slots__ = ("tier", "e")

    def __init__(self, tier, e):
        self.tier = int(tier)
        self.e = Fraction(e)
        if self.tier not in TIER_NAMES:
            raise NotComparable(_t("growth.bad_tier", tier=tier,
                                   known=", ".join(sorted(NAMED_TIERS))))
        # A tier above polynomial with a zero exponent is just a constant, and
        # keeping it at its old tier would let it beat a polynomial it does
        # not beat.
        if self.tier > POLY and self.e == 0:
            self.tier = POLY

    def __repr__(self):
        if self.tier == POLY:
            return "u^{}".format(self.e)
        return "{}(u)^{}".format(TIER_NAMES[self.tier], self.e)

    def __eq__(self, other):
        return (self.tier, self.e) == (other.tier, other.e)

    def __hash__(self):
        return hash((self.tier, self.e))

    def to_dict(self):
        return {"tier": TIER_NAMES[self.tier], "exponent": str(self.e)}

    @staticmethod
    def from_dict(d):
        return Class(NAMED_TIERS[d["tier"]], Fraction(d["exponent"]))


CONST = Class(POLY, 0)


def compare(a: Class, b: Class) -> int:
    """-1, 0 or +1: how `a` stands against `b` as `u -> infinity`."""
    if a.tier == b.tier:
        return (a.e > b.e) - (a.e < b.e)
    hi, sign = (a, 1) if a.tier > b.tier else (b, -1)
    # The higher tier decides, and its SIGN says in which direction: a tower
    # that grows dominates, a tower that decays is dominated.
    return sign * (1 if hi.e > 0 else -1)


def times(a: Class, b: Class) -> Class:
    """The class of a product."""
    if a.tier == b.tier:
        return Class(a.tier, a.e + b.e)
    return a if a.tier > b.tier else b


def power(a: Class, k) -> Class:
    """The class of `a**k`, for rational `k`."""
    return Class(a.tier, a.e * Fraction(k))


def invert(a: Class) -> Class:
    return Class(a.tier, -a.e)


def apply(fn: str, arg: Class, degree=1) -> Class:
    """The class of `fn(x)` where `x` has class `arg`.

    Refuses rather than guesses. `exp` of something that VANISHES tends to
    one, which is a constant and not an exponential -- getting that wrong is
    how a cycle would be declared empty when it is not.
    """
    if fn == "poly":
        return power(arg, degree)
    if fn in ("exp", "tower"):
        if arg.e == 0:
            return CONST                     # exp(const) is a constant
        if arg.e < 0:
            # exp(x) -> 1 as x -> 0. The magnitude is constant, and claiming a
            # tier here would invent growth out of a vanishing argument.
            return CONST
        step = 1 if fn == "exp" else 2
        tier = min(TOWER, arg.tier + step)
        return Class(tier, 1)
    raise NotComparable(_t("growth.bad_function", fn=fn,
                           known="poly, exp, tower"))
