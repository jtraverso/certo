"""The best INTEGER choice, for a whole family of quadratics at once.

The shape turns up wherever a value function is optimised over something that
has to be a whole number -- a clique size, a block count, a number of parts.
On the reals it is one line: a concave quadratic peaks at `-B/2A`, done. Over
the integers the peak is at one of the two integers nearest that, and which
one, and what the value is, and whether the claim holds for EVERY parameter
value rather than the ones somebody ran, is where the work is.

A write-up reaches it like this: complete the square, observe the objective is
an integer at integer argument, conclude the maximum is the FLOOR of the
continuous peak, and attain it at the nearest integer. Every step is right.
None of them is a finite object a reader can check, because the floor of a
parametric expression is not a polynomial and there is nothing to expand.

THE CRITERION THAT IS POLYNOMIAL. Write the claimed integer maximiser as `x*`
and move the origin there. For any integer step `t`,

    q(x* + t) - q(x*)  =  A t^2 + q'(x*) t

with `A` the leading coefficient. When `A < 0` this is `<= 0` for every
non-zero integer `t` exactly when

    A  <=  q'(x*)  <=  -A

-- and that is it. Two polynomial inequalities in the parameters, no floor, no
residue, no case split inside the certificate. They are the statement that `x*`
is within half a step of the real vertex, written so that it expands.

The reason the bound is TIGHT rather than merely valid is that `x*` is an
integer, so `q(x*)` is attained. A certificate here therefore says two things
at once: no integer does better, and this integer does that well.

WHERE THE RESIDUES GO. They do not go in the certificate. Which integer is
nearest the vertex depends on the parameter modulo something, so the family
splits into classes and each class gets its own `x*`, its own certificate and
its own closed form -- the same division `parametric` makes for the branches of
a piecewise value function, and for the same reason: they are different claims.

WHAT THIS DOES NOT DO. It does not search for `x*`. Round the real vertex and
hand it over; checking one is arithmetic, and that split is the whole design.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t
from .polynomials import Poly


class NotAPeak(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def split(poly: Poly, variable: str):
    """`q = A x^2 + B x + C` with `A, B, C` polynomials in the parameters.

    Returns them in the PARAMETER ring, so everything downstream is about the
    parameters alone and the variable has been eliminated by being read off.
    """
    if variable not in poly.vars:
        raise NotAPeak(_t("peak.no_variable", name=variable,
                          names=", ".join(poly.vars)))
    k = poly.vars.index(variable)
    params = tuple(v for v in poly.vars if v != variable)
    degree = max((e[k] for e in poly.terms), default=0)
    if degree > 2:
        raise NotAPeak(_t("peak.too_high", name=variable, degree=degree))

    parts = [Poly(params) for _ in range(3)]
    for e, coef in poly.terms.items():
        rest = tuple(v for i, v in enumerate(e) if i != k)
        parts[e[k]] = parts[e[k]] + Poly(params, {rest: coef})
    return parts[2], parts[1], parts[0]


def certify(spec) -> dict:
    """The three checks, and everything the certificate needs to repeat them."""
    from .parametric import nonneg_on_region, region_terms

    variable = spec.variable
    objective = spec.objective
    if not isinstance(objective, Poly):
        raise NotAPeak(_t("peak.not_poly"))
    A, B, C = split(objective, variable)
    params = A.vars

    star = spec.argmax
    if not isinstance(star, Poly):
        star = Poly.const(params, star)
    if star.vars != params:
        raise NotAPeak(_t("peak.wrong_ring", got=", ".join(star.vars),
                          want=", ".join(params) or "-"))

    # `x*` has to BE an integer at every integer parameter value, or the whole
    # argument is about a point that does not exist. Integer coefficients are
    # a sufficient reason and a checkable one; anything else is refused rather
    # than assumed, because "it is an integer really" is exactly the kind of
    # step this tool exists not to take on trust.
    fractional = sorted(str(c) for c in star.terms.values()
                        if c.denominator != 1)
    integral = not fractional

    lows = dict(spec.parameters)
    terms = region_terms([(str(n), _as_poly(g, params))
                          for n, g in (spec.region or [])], lows)

    # Concavity: `-A > 0` on the ray. Non-negative by shift AND a strictly
    # positive constant term, because `-A >= 0` would allow the degenerate
    # `A = 0`, where there is no peak to find.
    neg_a = A.scaled(-1)
    concave_shape, _sh, _u, _r = nonneg_on_region(neg_a, lows, terms)
    const = neg_a.terms.get((0,) * len(params), Fraction(0))
    concave = concave_shape and const > 0

    # The criterion. `q'(x) = 2 A x + B`, evaluated at the claimed maximiser.
    slope = A.scaled(2) * star + B
    upper = neg_a - slope                     # q'(x*) <= -A
    lower = slope - A                         # q'(x*) >= A
    up_ok, _s1, up_mult, _r1 = nonneg_on_region(upper, lows, terms)
    low_ok, _s2, low_mult, _r2 = nonneg_on_region(lower, lows, terms)

    value = A * star * star + B * star + C

    return {
        "A": A, "B": B, "C": C,
        "argmax": star,
        "slope": slope,
        "value": value,
        "upper": upper, "lower": lower,
        "upper_ok": up_ok, "lower_ok": low_ok,
        "upper_multipliers": {k: str(v) for k, v in up_mult.items()},
        "lower_multipliers": {k: str(v) for k, v in low_mult.items()},
        "concave": concave,
        "integral": integral,
        "fractional": fractional,
        "region": {str(n): _as_poly(g, params).serialize()
                   for n, g in (spec.region or [])},
        "ok": concave and integral and up_ok and low_ok,
    }


def _as_poly(x, ring):
    if isinstance(x, Poly):
        if x.vars != ring:
            raise NotAPeak(_t("peak.wrong_ring", got=", ".join(x.vars),
                              want=", ".join(ring) or "-"))
        return x
    if isinstance(x, (int, Fraction)):
        return Poly.const(ring, x)
    return Poly.from_z3(x, ring)
