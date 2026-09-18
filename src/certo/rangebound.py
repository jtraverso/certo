"""The admissible RANGE of a variable, not one point of it.

`check --hypotheses-only` answers "is this regime inhabited?" and hands back a
model: one point where the hypotheses hold. That is the right answer to that
question, and it is not the question people usually have next. A user asking
whether their repaired window was sound got `a = 0` -- true, and what they
needed was `a <= 1/3`, the whole interval, which they then derived by hand.

WHAT THIS COMPUTES. For a variable `a` and a regime of linear hypotheses, the
exact rational `min a` and `max a` over that regime, each with the certificate
that establishes it.

THE CERTIFICATE IS A FARKAS COMBINATION, which is why this is worth a command
rather than a loop. `a <= 1/3` follows from the hypotheses exactly when some
non-negative combination of them yields it, and LP duality says the tightest
such bound is the optimum of

    min b.y   subject to   A^T y = e_a,   y >= 0

so the multipliers ARE the proof. Checking one is multiplying out and adding
fractions: no solver, and nobody has to trust the search that found it.

The equality in the dual, rather than `>=`, is what lets the variables be
FREE. A regime is not a packing; `a` may be negative, and a dual derived under
`x >= 0` would certify a bound that does not hold.

WHAT IT DOES NOT ESTABLISH. That the endpoint is attained, when the binding
row is a strict inequality: `a < 1/3` and `a <= 1/3` have the same supremum
and only one of them contains it, so strictness is reported rather than
rounded away. And nothing outside linear arithmetic -- a non-linear hypothesis
is refused by name rather than dropped, because dropping one would widen the
range and the answer would be wrong in the direction that looks safe.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotRangeable(ValueError):
    """Raised with what was wrong: a bare failure helps nobody."""


UNBOUNDED = "unbounded"
EMPTY = "empty"
STRICT = "strict"


def _hypothesis_rows(spec):
    """The hypotheses as `p REL 0`, with equalities split in two.

    Built from `spec.assumptions` rather than `linarith.rows_of`, which also
    parses the GOAL: a range is a question about the regime, and a claim this
    command never reads should not be able to refuse it.
    """
    from . import linarith

    out = []
    for name, f in spec.assumptions:
        poly, rel = linarith.as_row(f)
        if rel == "=":
            out.append((name, poly, "<="))
            out.append((name + "_rev", {m: -c for m, c in poly.items()}, "<="))
        else:
            out.append((name, poly, rel))
    return out


def _linear_rows(spec):
    """The hypotheses as `(name, {var: coef}, const, strict)`, or refuse."""
    out = []
    for name, poly, rel in _hypothesis_rows(spec):
        coeffs, const = {}, Fraction(0)
        for monomial, coef in poly.items():
            if len(monomial) == 0:
                const += Fraction(coef)
            elif len(monomial) == 1:
                coeffs[monomial[0]] = coeffs.get(monomial[0], Fraction(0)) \
                    + Fraction(coef)
            else:
                raise NotRangeable(_t("range.not_linear", name=name,
                                      term="*".join(monomial)))
        out.append((name, coeffs, const, rel == "<"))
    if not out:
        raise NotRangeable(_t("range.no_hypotheses"))
    return out


def variables_of(spec) -> list:
    """Every symbol the hypotheses mention, in a stable order."""
    seen = set()
    for _name, coeffs, _c, _s in _linear_rows(spec):
        seen.update(coeffs)
    return sorted(seen)


def _endpoint(rows, names, var, sign, limits):
    """`max sign*var` over the rows, as a dual. Returns None when unbounded.

    `A x <= b` with x FREE, so the dual constraint is an equality and is
    encoded as the two inequalities the exact simplex accepts.
    """
    from . import simplex

    A = [[row[1].get(v, Fraction(0)) for v in names] for row in rows]
    b = [-row[2] for row in rows]
    c = [Fraction(sign) if v == var else Fraction(0) for v in names]

    # A^T y = c  <=>  A^T y >= c  and  (-A)^T y >= -c
    wide = [list(r) + [-x for x in r] for r in A]
    target = list(c) + [-x for x in c]

    try:
        y = simplex.minimise(wide, b, target)
    except Exception as exc:                       # noqa: BLE001
        # No feasible dual means the primal is unbounded in this direction --
        # a legitimate answer, and a different one from "no range".
        return {"bound": None, "why": UNBOUNDED, "detail": str(exc)}

    value = sum((bi * yi for bi, yi in zip(b, y)), Fraction(0))
    used = [rows[i][0] for i, yi in enumerate(y) if yi != 0]
    strict = any(rows[i][3] for i, yi in enumerate(y) if yi != 0)
    return {"bound": value * sign, "multipliers": {rows[i][0]: y[i]
                                                   for i in range(len(y))
                                                   if y[i] != 0},
            "used": used, "strict": strict, "why": None}


def _inhabited(rows, names, limits) -> bool:
    """Is there any point at all? `max 0` is feasible exactly when there is.

    This has to be asked FIRST. Over an empty regime every endpoint comes back
    unbounded -- the dual of an infeasible primal is -- and the honest reading
    of that is not "a ranges over everything". It is that there is no `a`. The
    first version of this reported `(-inf, +inf)` for `a <= 1 and a >= 3`,
    which is the wrong answer in the direction that looks permissive.
    """
    probe = _endpoint(rows, names, None, 0, limits)
    return probe["bound"] is not None


def bounds_of(spec, var, limits=None) -> dict:
    """`min var` and `max var` over the regime, each with its multipliers."""
    rows = _linear_rows(spec)
    names = sorted({v for _n, c, _c, _s in rows for v in c})
    if var not in names:
        raise NotRangeable(_t("range.unknown_variable", name=var,
                              known=", ".join(names[:6]) or "-"))

    if not _inhabited(rows, names, limits):
        return {
            "variable": var, "variables": names, "empty": True,
            "rows": [{"name": n, "coeffs": {k: str(v) for k, v in c.items()},
                      "const": str(k), "strict": s} for n, c, k, s in rows],
            "lower": {"bound": None, "why": EMPTY},
            "upper": {"bound": None, "why": EMPTY},
            "interval": "(empty)",
            "title": getattr(spec, "title", ""),
        }

    hi = _endpoint(rows, names, var, 1, limits)
    lo = _endpoint(rows, names, var, -1, limits)

    return {
        "variable": var,
        "variables": names,
        "empty": False,
        "rows": [{"name": n, "coeffs": {k: str(v) for k, v in c.items()},
                  "const": str(k), "strict": s} for n, c, k, s in rows],
        "lower": _serial(lo),
        "upper": _serial(hi),
        # Both ends open is not the same statement as both ends closed, and a
        # reader who cannot see which got a different interval.
        "interval": _interval(lo, hi),
        "title": getattr(spec, "title", ""),
    }


def _serial(end) -> dict:
    if end["bound"] is None:
        return {"bound": None, "why": end["why"]}
    return {"bound": str(end["bound"]),
            "multipliers": {k: str(v) for k, v in end["multipliers"].items()},
            "used": end["used"], "strict": end["strict"], "why": None}


def _interval(lo, hi) -> str:
    left = "(-inf" if lo["bound"] is None else \
        ("(" if lo["strict"] else "[") + str(lo["bound"])
    right = "+inf)" if hi["bound"] is None else \
        str(hi["bound"]) + (")" if hi["strict"] else "]")
    return left + ", " + right


def check(payload) -> dict:
    """Re-derive every claim from the rows: no solver, no search.

    A multiplier vector is checked, never believed. Non-negative, combining to
    exactly `+/- e_var`, and reaching the declared value -- three products and
    a comparison.
    """
    rows = {r["name"]: r for r in payload["rows"]}
    out = {}
    for side, sign in (("upper", 1), ("lower", -1)):
        end = payload[side]
        if end["bound"] is None:
            out[side] = {"ok": True, "why": end.get("why")}
            continue
        mult = {k: Fraction(v) for k, v in end["multipliers"].items()}
        bad = [k for k, v in mult.items() if v < 0 or k not in rows]
        combo, rhs = {}, Fraction(0)
        for name, y in mult.items():
            if name not in rows:
                continue
            for v, coef in rows[name]["coeffs"].items():
                combo[v] = combo.get(v, Fraction(0)) + y * Fraction(coef)
            rhs += y * -Fraction(rows[name]["const"])
        want = {payload["variable"]: Fraction(sign)}
        combo = {k: v for k, v in combo.items() if v != 0}
        out[side] = {
            "ok": not bad and combo == want
            and rhs == Fraction(end["bound"]) * sign,
            "negative": bad,
            "combination": {k: str(v) for k, v in combo.items()},
            "reached": str(rhs * sign),
        }
    return out
