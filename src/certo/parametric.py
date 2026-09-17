"""A bound that holds for EVERY value of a parameter, not for the ones you tried.

This is the thing certo has kept saying it cannot do. A sweep checks
`p = 5..12`; a user then writes "and similarly for larger p", and that sentence
is where the work actually is.

For a linear program whose data are POLYNOMIALS in the parameters,

    max c(p).x   subject to   A(p) x <= b(p),  x >= 0

weak duality is available symbolically. Any `y >= 0` with `A(p)^T y >= c(p)`
gives `opt(p) <= b(p).y`, for every `p` at once. So a certificate that the
optimum is bounded by `B(p) = b(p).y` on `p >= p0` needs three things, and
none of them is a solver:

  1. `y >= 0` -- rational constants, compared.
  2. `A(p)^T y - c(p) >= 0` for every column, for all `p >= p0` -- a finite
     set of polynomial inequalities in the parameters.
  3. `B(p) = b(p).y`, expanded.

Only (2) is interesting, and it is handled by a SHIFT. Substitute
`p = p0 + u` with `u >= 0`: if every coefficient of the shifted polynomial is
non-negative, the polynomial is non-negative on the whole ray, because `u` and
all its powers are. Checking that is reading signs off a list.

The shift is SUFFICIENT AND NOT NECESSARY, and this file says so rather than
implying otherwise. `p^2 - 3p + 3` is positive everywhere and shifts to
`(3, -3, 1)` at `p0 = 0`; the test fails and the fact holds. When that happens
the answer is "not certified by this route", never "false" -- and the shifted
coefficients are reported so the next step is obvious.

WHERE THE DUAL COMES FROM is deliberately not this file's problem. Solve one
instance with `opt`, read the dual, and hand it over. That division is the
point: finding a `y` is search and can be as numeric as it likes; checking one
is arithmetic. It is the same split as `farkas`, one level up -- there the
multipliers are constants, here they are constants attached to a family.

TWO SHAPES, NOT ONE. The above is the packing shape: maximise, `<=` rows, and
a bound from above. Symmetrised COVER programs are the other half of the same
duality and turn up at least as often --

    min w(p).z   subject to   M z >= 1,  z >= 0

-- where the useful certificate is a feasible PACKING `y >= 0` with
`M^T y <= w(p)`, giving `opt(p) >= 1.y` for every `p` at once. Same three
checks with the residual's sign flipped, so `sense="min"` with `>=` rows is
accepted and the claim it certifies is a bound from BELOW.

A COVER PROGRAM'S DUAL IS NOT CONSTANT. In the packing shape the multipliers
are pure numbers, because they are rates. In the cover shape the dual is a
packing, and a packing of a growing object grows with it: `d(d-1)/2` triangles
on a neighbourhood of size `d`. So a dual entry may itself be a polynomial in
the parameters, and then `y >= 0` stops being a comparison and becomes the
same shift test as everything else. Both are allowed, and a constant is just
the degree-zero case.
"""
from __future__ import annotations

from fractions import Fraction
from math import comb

from .i18n import t as _t
from .polynomials import Poly


class NotParametric(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def shift(poly: Poly, offsets: dict) -> Poly:
    """Substitute `v -> v + offset` for each named variable, exactly.

    One variable at a time, expanding `v^k` binomially. The result lives in
    the same ring, where the variable now means the DISTANCE above the offset.
    """
    out = poly
    for name, off in offsets.items():
        off = Fraction(off)
        if not off:
            continue
        if name not in out.vars:
            raise NotParametric(_t("param.unknown", name=name,
                                   names=", ".join(out.vars)))
        k = out.vars.index(name)
        acc = Poly(out.vars)
        for e, coef in out.terms.items():
            power = e[k]
            for j in range(power + 1):
                mono = list(e)
                mono[k] = j
                weight = Fraction(comb(power, j)) * off ** (power - j)
                acc = acc + Poly(out.vars, {tuple(mono): coef * weight})
        out = acc
    return out


def nonneg_on_ray(poly: Poly, lows: dict):
    """Is `poly >= 0` everywhere at or above `lows`? Returns (ok, shifted).

    Sufficient, not necessary: every coefficient non-negative after the shift
    means the polynomial is a non-negative combination of products of
    non-negative quantities. A negative coefficient decides nothing, and the
    caller is told exactly that.
    """
    shifted = shift(poly, lows)
    return all(c >= 0 for c in shifted.terms.values()), shifted


# ---------------------------------------------------------------------------


def dual_text(poly) -> str:
    """How a dual entry reads. One function, so the two copies cannot drift.

    `dual` is what somebody opening the file sees and `dual_poly` is what the
    verifier recomputes from; they are checked against each other, and that
    check is only meaningful if both sides agree on what the text should be.
    """
    if not poly.terms:
        return "0"
    if len(poly.terms) == 1 and not any(next(iter(poly.terms))):
        return str(next(iter(poly.terms.values())))
    return str(poly)


def certify(spec) -> dict:
    """The three checks, and everything the certificate needs to repeat them.

    `spec.constraints` are `(name, {var: coef}, sense, rhs)` with every
    coefficient a polynomial in the parameters, `sense` being `"<="` for a
    maximisation and `">="` for a minimisation; `spec.dual` is one rational --
    or one polynomial -- per constraint name.
    """
    params = tuple(spec.parameters)
    ring = params
    minimising = getattr(spec, "sense", "max") == "min"

    def P(x):
        if isinstance(x, Poly):
            if x.vars != ring:
                raise NotParametric(_t("param.wrong_ring",
                                       got=", ".join(x.vars),
                                       want=", ".join(ring)))
            return x
        if isinstance(x, (int, Fraction)):
            return Poly.const(ring, x)
        return Poly.from_z3(x, ring)

    y = {n: P(v) for n, v in spec.dual.items()}
    names = [n for n, _, _, _ in spec.constraints]
    missing = [n for n in names if n not in y]
    if missing:
        raise NotParametric(_t("param.dual_missing",
                               names=", ".join(missing[:5])))
    extra = [n for n in y if n not in names]
    if extra:
        raise NotParametric(_t("param.dual_extra", names=", ".join(extra[:5])))

    # `y >= 0`. A constant dual is a comparison; a polynomial one is the same
    # shift test the residuals get, and "not shown non-negative" is what a
    # failure means there -- never "negative".
    negative, dual_rows = [], []
    for name in sorted(y):
        ok, shifted = nonneg_on_ray(y[name], spec.parameters)
        if not ok:
            negative.append(name)
        dual_rows.append({"constraint": str(name), "value": y[name].serialize(),
                          "shifted": shifted.serialize(), "ok": ok})

    # A^T y - c, column by column. Every variable that appears anywhere gets a
    # column, including ones the objective never mentions: a variable with no
    # objective coefficient still constrains the dual.
    variables = sorted({v for _, row, _, _ in spec.constraints for v in row}
                       | set(spec.objective))
    rows = []
    for var in variables:
        acc = Poly(ring)
        for name, row, _sense, _rhs in spec.constraints:
            if var in row and y[name].terms:
                acc = acc + P(row[var]) * y[name]
        obj = P(spec.objective.get(var, 0))
        # Maximise: `A^T y >= c`. Minimise: `M^T y <= w`. One sign.
        residual = (obj - acc) if minimising else (acc - obj)
        ok, shifted = nonneg_on_ray(residual, spec.parameters)
        rows.append({"variable": var,
                     "residual": residual.serialize(),
                     "shifted": shifted.serialize(),
                     "ok": ok,
                     "negative": sorted(str(c) for c in shifted.terms.values()
                                        if c < 0)})

    bound = Poly(ring)
    for name, _row, _sense, rhs in spec.constraints:
        if y[name].terms:
            bound = bound + P(rhs) * y[name]

    return {
        "variables": variables,
        "rows": rows,
        "bound": bound,
        "sense": "min" if minimising else "max",
        "dual_rows": dual_rows,
        "polynomial_dual": any(len(p.terms) > 1 or any(e for e in p.terms)
                               for p in y.values()),
        "negative_dual": negative,
        "ok": not negative and all(r["ok"] for r in rows),
        "failed": [r["variable"] for r in rows if not r["ok"]],
    }


def evaluate(poly: Poly, values: dict) -> Fraction:
    """The polynomial at one point. For checking a bound against a known LP."""
    total = Fraction(0)
    for e, coef in poly.terms.items():
        term = coef
        for name, power in zip(poly.vars, e):
            if power:
                term *= Fraction(values[name]) ** power
        total += term
    return total
