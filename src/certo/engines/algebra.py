"""Engines for polynomial ideals, sums of squares, and integers.

Three commands that have nothing to do with SMT, and one shape in common with
everything else here: a search that may be as clever or as numeric as it
likes, and a certificate that is exact and checkable without it.

  parametric A bound that holds for EVERY value of a parameter, not the ones
          you tried. Weak duality, symbolically: `y >= 0` with
          `A(p)^T y >= c(p)` bounds the optimum for all p at once, and each
          inequality is certified on a ray by a shift.

  eliminate  The resultant of two polynomials in one variable, with the
          Bezout identity `Res = A f + B g` attached. Turns "do these two
          share a root in t" into a condition on the other variables.

  ideal   Groebner cofactors. `1 = sum h_i g_i` refutes a polynomial system
          outright; `f = sum h_i g_i` says f follows from it. Either way the
          check is expanding a product.
  sos     A sum of squares, searched for in floating point and then rounded,
          re-projected and re-verified in exact rationals. The floats never
          reach the certificate.
  number  A Pratt primality tree, or a factorisation whose factors carry one.
          Checked with modular exponentiation alone.
"""
from __future__ import annotations

import time

from ..certificate import (cover_certificate, ideal_certificate,
                           number_certificate, parametric_bound_certificate,
                           resultant_certificate, sos_certificate)
from ..i18n import t
from ..limits import Limits
from ..polynomials import Budget, Poly, cofactors
from ..status import Result, Status, Verdict

ENGINE_IDEAL = "certo/groebner"
ENGINE_ELIM = "certo/sylvester"
ENGINE_PARAM = "certo/weak-duality"
ENGINE_COVER = "certo/counting"
ENGINE_SOS = "certo/sos"
ENGINE_NUM = "certo/pratt"


def _poly(expr, variables):
    """A spec's term, whether it arrived as a Poly or as a z3 expression."""
    if isinstance(expr, Poly):
        return expr
    return Poly.from_z3(expr, variables)


# ---------------------------------------------------------------------------


def cover(spec, limits: Limits | None = None, spec_path: str = "") -> Result:
    """Is this an exact cover, and how many parts does it use?"""
    from ..cover import NotACover, check, clique_parts

    t0 = time.perf_counter()
    universe = [u for u in spec.universe]
    report = None
    try:
        if spec.cliques:
            parts, report = clique_parts(universe, spec.parts, spec.max_size)
        else:
            parts = [list(part) for part in spec.parts]
        out = check(universe, parts, exact=spec.exact)
    except NotACover as e:
        return Result("cover", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_COVER, (time.perf_counter() - t0) * 1000, None,
                      detail=str(e))

    ms = (time.perf_counter() - t0) * 1000
    meta = {"parts": out["parts"], "universe": out["universe"],
            "missed": len(out["missed"]), "doubled": len(out["doubled"])}

    if not out["ok"]:
        # Not a cover. No certificate, and the reason is the useful part.
        if out["foreign"]:
            detail = t("engine.cover.foreign", n=len(out["foreign"]))
        elif out["missed"]:
            detail = t("engine.cover.missed", n=len(out["missed"]),
                       names=", ".join(map(str, out["missed"][:4])))
        else:
            detail = t("engine.cover.doubled", n=len(out["doubled"]),
                       names=", ".join(map(str, out["doubled"][:4])))
        return Result("cover", Status.SAT, Verdict.REFUTED, ENGINE_COVER, ms,
                      None, detail=detail, meta=meta)

    cert = cover_certificate(
        universe=[list(u) if isinstance(u, (tuple, list)) else u
                  for u in universe],
        parts=[[list(e) if isinstance(e, (tuple, list)) else e for e in part]
               for part in parts],
        exact=spec.exact, cliques=spec.cliques,
        multiplicities={}, part_report=report, max_size=spec.max_size,
        title=spec.title,
    ).stamp(spec_path or None)

    return Result("cover", Status.UNSAT, Verdict.PROVED, ENGINE_COVER, ms,
                  cert,
                  detail=t("engine.cover.proved" if spec.exact
                           else "engine.cover.proved_atleast",
                           parts=out["parts"], n=out["universe"]),
                  meta=meta)


def parametric(spec, limits: Limits | None = None,
               spec_path: str = "") -> Result:
    """`opt(p) <= b(p).y` for every p at or above the floor, or why not."""
    from ..linarith import NotPolynomial
    from ..parametric import NotParametric, certify

    t0 = time.perf_counter()

    if spec.sense != "max":
        return Result("parametric", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_PARAM, 0.0, None,
                      detail=t("engine.param.max_only", sense=spec.sense))
    bad_sense = [n for n, _, sense, _ in spec.constraints if sense != "<="]
    if bad_sense:
        return Result("parametric", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_PARAM, 0.0, None,
                      detail=t("engine.param.le_only",
                               names=", ".join(map(str, bad_sense[:4]))))
    try:
        out = certify(spec)
    except (NotParametric, NotPolynomial) as e:
        return Result("parametric", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_PARAM, 0.0, None, detail=str(e))

    ms = (time.perf_counter() - t0) * 1000
    floor = ", ".join("{} >= {}".format(k, v)
                      for k, v in spec.parameters.items())

    if not out["ok"]:
        # No certificate. The shift is sufficient and not necessary, so a
        # failure is "not established by this route" and never "false" -- and
        # emitting a certificate for it would be the overclaim this whole
        # project exists to avoid.
        if out["negative_dual"]:
            detail = t("engine.param.negative",
                       names=", ".join(out["negative_dual"][:4]))
        else:
            detail = t("engine.param.not_shown",
                       names=", ".join(out["failed"][:4]), floor=floor)
        return Result("parametric", Status.UNKNOWN_SOLVER,
                      Verdict.INCONCLUSIVE, ENGINE_PARAM, ms, None,
                      detail=detail,
                      meta={"failed_columns": out["failed"]})

    cert = parametric_bound_certificate(
        parameters=dict(spec.parameters),
        variables=out["variables"],
        objective={v: _ser(spec, c) for v, c in spec.objective.items()},
        constraints=[[str(n), {v: _ser(spec, c) for v, c in row.items()},
                      sense, _ser(spec, rhs)]
                     for n, row, sense, rhs in spec.constraints],
        dual={str(n): str(v) for n, v in spec.dual.items()},
        bound=out["bound"].serialize(),
        rows=out["rows"],
        title=spec.title,
    ).stamp(spec_path or None)

    return Result("parametric", Status.UNSAT, Verdict.PROVED, ENGINE_PARAM,
                  ms, cert,
                  detail=t("engine.param.proved", bound=str(out["bound"]),
                           floor=floor),
                  meta={"bound": str(out["bound"]), "floor": floor,
                        "columns": len(out["variables"])})


def _ser(spec, coef):
    """A coefficient as a serialised Poly over the parameter ring."""
    from ..polynomials import Poly

    ring = tuple(spec.parameters)
    if isinstance(coef, Poly):
        return coef.serialize()
    if isinstance(coef, (int, float)) or hasattr(coef, "numerator"):
        return Poly.const(ring, coef).serialize()
    return Poly.from_z3(coef, ring).serialize()


def eliminate(spec, limits: Limits | None = None,
              spec_path: str = "") -> Result:
    """Get rid of one variable, and say what has to hold without it."""
    from ..linarith import NotPolynomial
    from ..resultants import NotEliminable, eliminate as _elim

    lim = limits or Limits()
    t0 = time.perf_counter()
    variables = tuple(spec.variables)

    if len(spec.equations) != 2:
        return Result("eliminate", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_ELIM, 0.0, None,
                      detail=t("engine.eliminate.two_only",
                               n=len(spec.equations)))
    try:
        f, g = (_poly(e, variables) for e in spec.equations)
    except NotPolynomial as e:
        return Result("eliminate", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_ELIM, 0.0, None,
                      detail=t("engine.ideal.not_polynomial", detail=str(e)))

    try:
        out = _elim(f, g, spec.eliminate)
    except NotEliminable as e:
        return Result("eliminate", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_ELIM, 0.0, None, detail=str(e))
    except Budget as e:
        return Result("eliminate", Status.RESOURCE_EXHAUSTED,
                      Verdict.INCONCLUSIVE, ENGINE_ELIM, 0.0, None,
                      detail=str(e))

    res = out["resultant"]
    ms = (time.perf_counter() - t0) * 1000
    cert = resultant_certificate(
        variables=variables, eliminated=spec.eliminate,
        f=f.serialize(), g=g.serialize(), resultant=res.serialize(),
        A=out["A"].serialize(), B=out["B"].serialize(),
        deg_f=out["deg_f"], deg_g=out["deg_g"],
        lead_f=out["lead_f"].serialize(), lead_g=out["lead_g"].serialize(),
        lead_f_constant=out["lead_f_constant"],
        lead_g_constant=out["lead_g_constant"],
        title=spec.title,
    ).stamp(spec_path or None)

    meta = {"resultant": str(res) or "0",
            "degrees": "{} and {} in {}".format(out["deg_f"], out["deg_g"],
                                                spec.eliminate)}

    # A non-zero CONSTANT resultant is conclusive in the useful direction:
    # no common root, for any values of anything, over any extension field.
    if out["constant"] and res:
        return Result("eliminate", Status.UNSAT, Verdict.REFUTED, ENGINE_ELIM,
                      ms, cert,
                      detail=t("engine.eliminate.never", var=spec.eliminate,
                               value=str(res)),
                      meta=dict(meta, case="no_common_root"))

    if out["identically_zero"]:
        return Result("eliminate", Status.SAT, Verdict.SATISFIABLE,
                      ENGINE_ELIM, ms, cert,
                      detail=t("engine.eliminate.always", var=spec.eliminate),
                      meta=dict(meta, case="common_factor"))

    return Result("eliminate", Status.SAT, Verdict.SATISFIABLE, ENGINE_ELIM,
                  ms, cert,
                  detail=t("engine.eliminate.condition", var=spec.eliminate,
                           res=str(res)),
                  meta=dict(meta, case="condition"))


def ideal(spec, limits: Limits | None = None, spec_path: str = "") -> Result:
    from ..linarith import NotPolynomial

    lim = limits or Limits()
    t0 = time.perf_counter()
    variables = tuple(spec.variables)

    try:
        gs = [_poly(e, variables) for e in spec.equations]
        claim = None if spec.claim is None else _poly(spec.claim, variables)
    except NotPolynomial as e:
        return Result("ideal", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_IDEAL, 0.0, None,
                      detail=t("engine.ideal.not_polynomial", detail=str(e)))

    target = claim if claim is not None else Poly.const(variables, 1)
    try:
        hs, in_ideal = cofactors(target, gs, max_pairs=spec.max_pairs)
    except Budget as e:
        return Result("ideal", Status.RESOURCE_EXHAUSTED, Verdict.INCONCLUSIVE,
                      ENGINE_IDEAL, (time.perf_counter() - t0) * 1000, None,
                      detail=t("engine.ideal.budget", detail=str(e)))

    ms = (time.perf_counter() - t0) * 1000
    if not in_ideal:
        # Conclusive, not a failure to find: Groebner decides membership.
        detail = (t("engine.ideal.consistent") if claim is None
                  else t("engine.ideal.not_member"))
        return Result("ideal", Status.SAT, Verdict.REFUTED, ENGINE_IDEAL, ms,
                      None, detail=detail)

    cert = ideal_certificate(
        variables=variables,
        equations=[g.serialize() for g in gs],
        claim=None if claim is None else claim.serialize(),
        cofactors=[h.serialize() for h in hs],
        inconsistent=claim is None, title=spec.title,
    ).stamp(spec_path or None)

    used = [str(h) for h in hs if h]
    return Result(
        "ideal", Status.UNSAT, Verdict.PROVED, ENGINE_IDEAL, ms, cert,
        detail=(t("engine.ideal.inconsistent") if claim is None
                else t("engine.ideal.member", n=len(used))),
        meta={"cofactors": {str(i): str(h) for i, h in enumerate(hs) if h},
              "equations": len(gs), "degree": target.degree},
    )


# ---------------------------------------------------------------------------


def sos(spec, limits: Limits | None = None, spec_path: str = "") -> Result:
    from .. import sos as sosmod
    from ..linarith import NotPolynomial

    t0 = time.perf_counter()
    variables = tuple(spec.variables)
    try:
        p = _poly(spec.poly, variables)
    except NotPolynomial as e:
        return Result("sos", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_SOS, 0.0, None,
                      detail=t("engine.ideal.not_polynomial", detail=str(e)))

    try:
        found, why = sosmod.certify(p, spec.half_degree, spec.iterations)
    except sosmod.NoBackend as e:
        return Result("sos", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_SOS, 0.0, None,
                      detail=t("engine.sos.no_backend", detail=str(e)))

    ms = (time.perf_counter() - t0) * 1000
    if found is None:
        # Never REFUTED: not every non-negative polynomial is a sum of squares.
        return Result("sos", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                      ENGINE_SOS, ms, None,
                      detail=t("engine.sos.none", detail=why))

    terms, basis, denom = found
    cert = sos_certificate(
        variables=variables, poly=p.serialize(),
        terms=sosmod.serialize(terms), basis_size=len(basis), denom=denom,
        title=spec.title,
    ).stamp(spec_path or None)
    return Result(
        "sos", Status.UNSAT, Verdict.PROVED, ENGINE_SOS, ms, cert,
        detail=t("engine.sos.found", n=len(terms), denom=denom),
        meta={"squares": ["{} * ({})^2".format(d, q) for d, q in terms],
              "basis_size": len(basis), "denominator": denom},
    )


# ---------------------------------------------------------------------------


def number(spec, limits: Limits | None = None, spec_path: str = "") -> Result:
    from .. import numbers

    t0 = time.perf_counter()
    n = int(spec.n)

    if spec.question not in ("prime", "factor"):
        return Result("number", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      ENGINE_NUM, 0.0, None,
                      detail=t("engine.number.bad_question", got=spec.question))

    if spec.question == "factor":
        tree = numbers.factorisation(n)
        checks = numbers.verify_factorisation(tree)
        ms = (time.perf_counter() - t0) * 1000
        cert = number_certificate("factor", tree, spec.title).stamp(
            spec_path or None)
        factors = " * ".join("{}^{}".format(f["p"], f["e"])
                             for f in tree["factors"]) or "1"
        return Result("number", Status.UNSAT, Verdict.PROVED, ENGINE_NUM, ms,
                      cert, detail=t("engine.number.factored", n=n,
                                     factors=factors),
                      meta={"factors": factors, "checks": len(checks)})

    try:
        tree = numbers.pratt(n)
    except (ValueError, RuntimeError) as e:
        # A composite is a real answer, not a failure to find one.
        return Result("number", Status.SAT, Verdict.REFUTED, ENGINE_NUM,
                      (time.perf_counter() - t0) * 1000, None,
                      detail=t("engine.number.composite", n=n, detail=str(e)))

    checks = numbers.verify_pratt(tree)
    ms = (time.perf_counter() - t0) * 1000
    cert = number_certificate("prime", tree, spec.title).stamp(spec_path or None)
    return Result("number", Status.UNSAT, Verdict.PROVED, ENGINE_NUM, ms, cert,
                  detail=t("engine.number.prime", n=n, checks=len(checks)),
                  meta={"witness": tree.get("witness"), "checks": len(checks),
                        "nodes": _nodes(tree), "depth": _depth(tree)})


def _nodes(tree) -> int:
    return 1 + sum(_nodes(f["cert"]) for f in tree.get("factors", []))


def _depth(tree) -> int:
    return 1 + max((_depth(f["cert"]) for f in tree.get("factors", [])),
                   default=0)
