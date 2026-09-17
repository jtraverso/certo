"""The largest of many linear programs, and why nothing beats it.

The shape comes from a script somebody wrote by hand: enumerate every
bipartition of a graph's edges, solve one linear program per bipartition in
floating point, take the largest, and then re-solve just that one in exact
rationals to confirm the number. Sixteen thousand LPs, one of which is the
answer.

That confirms the WINNER and leaves the claim unmade. "No bipartition does
better" is a statement about all sixteen thousand, and re-solving the best one
says nothing about the other 16,383. Reading a float maximum as the maximum is
the same step `cover --optimize` was built for after a valid cover was read as
an optimal one.

The certificate has two halves and they are not symmetric.

  THE WINNER is attained: an exact primal and an exact dual whose values meet,
  so that item's optimum IS the claimed value and not a bound on it.

  EVERY OTHER ITEM is bounded: a dual `y >= 0` with `A^T y >= c` and
  `b.y <= V`. That is all it takes, and it is much less than solving them.
  A dual does not have to be optimal to bound -- it has to be feasible, and
  weak duality does the rest. So the expensive half of the search never has to
  be exact; only the checking does.

NOTHING STORES AN LP. Each item's program is rebuilt from the spec and the
item, by the spec's own function, and the stored vectors are checked against
what comes out. The alternative -- carrying one linear program per item -- is
both enormous and unchecked, and a dual for a different item's program would
fit it perfectly. That is the same hole a branch-and-bound tree had.

So verification NEEDS THE SPEC, the way a sweep's replay does, and says so
when it does not have it rather than checking less while looking the same.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotAFamily(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def leq_parts(lp_spec):
    """`max c.x, A x <= b, x >= 0` for one item, exactly.

    One reading of "the item's linear program", shared by the producer and the
    verifier, for the same reason `tree.restrict` is: two readings is the gap a
    forged certificate fits through.
    """
    from . import exact

    if lp_spec.sense != "max":
        raise NotAFamily(_t("family.max_only", sense=lp_spec.sense))
    A, b, c, _names = lp_spec.as_leq_system()
    return ([[exact.to_fraction(v) for v in row] for row in A],
            [exact.to_fraction(v) for v in b],
            [exact.to_fraction(v) for v in c])


def bounds_value(A, b, c, y, value) -> bool:
    """Does this dual bound this program by `value`? Weak duality, checked.

    `y >= 0` and `A^T y >= c` make `b.y` an upper bound on the optimum, so
    `b.y <= value` puts the optimum under `value`. Three passes over the data
    and no solver.
    """
    if len(y) != len(A) or any(v < 0 for v in y):
        return False
    for j in range(len(c)):
        if sum(A[i][j] * y[i] for i in range(len(A))) < c[j]:
            return False
    return sum(bi * yi for bi, yi in zip(b, y)) <= value


def attains_value(A, b, c, x, y, value) -> bool:
    """Is `value` ATTAINED here -- a feasible primal and dual that meet?

    The winner needs more than a bound: if its own optimum were below the
    claimed maximum, the maximum would be a number no item reaches.
    """
    if len(x) != len(c) or any(v < 0 for v in x):
        return False
    for i in range(len(A)):
        if sum(A[i][j] * x[j] for j in range(len(c))) > b[i]:
            return False
    primal = sum(cj * xj for cj, xj in zip(c, x))
    if primal != value:
        return False
    return bounds_value(A, b, c, y, value)


def certify(spec, limits=None) -> dict:
    """Solve every item, keep the winner exactly, and bound the rest."""
    from . import exact
    from .engines import lp as lp_engine
    from .status import Verdict

    items = spec.items() if callable(spec.items) else list(spec.items)
    items = list(items)
    if not items:
        raise NotAFamily(_t("family.empty"))
    key = spec.key or str
    ids = [str(key(it)) for it in items]
    if len(set(ids)) != len(ids):
        raise NotAFamily(_t("family.duplicate_ids", n=len(ids) - len(set(ids))))

    best = None                      # (value, index, primal, dual)
    duals, failed = {}, []
    for i, item in enumerate(items):
        one = spec.lp(item)
        leq_parts(one)               # refuse a min item before solving it
        got = lp_engine.opt(one, limits)
        if got.certificate is None or not got.meta.get("exact"):
            failed.append(ids[i])
            continue
        p = got.certificate.payload
        value = exact.to_fraction(got.meta["objective"])
        duals[i] = [str(v) for v in p["dual"]]
        if best is None or value > best[0]:
            best = (value, i, [str(v) for v in p["primal"] or []],
                    list(duals[i]))

    if failed:
        raise NotAFamily(_t("family.inexact", n=len(failed),
                            names=", ".join(failed[:4])))

    value, win, primal, dual = best
    return {
        "items": items, "ids": ids, "value": value, "argmax": ids[win],
        "argmax_index": win, "primal": primal, "dual": dual,
        "bounds": [[ids[i], duals[i]] for i in range(len(items)) if i != win],
        "count": len(items),
    }


def check(payload, spec, limits=None) -> tuple:
    """Re-derive every item's program and re-check the vector stored for it.

    Returns `(ok_argmax, bad, missing)`. Needs the spec, because the programs
    are not stored -- which is what stops a dual for one item closing another.
    """
    from . import exact

    items = spec.items() if callable(spec.items) else list(spec.items)
    key = spec.key or str
    by_id = {str(key(it)): it for it in items}
    value = exact.to_fraction(payload["value"])

    A, b, c = leq_parts(spec.lp(by_id[payload["argmax"]])) \
        if payload["argmax"] in by_id else (None, None, None)
    ok_argmax = A is not None and attains_value(
        A, b, c, exact.parse_all(payload["primal"]),
        exact.parse_all(payload["dual"]), value)

    bad, missing = [], []
    for item_id, y in payload["bounds"]:
        item = by_id.get(item_id)
        if item is None:
            missing.append(item_id)
            continue
        A, b, c = leq_parts(spec.lp(item))
        if not bounds_value(A, b, c, exact.parse_all(y), value):
            bad.append(item_id)
    # An item in the family that the certificate never bounded is exactly the
    # gap this exists to close: the maximum would be over a subfamily.
    covered = {payload["argmax"]} | {i for i, _ in payload["bounds"]}
    missing.extend(sorted(set(by_id) - covered))
    return ok_argmax, bad, missing
