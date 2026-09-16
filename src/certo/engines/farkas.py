"""The `farkas` command: linarith and nlinarith, with an exact certificate.

`prove` tells you whether something is true; this tells you WHY in a form a
referee can check by hand and Lean can consume. The whole content of the
certificate is a list of non-negative rationals.
"""
from __future__ import annotations

import time
from fractions import Fraction

from .. import exact, linarith
from ..certificate import farkas_certificate
from ..i18n import t
from ..limits import Limits
from ..status import Result, Status, Verdict


def _search(rows, limits):
    """The LP behind linarith: lambda >= 0 that cancels every monomial.

    Two closing conditions, and they are not interchangeable. With a strict
    row carrying weight, the constant only has to be >= 0 (the contradiction
    is `0 < 0`). With no strict row it has to be strictly positive, and 1 is
    as good as any because the system is scale-free.
    """
    from ..engines import lp
    from ..spec import LPSpec

    monomials = sorted({m for _, p, _ in rows for m in p if m != linarith.CONST})
    strict = [i for i, (_, _, rel) in enumerate(rows) if rel == "<"]

    def build(with_strict):
        s = LPSpec(sense="max", title="farkas")
        for i, _ in enumerate(rows):
            s.variable("L{}".format(i))
        s.objective({"L{}".format(i): 0 for i in range(len(rows))})
        for m in monomials:
            s.constraint({"L{}".format(i): p.get(m, 0)
                          for i, (_, p, _) in enumerate(rows)}, "==", 0,
                         name="cancel_" + ("_".join(m)))
        consts = {"L{}".format(i): p.get(linarith.CONST, 0)
                  for i, (_, p, _) in enumerate(rows)}
        if with_strict:
            s.constraint(consts, ">=", 0, name="const_nonneg")
            s.constraint({"L{}".format(i): 1 for i in strict}, ">=", 1,
                         name="strict_active")
        else:
            s.constraint(consts, ">=", 1, name="const_positive")
        return s

    for with_strict in ([True, False] if strict else [False]):
        res = lp.opt(build(with_strict), limits)
        if res.verdict is not Verdict.SATISFIABLE:
            continue
        sol = res.meta.get("solution") or {}
        lams = [Fraction(str(sol.get("L{}".format(i), 0)))
                for i in range(len(rows))]
        ok, const, strict_used = linarith.is_contradiction(rows, lams)
        if ok:
            return lams, const, strict_used, res.meta.get("exact", False)
    return None, None, None, False


def farkas(spec, limits: Limits | None = None, nonlinear: bool = False,
           spec_path: str = "") -> Result:
    lim = limits or Limits()
    t0 = time.perf_counter()

    try:
        rows = linarith.rows_of(spec)
    except linarith.NotPolynomial as e:
        return Result("farkas", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      "certo/farkas", (time.perf_counter() - t0) * 1000, None,
                      detail=t("engine.farkas.not_polynomial", detail=str(e)))

    base, origin = len(rows), {}
    if nonlinear:
        extra, origin = linarith.products(rows)
        rows = rows + extra

    degree = max((len(m) for _, p, _ in rows for m in p), default=0)
    if degree > 1 and not nonlinear:
        return Result("farkas", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      "certo/farkas", (time.perf_counter() - t0) * 1000, None,
                      detail=t("engine.farkas.nonlinear_needed"))

    lams, const, strict, is_exact = _search(rows, lim)
    ms = (time.perf_counter() - t0) * 1000

    if lams is None:
        return Result("farkas", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                      "certo/farkas", ms, None,
                      detail=t("engine.farkas.none",
                               mode=t("engine.farkas.nonlinear" if nonlinear
                                      else "engine.farkas.linear")),
                      meta={"rows": len(rows), "degree": degree})
    if not is_exact:
        return Result("farkas", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                      "certo/farkas", ms, None,
                      detail=t("engine.farkas.inexact"))

    used = [(rows[i][0], exact.serialize(l)) for i, l in enumerate(lams) if l]
    vacuous = _vacuous(rows, lim)
    cert = farkas_certificate(
        rows=linarith.serialize_rows(rows),
        multipliers=[exact.serialize(l) for l in lams],
        constant=exact.serialize(const), strict=strict,
        nonlinear=nonlinear, base_rows=base, sorts=_sorts(spec),
        vacuous=vacuous, derived=origin, spec_path=str(spec_path))

    return Result(
        "farkas", Status.UNSAT, Verdict.PROVED, "certo/farkas", ms, cert,
        detail=(t("engine.farkas.vacuous") if vacuous else
                t("engine.farkas.found", n=len(used),
                  mode=t("engine.farkas.nonlinear" if nonlinear
                         else "engine.farkas.linear"))),
        meta={"multipliers": dict(used), "rows": len(rows), "degree": degree,
              "vacuous": vacuous,
              "constant": exact.serialize(const), "strict": strict,
              "hint": _lean_hint(spec, used, nonlinear)},
    )


def _vacuous(rows, limits) -> bool:
    """Do the hypotheses close the system WITHOUT the negated goal?

    Reading it off the multipliers does not work: the LP is free to give the
    goal row a non-zero weight even when it is not needed, and often does. So
    the question has to be asked directly -- drop the goal row and search
    again. One extra LP, only on the successful path.
    """
    # Every row DERIVED from the goal has to go too, not just the goal row:
    # in nonlinear mode the products are named "h*__goal__" and keeping one
    # would smuggle the goal back in and report vacuity that is not there.
    rest = [r for r in rows if "__goal__" not in r[0]]
    if not rest:
        return False
    lams, _, _, exact_ok = _search(rest, limits)
    return lams is not None and exact_ok


def _sorts(spec) -> dict:
    """Which variables are integers. A row rebuilt in the wrong sort is a
    different variable, so `compose` needs this to re-read the rows."""
    from .. import z3util

    exprs = [f for _, f in spec.assumptions]
    if spec.goal is not None:
        exprs.append(spec.goal)
    out = {}
    for c in z3util.free_consts(*exprs):
        try:
            out[str(c)] = z3util.sort_name(c)
        except ValueError:
            pass
    return out


def _lean_hint(spec, used, nonlinear) -> str:
    """The Lean one-liner this certificate corresponds to.

    The multipliers are not needed there -- `linarith` will rediscover them --
    but which hypotheses to hand it is exactly what this found out.
    """
    names = [n for n, _ in used if not n.startswith(("__goal__", "sq_"))
             and "*" not in n and "^" not in n]
    names = [n[:-4] if n.endswith("_rev") else n for n in names]
    seen, ordered = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    tactic = "nlinarith" if nonlinear else "linarith"
    return "{} [{}]".format(tactic, ", ".join(ordered)) if ordered else tactic
