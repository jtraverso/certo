"""The first moment, in exact rationals, and the existence it buys.

The probabilistic method in one line: if the EXPECTED number of bad events is
below one, some outcome has none of them, so an object avoiding all of them
exists. The whole argument is a sum of rationals and a comparison, and it is
usually done on the back of an envelope -- which is why it is usually done in
floating point, and why `0.9999999` and `1.0000001` have both been written
down as "less than one".

Two ways to supply the arithmetic, because two shapes turn up.

BY EVENT. A list of bad events with their probabilities. The expected count is
their sum, by linearity of expectation -- which needs NO independence, and
that is the whole reason the method is usable. certo checks each probability
is a probability, sums them exactly, and compares.

BY TAIL. A distribution given as `P(X >= 1), P(X >= 2), ...`. The masses are
the successive differences, and

    E[X] = sum of the tails

for a non-negative integer variable. Checked: the tails are non-increasing,
each is a probability, and every difference is non-negative -- a tail sequence
that goes back up is not a distribution, and the mass it implies is negative.

WHAT THE CONCLUSION NEEDS, and what it is refused without. "`E[X] < 1` implies
some outcome has `X = 0`" is true because `X` COUNTS something: non-negative
and integer-valued. If `X` could be `1/2` everywhere its mean would be below
one with no outcome at zero. So the existence conclusion is drawn only when
the spec says the quantity is a count, and a threshold other than one gets the
bound without the conclusion -- `E[X] <= c` is a fact about a mean and nothing
more.

Nothing here is a search. The probabilities come from wherever they come
from; what this checks is that they are probabilities, that the sum is the
sum, and that the comparison holds.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotAMoment(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def _rational(x, where) -> Fraction:
    try:
        return Fraction(x)
    except (TypeError, ValueError, ZeroDivisionError):
        raise NotAMoment(_t("moment.not_rational", where=where, got=repr(x)))


def masses_from_tails(tails) -> list:
    """`P(X = k)` from `P(X >= k)`. The successive differences.

    With `T_0 = 1` implicit: `p_0 = 1 - T_1`, `p_k = T_k - T_{k+1}`, and the
    last tail closing the sequence. A tail that goes back up gives a negative
    mass, which is not a distribution, so the differences ARE the check.
    """
    seq = [Fraction(1)] + [_rational(x, "tail") for x in tails]
    return [seq[i] - seq[i + 1] for i in range(len(seq) - 1)] + [seq[-1]]


def certify(spec) -> dict:
    """Sum exactly, compare exactly, and say what the comparison buys."""
    if (spec.events is None) == (spec.tails is None):
        raise NotAMoment(_t("moment.one_shape"))
    if spec.relation not in ("<", "<="):
        raise NotAMoment(_t("moment.relation", rel=spec.relation))

    bad, masses, terms = [], None, []
    if spec.events is not None:
        for name, p in spec.events:
            value = _rational(p, str(name))
            terms.append((str(name), value))
            if value < 0 or value > 1:
                bad.append(str(name))
        total = sum((v for _n, v in terms), Fraction(0))
    else:
        tails = [_rational(x, "tail") for x in spec.tails]
        masses = masses_from_tails(tails)
        for i, m in enumerate(masses):
            if m < 0:
                bad.append("P(X={})".format(i))
        for i, tl in enumerate(tails):
            if tl < 0 or tl > 1:
                bad.append("P(X>={})".format(i + 1))
            terms.append(("P(X>={})".format(i + 1), tl))
        # E[X] = sum of the tails, for a non-negative integer variable.
        total = sum(tails, Fraction(0))

    threshold = _rational(spec.threshold, "threshold")
    holds = total < threshold if spec.relation == "<" else total <= threshold

    # The existence conclusion needs the quantity to be a COUNT -- non-negative
    # and integer-valued -- and the threshold to be one. Anything else is a
    # bound on a mean, which is a smaller and still useful statement.
    concludes = bool(spec.counts and threshold == 1 and spec.relation == "<"
                     and holds and not bad)

    return {
        "terms": [[n, str(v)] for n, v in terms],
        "expectation": total,
        "threshold": threshold,
        "relation": spec.relation,
        "masses": [str(m) for m in masses] if masses is not None else None,
        "from_tails": spec.tails is not None,
        "counts": bool(spec.counts),
        "out_of_range": sorted(set(bad)),
        "holds": bool(holds),
        "concludes": concludes,
        "ok": bool(holds and not bad),
    }
