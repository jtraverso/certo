"""Exponents derived from relations, instead of assigned by hand.

`OrderSpec` asks for the exponent of every symbol. On a real term that is six
or seven numbers somebody worked out mentally from `|E| <= Lmass`, `C >= n`,
`d' >= C(n,2)` -- and if one of them is wrong the answer comes back clean and
false, which is the exact shape of an error nothing downstream catches.

WHAT THIS TAKES INSTEAD. The relations themselves:

    relations=["Lmass >= E * tC", "E ~ n**2", "tC ~ 1", "C >= n"]

`~` is "same order", `>=` and `<=` are bounds. Every relation is LINEAR in the
exponents -- `E ~ n**2` is `exp(E) = 2`, and `Lmass >= E * tC` is
`exp(Lmass) >= exp(E) + exp(tC)` -- so the system is a linear program over the
exponent vector, solved exactly.

IT DOES NOT NEED EVERY EXPONENT PINNED, and insisting on that would refuse
most real inputs. A `>=` gives a one-sided bound, and a one-sided bound on a
denominator is still a two-sided answer about the term: the exponent of the
whole expression is minimised and maximised over the feasible set, and

    hi < 0   ->  it decays, for every assignment the relations allow
    lo > 0   ->  it grows
    lo = hi  ->  the exponent is determined outright
    otherwise -> the relations do not decide it, and the interval says so

The last line is the point. A range that straddles zero is not a failure to
report -- it is the honest statement that the relations given are too weak,
and it names how much room is left.

WHAT IT DOES NOT ESTABLISH. That the relations are true: they are the spec's
claim, the way a group is for `reduce` and a dual is for `parametric`. And the
exponent is not the constant -- the same limit `order` has always had.
"""
from __future__ import annotations

import re
from fractions import Fraction

from .i18n import t as _t

EQ, GE, LE = "~", ">=", "<="
_OPS = (GE, LE, EQ)
_FACTOR = re.compile(r"^([A-Za-z_]\w*)(?:\^(-?\d+))?$")


class NotInferable(ValueError):
    """Raised with what was wrong: a bare failure helps nobody."""


def _side(text, where):
    """A product of powers -> {symbol: exponent multiplier}, constants free."""
    out = {}
    body = text.replace("**", "^").strip()
    if not body:
        raise NotInferable(_t("order.empty_side", rel=where))
    for factor in body.split("*"):
        f = factor.strip()
        if not f:
            raise NotInferable(_t("order.empty_side", rel=where))
        if re.fullmatch(r"-?\d+(/\d+)?", f):
            continue                       # a constant has exponent zero
        m = _FACTOR.match(f)
        if not m:
            raise NotInferable(_t("order.bad_factor", factor=f, rel=where))
        name, power = m.group(1), int(m.group(2) or 1)
        out[name] = out.get(name, 0) + power
    return out


def parse(relations) -> list:
    """`["A >= B * C", ...]` -> `[(op, {sym: mult}, {sym: mult}, text)]`."""
    out = []
    for text in relations or []:
        for op in _OPS:                    # ">=" and "<=" before "~"
            if op in text:
                left, right = text.split(op, 1)
                out.append((op, _side(left, text), _side(right, text), text))
                break
        else:
            raise NotInferable(_t("order.no_operator", rel=text,
                                  ops=" ".join(_OPS)))
    return out


def _rows(parsed, known, names):
    """Each relation as `coeffs . x <= const`, over the exponent vector."""
    rows = []

    def coeffs(left, right):
        c = {k: Fraction(v) for k, v in left.items()}
        for k, v in right.items():
            c[k] = c.get(k, Fraction(0)) - v
        return c

    for op, left, right, text in parsed:
        c = coeffs(left, right)
        if op == GE:                       # left >= right  ->  right - left <= 0
            rows.append(({k: -v for k, v in c.items()}, Fraction(0), text))
        elif op == LE:
            rows.append((c, Fraction(0), text))
        else:                              # equality, both ways
            rows.append((c, Fraction(0), text))
            rows.append(({k: -v for k, v in c.items()}, Fraction(0), text))

    # A symbol whose exponent the caller states outright is pinned the same
    # way, so `orders` and `relations` can be mixed without one silently
    # overriding the other.
    for name, value in (known or {}).items():
        rows.append(({name: Fraction(1)}, Fraction(value), "orders[{}]".format(name)))
        rows.append(({name: Fraction(-1)}, -Fraction(value),
                     "orders[{}]".format(name)))
    return rows


def _extreme(rows, names, target, sign):
    """`max sign * target . x` subject to the rows, exactly. None if unbounded."""
    from . import simplex

    A = [[row[0].get(v, Fraction(0)) for v in names] for row in rows]
    b = [row[1] for row in rows]
    c = [Fraction(sign) * target.get(v, Fraction(0)) for v in names]
    wide = [list(r) + [-x for x in r] for r in A]
    want = list(c) + [-x for x in c]
    try:
        y = simplex.minimise(wide, b, want)
    except Exception:                      # noqa: BLE001
        return None, None
    value = sum((bi * yi for bi, yi in zip(b, y)), Fraction(0))
    used = [rows[i][2] for i, yi in enumerate(y) if yi != 0]
    return value * sign, used


def infer(relations, known, wanted, var="n") -> dict:
    """The exponent of each wanted symbol, and of any linear combination.

    `wanted` maps a label to `{symbol: multiplier}` -- the exponent of a
    product is the sum of its exponents, so the expression `order` cares about
    is one of these.
    """
    parsed = parse(relations)
    # The growth variable is the SCALE, not an unknown: `E ~ n**2` says the
    # exponent of E is 2, which only follows once `n` itself is pinned at 1.
    # Leaving it free made every interval unbounded and every verdict
    # `undecided` -- true of the system as written, and not what was meant.
    pinned = dict(known or {})
    pinned.setdefault(var, 1)
    names = sorted({s for _op, l, r, _t2 in parsed for s in list(l) + list(r)}
                   | set(pinned)
                   | {s for m in wanted.values() for s in m})
    rows = _rows(parsed, pinned, names)

    out = {}
    for label, target in wanted.items():
        tgt = {k: Fraction(v) for k, v in target.items()}
        hi, hi_used = _extreme(rows, names, tgt, 1)
        lo, lo_used = _extreme(rows, names, tgt, -1)
        out[label] = {
            "lower": None if lo is None else str(lo),
            "upper": None if hi is None else str(hi),
            "determined": lo is not None and hi is not None and lo == hi,
            "verdict": _verdict(lo, hi),
            "from": sorted(set((lo_used or []) + (hi_used or []))),
        }
    return {"relations": [r[3] for r in parsed], "symbols": names,
            "var": var,
            "known": {k: str(v) for k, v in pinned.items()},
            "targets": {k: {s: str(m) for s, m in v.items()}
                        for k, v in wanted.items()},
            "results": out}


def _verdict(lo, hi) -> str:
    if hi is not None and hi < 0:
        return "decays"
    if lo is not None and lo > 0:
        return "grows"
    if lo is not None and hi is not None and lo == hi:
        return "theta" if lo == 0 else "determined"
    return "undecided"


def check(payload) -> dict:
    """Re-derive every interval from the relations: no solver, no search."""
    parsed = parse(payload["relations"])
    known = {k: Fraction(v) for k, v in payload.get("known", {}).items()}
    names = payload["symbols"]
    rows = _rows(parsed, known, names)
    out = {}
    for label, got in payload["results"].items():
        target = payload["targets"][label]
        tgt = {k: Fraction(v) for k, v in target.items()}
        hi, _ = _extreme(rows, names, tgt, 1)
        lo, _ = _extreme(rows, names, tgt, -1)
        out[label] = {
            "ok": (str(lo) if lo is not None else None) == got["lower"]
            and (str(hi) if hi is not None else None) == got["upper"]
            and _verdict(lo, hi) == got["verdict"],
            "lower": None if lo is None else str(lo),
            "upper": None if hi is None else str(hi),
        }
    return out


def derive_orders(relations, known, symbols, var="n") -> dict:
    """Every symbol's exponent, or a refusal naming the ones left free.

    `order` needs a number per symbol: its Laurent core is exact, and an
    interval is not an exponent. So the relations are solved, the symbols that
    come out DETERMINED become the `orders` dict, and any that do not are
    refused by name -- with the interval, because "Lmass is anywhere in
    [2, +inf)" tells you exactly which bound is missing, and "cannot infer"
    does not.
    """
    wanted = {s: {s: 1} for s in symbols}
    out = infer(relations, known, wanted, var=var)

    orders, free = {}, []
    for name, res in sorted(out["results"].items()):
        if res["determined"]:
            value = Fraction(res["lower"])
            if value.denominator != 1:
                free.append({"symbol": name, "lower": res["lower"],
                             "upper": res["upper"],
                             "why": "not an integer exponent"})
            else:
                orders[name] = int(value)
        else:
            free.append({"symbol": name, "lower": res["lower"],
                         "upper": res["upper"], "why": "undetermined"})

    if free:
        gaps = "; ".join(
            "{} in [{}, {}]".format(f["symbol"], f["lower"] or "-inf",
                                    f["upper"] or "+inf") for f in free[:4])
        raise NotInferable(_t("order.undetermined", gaps=gaps))

    return {"orders": orders, "relations": out["relations"],
            "symbols": out["symbols"], "var": var,
            "known": out["known"], "results": out["results"],
            "targets": out["targets"]}
