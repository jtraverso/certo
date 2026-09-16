"""Orders of magnitude: does this term decay, or is it Theta(1)?

A user described the bug this exists for better than I could have. They had a
symbolic constraint, substituted asymptotic magnitudes by hand -- `d` is about
`n^2`, `C` about `n`, `|W|` about `n^2` -- and asked whether a term decays in
`n`. Four bugs lived in that step. One of them,

    5|k| W C^2 / (u^3 d^2 p^10)

was constant in `n`, and it was invisible to BOTH Lean and `prove`, for the
same reason: **it is not an infeasibility.** It is a feasibility that does not
improve with `n`, and a solver asked "is this satisfiable" will keep saying
yes, correctly, forever.

That is a different question from any the tool could ask. So:

    order(expr, {"d": 2, "C": 1, "W": 2, "u": 0, "p": 0, "k": 0})

substitutes `n^a` for each symbol, collects the expression into powers of `n`
with EXACT rational coefficients, and reports the leading exponent. Negative
means it decays, positive means it grows, and zero -- the case that hurt --
means Theta(1): the term is not going away however large `n` gets.

Two things it is careful about, because both would make it lie.

Cancellation is real. Two terms with the same exponent whose coefficients sum
to zero do not contribute, and since the coefficients are `Fraction` that is
decided rather than estimated.

And `≍` hides a constant. This certifies the EXPONENT of `n`, not the
constant in front of it. A `Theta(1)` term with a coefficient of 1e-9 may be
perfectly fine in practice; what the certificate says is that it does not
shrink, and it says only that.
"""
from __future__ import annotations

from fractions import Fraction

import z3

from .i18n import t

#: A Laurent monomial is {symbol: exponent}, exponents may be negative -- which
#: is the whole point, since the interesting terms are quotients.
DECAYS, CONSTANT, GROWS = "decays", "constant", "grows"


class NotAsymptotic(ValueError):
    """Raised with the offending subterm, because "it failed" is useless."""


def _mono_mul(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
        if out[k] == 0:
            del out[k]
    return out


def _key(m: dict):
    return tuple(sorted(m.items()))


class Laurent:
    """A sum of Laurent monomials with exact rational coefficients."""

    __slots__ = ("terms",)

    def __init__(self, terms=None):
        self.terms = {}
        for m, c in (terms or {}).items():
            c = Fraction(c)
            if c:
                self.terms[m] = c

    @classmethod
    def const(cls, c):
        return cls({(): Fraction(c)})

    @classmethod
    def var(cls, name):
        return cls({((name, 1),): Fraction(1)})

    def __add__(self, other):
        out = dict(self.terms)
        for m, c in other.terms.items():
            out[m] = out.get(m, Fraction(0)) + c
            if not out[m]:
                del out[m]
        return Laurent(out)

    def __neg__(self):
        return Laurent({m: -c for m, c in self.terms.items()})

    def __sub__(self, other):
        return self + (-other)

    def __mul__(self, other):
        out = {}
        for m1, c1 in self.terms.items():
            for m2, c2 in other.terms.items():
                m = _key(_mono_mul(dict(m1), dict(m2)))
                out[m] = out.get(m, Fraction(0)) + c1 * c2
                if not out[m]:
                    del out[m]
        return Laurent(out)

    def inverse(self):
        """Only a single monomial can be inverted, and that is the honest limit.

        `1/(x + y)` is not a Laurent polynomial and its order depends on which
        of x and y dominates -- a question this cannot answer and should not
        pretend to. Divide by a product, not by a sum.
        """
        if len(self.terms) != 1:
            raise NotAsymptotic(t("asym.divide_sum", n=len(self.terms)))
        (m, c), = self.terms.items()
        return Laurent({_key({k: -v for k, v in dict(m).items()}):
                        Fraction(1) / c})

    def power(self, n: int):
        out = Laurent.const(1)
        base = self if n >= 0 else self.inverse()
        for _ in range(abs(n)):
            out = out * base
        return out


def parse(expr) -> Laurent:
    """A z3 arithmetic term as a Laurent polynomial. Division included."""
    if z3.is_int_value(expr):
        return Laurent.const(expr.as_long())
    if z3.is_rational_value(expr):
        return Laurent.const(expr.as_fraction())
    if z3.is_const(expr) and expr.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        return Laurent.var(str(expr))
    if z3.is_add(expr):
        out = Laurent()
        for c in expr.children():
            out = out + parse(c)
        return out
    if z3.is_sub(expr):
        a, b = expr.children()
        return parse(a) - parse(b)
    if z3.is_mul(expr):
        out = Laurent.const(1)
        for c in expr.children():
            out = out * parse(c)
        return out
    if z3.is_app_of(expr, z3.Z3_OP_UMINUS):
        return -parse(expr.arg(0))
    if z3.is_div(expr) or z3.is_idiv(expr):
        a, b = expr.children()
        return parse(a) * parse(b).inverse()
    if z3.is_app_of(expr, z3.Z3_OP_POWER):
        from .linarith import _literal_exponent

        base, exp = expr.children()
        n = _literal_exponent(exp)
        if n is None:
            # A negative literal exponent is fine here -- unlike in linarith,
            # a quotient IS the shape we are here for.
            n = _negative_exponent(exp)
        if n is None:
            raise NotAsymptotic(t("asym.bad_exponent", expr=str(expr)))
        return parse(base).power(n)
    raise NotAsymptotic(t("asym.not_arithmetic", expr=str(expr)))


def _negative_exponent(exp):
    if z3.is_int_value(exp):
        return exp.as_long()
    if z3.is_rational_value(exp):
        f = exp.as_fraction()
        return f.numerator if f.denominator == 1 else None
    return None


# ---------------------------------------------------------------------------


def order(expr, orders: dict, var: str = "n"):
    """The exponent of `var`, and the terms that produce it.

    `orders` maps each symbol to its exponent: `{"d": 2}` for `d` about `n^2`,
    `{"u": 0}` for `u` about a constant, `{"r": Fraction(1,2)}` for a square
    root. A symbol with no entry is an error rather than an assumption -- the
    whole point is that the assignment is explicit.
    """
    poly = parse(expr) if not isinstance(expr, Laurent) else expr
    missing = sorted({s for m in poly.terms for s, _ in m} - set(orders))
    if missing:
        raise NotAsymptotic(t("asym.unassigned", names=", ".join(missing)))

    by_exp: dict = {}
    rows = []
    for m, c in poly.terms.items():
        e = sum((Fraction(orders[s]) * p for s, p in m), Fraction(0))
        by_exp[e] = by_exp.get(e, Fraction(0)) + c
        rows.append({"monomial": _render(m), "coefficient": str(c),
                     "exponent": str(e)})

    # Cancellation is real, and with exact coefficients it is decided rather
    # than estimated: a term whose coefficients sum to zero is not there.
    surviving = {e: c for e, c in by_exp.items() if c}
    degree = max(surviving) if surviving else None
    return {
        "terms": sorted(rows, key=lambda r: Fraction(r["exponent"]),
                        reverse=True),
        "collected": sorted(({"exponent": str(e), "coefficient": str(c)}
                             for e, c in surviving.items()),
                            key=lambda r: Fraction(r["exponent"]),
                            reverse=True),
        "degree": None if degree is None else str(degree),
        "verdict": _verdict(degree),
        "cancelled": len(by_exp) - len(surviving),
        "var": var,
    }


def _verdict(degree):
    if degree is None:
        return DECAYS            # identically zero decays as fast as anything
    if degree < 0:
        return DECAYS
    return CONSTANT if degree == 0 else GROWS


def _render(m) -> str:
    if not m:
        return "1"
    return " ".join("{}^{}".format(s, p) if p != 1 else s for s, p in m)
