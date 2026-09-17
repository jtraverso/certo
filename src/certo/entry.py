"""Where a sequence first crosses a threshold, and how far past it lands.

A proof walks along a finite path -- successive edits, successive copies,
successive rounds -- watching a quantity, and stops at the first index where
it crosses a line. Everything after that is about the crossing point, so the
crossing point had better be the one claimed. Two things are being asserted
and they are easy to conflate:

    it crosses HERE          a_k is on the far side
    it had not crossed yet   a_j is on the near side for EVERY j < k

The second is the one that carries the weight and the one that goes wrong: an
off-by-one, or a `<=` where the argument needed `<`, and the "first" index is
not first. Both are finite checks over stored numbers, in exact rationals.

THE CERTIFICATE ONLY NEEDS THE PREFIX. Nothing past the crossing is part of
either claim, so `a_0 .. a_k` is the whole evidence and the tail of the
sequence -- which is usually where the length is -- never has to travel.

THE WINDOW is the other half, and it is the reason this is worth a command
rather than a loop. With a bound `delta` on the step size,

    a_{k-1} < threshold  and  a_k <= a_{k-1} + delta

so the crossing lands strictly inside `[threshold, threshold + delta)`: the
quantity does not merely cross, it crosses BY AT MOST delta. That is what a
first-entry argument is usually for, and only the LAST step is used for it --
though `delta` is checked against every step of the prefix, because a bound
that fails earlier is a bound somebody got wrong.

Nothing here searches. The sequence comes from wherever it comes from; what
this checks is that the index is the first one, and what it buys.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotAnEntry(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def _rational(x, where) -> Fraction:
    try:
        return Fraction(x)
    except (TypeError, ValueError, ZeroDivisionError):
        raise NotAnEntry(_t("entry.not_rational", where=where, got=repr(x)))


def crossed(value, threshold, direction, strict) -> bool:
    """Is `value` on the far side of the line?"""
    if direction == "up":
        return value > threshold if strict else value >= threshold
    return value < threshold if strict else value <= threshold


def certify(spec) -> dict:
    """Find the first crossing, check it is the first, and read off the window."""
    if spec.direction not in ("up", "down"):
        raise NotAnEntry(_t("entry.direction", got=spec.direction))
    values = list(spec.values() if callable(spec.values) else spec.values)
    if not values:
        raise NotAnEntry(_t("entry.empty"))
    seq = [_rational(v, "value {}".format(i)) for i, v in enumerate(values)]
    threshold = _rational(spec.threshold, "threshold")
    strict = bool(spec.strict)

    index = next((i for i, v in enumerate(seq)
                  if crossed(v, threshold, spec.direction, strict)), None)
    if index is None:
        return {"index": None, "prefix": [], "threshold": threshold,
                "direction": spec.direction, "strict": strict,
                "step_bound": None, "window": None, "steps_ok": True,
                "ok": False}

    prefix = seq[:index + 1]
    steps_ok, window = True, None
    if spec.step_bound is not None:
        delta = _rational(spec.step_bound, "step_bound")
        if delta < 0:
            raise NotAnEntry(_t("entry.negative_step", delta=str(delta)))
        steps_ok = all(abs(prefix[i + 1] - prefix[i]) <= delta
                       for i in range(len(prefix) - 1))
        if index > 0:
            # Only the LAST step is used: the one before the crossing was on
            # the near side, so the crossing overshoots by at most delta.
            window = threshold + delta if spec.direction == "up" \
                else threshold - delta

    return {
        "index": index,
        "prefix": [str(v) for v in prefix],
        "threshold": threshold,
        "direction": spec.direction,
        "strict": strict,
        "step_bound": None if spec.step_bound is None
        else str(_rational(spec.step_bound, "step_bound")),
        "window": None if window is None else str(window),
        "steps_ok": steps_ok,
        "ok": bool(steps_ok),
    }


def check(payload) -> dict:
    """Re-find the crossing in the stored prefix. The whole verification."""
    prefix = [Fraction(v) for v in payload["prefix"]]
    threshold = Fraction(payload["threshold"])
    direction, strict = payload["direction"], bool(payload["strict"])

    crosses = bool(prefix) and crossed(prefix[-1], threshold, direction, strict)
    before = [i for i, v in enumerate(prefix[:-1])
              if crossed(v, threshold, direction, strict)]
    indexed = len(prefix) - 1 == payload["index"]

    steps, window = True, None
    if payload.get("step_bound") is not None:
        delta = Fraction(payload["step_bound"])
        steps = all(abs(prefix[i + 1] - prefix[i]) <= delta
                    for i in range(len(prefix) - 1))
        if len(prefix) > 1:
            window = threshold + delta if direction == "up" else threshold - delta
    declared = payload.get("window")
    window_ok = (window is None and declared is None) or (
        window is not None and declared is not None
        and Fraction(declared) == window)

    return {"crosses": crosses, "earliest": not before, "indexed": indexed,
            "steps": steps, "window_ok": window_ok,
            "early": [str(i) for i in before[:4]],
            "value": str(prefix[-1]) if prefix else "-"}
