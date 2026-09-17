"""A rational-function inequality, for every n at once, with no solver.

Statements like

    (n - 2) / n^2  <=  1 / n        for every n >= 2

turn up constantly in the middle of an argument -- a step bound, a window
width, an error term -- and they are exactly the kind of thing nobody wants to
stop and prove. `certo prove` settles them, and its certificate is an unsat
core, which re-checks by running a solver again. For a line of arithmetic in a
long proof that is a heavy artefact.

There is a much smaller one. Clear the denominators and the claim becomes a
polynomial inequality on a ray, which is the shift test the parametric bound
already uses:

    right_num * left_den  -  left_num * right_den  >=  0

CLEARING DENOMINATORS IS THE STEP THAT CAN GO WRONG, so it is the step that
gets checked. Multiplying both sides by `left_den * right_den` preserves the
direction only when both are POSITIVE, and "n^2 is positive" is obvious while
"n^2 - 3n + 1 is positive for n >= 3" is not. Each denominator is put through
the same test, and a denominator not shown positive is a refusal rather than
an assumption -- because if one were negative the inequality would flip and
the certificate would be exactly backwards.

STRICTNESS is a coefficient, not an afterthought. `>= 0` on the ray needs
every shifted coefficient non-negative; `> 0` needs that AND a positive
constant term, since the constant term is the value at the floor.

The shift is SUFFICIENT AND NOT NECESSARY, here as everywhere. A failure means
"not established by this route" and never "false", and no certificate is
emitted for one.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t
from .polynomials import Poly


class NotARatio(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


def positive_on_ray(poly: Poly, lows: dict, terms=()):
    """Is `poly > 0` at and above `lows`? Returns (ok, shifted).

    Non-negative by shift, plus a strictly positive constant term -- which is
    the value AT the floor, so together they give strict positivity on the
    whole ray.
    """
    from .parametric import nonneg_on_region

    ok, shifted, _used, _rem = nonneg_on_region(poly, lows, terms)
    const = shifted.terms.get((0,) * len(poly.vars), Fraction(0))
    return bool(ok and const > 0), shifted


def as_ratio(side, ring):
    """A side of the inequality as `(numerator, denominator)`."""
    if isinstance(side, Poly):
        return side, Poly.const(ring, 1)
    if isinstance(side, (tuple, list)):
        if len(side) != 2:
            raise NotARatio(_t("ratio.pair", n=len(side)))
        num, den = side
        return (num if isinstance(num, Poly) else Poly.const(ring, num),
                den if isinstance(den, Poly) else Poly.const(ring, den))
    if isinstance(side, (int, Fraction)):
        return Poly.const(ring, side), Poly.const(ring, 1)
    raise NotARatio(_t("ratio.not_poly", got=type(side).__name__))


def certify(spec) -> dict:
    """The three checks: both denominators positive, and the difference signed."""
    from .parametric import nonneg_on_region, region_terms

    ring = tuple(spec.parameters)
    lows = dict(spec.parameters)
    ln, ld = as_ratio(spec.left, ring)
    rn, rd = as_ratio(spec.right, ring)
    for p in (ln, ld, rn, rd):
        if p.vars != ring:
            raise NotARatio(_t("ratio.wrong_ring", got=", ".join(p.vars),
                               want=", ".join(ring)))
    if spec.relation not in ("<=", "<"):
        raise NotARatio(_t("ratio.relation", rel=spec.relation))

    terms = region_terms([(str(n), as_ratio(g, ring)[0])
                          for n, g in (spec.region or [])], lows)

    left_ok, left_shift = positive_on_ray(ld, lows, terms)
    right_ok, right_shift = positive_on_ray(rd, lows, terms)

    # right/rd - left/ld >= 0, multiplied through by the two denominators.
    # Sound only because both were just shown POSITIVE: a negative one would
    # flip the inequality and this certificate would be backwards.
    difference = rn * ld - ln * rd
    strict = spec.relation == "<"
    if strict:
        diff_ok, diff_shift = positive_on_ray(difference, lows, terms)
        used = {}
    else:
        diff_ok, diff_shift, used, _rem = nonneg_on_region(difference, lows,
                                                           terms)

    return {
        "left": (ln, ld), "right": (rn, rd),
        "difference": difference, "shifted": diff_shift,
        "left_positive": left_ok, "right_positive": right_ok,
        "difference_ok": bool(diff_ok),
        "left_shifted": left_shift, "right_shifted": right_shift,
        "multipliers": {k: str(v) for k, v in used.items()},
        "strict": strict,
        "region": {str(n): as_ratio(g, ring)[0].serialize()
                   for n, g in (spec.region or [])},
        "ok": bool(left_ok and right_ok and diff_ok),
    }
