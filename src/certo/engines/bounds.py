"""The `bounds` command: settle a numeric inequality, rigorously.

Precision is the work budget here, exactly as `rlimit` is for z3 and the
conflict budget is for SAT. The search starts at `prec` bits and doubles until
the enclosure is narrow enough to settle the claim -- and if it never is, that
comes back as `resource_exhausted`, which means "this computation did not
settle it" and never "it is false". An enclosure straddling the bound is the
one honest answer a float result cannot give.

The ladder matters more than it looks. Ball arithmetic loses accuracy at
cancellations, so the precision needed is a property of the expression, not of
the answer; guessing it once and printing whatever came out is how people end
up citing a number they have not established.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .. import numerics
from ..certificate import ball_certificate
from ..i18n import t
from ..limits import Limits
from ..status import Result, Status, Verdict


def _ladder(start: int, top: int):
    p = max(32, int(start))
    while p <= top:
        yield p
        p *= 2


def _sha(path) -> str:
    if not path:
        return ""
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def bounds(spec, limits: Limits | None = None, spec_path: str = "") -> Result:
    lim = limits or Limits()
    t0 = time.perf_counter()

    if not callable(getattr(spec, "value", None)):
        return Result("bounds", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      "certo/bounds", 0.0, None,
                      detail=t("engine.bounds.no_value"))

    try:
        backend = numerics.backend_name()
    except numerics.NoBackend as e:
        return Result("bounds", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                      "certo/bounds", 0.0, None, detail=str(e))

    claim = tuple(spec.claim) if spec.claim else None
    lo = hi = None
    settled, prec, tried = None, spec.prec, []

    for prec in _ladder(spec.prec, spec.max_prec):
        try:
            value = spec.value(numerics.Rig(prec, backend))
            lo, hi = value.enclosure()
        except numerics.NotRigorous as e:
            return Result("bounds", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                          "certo/bounds", (time.perf_counter() - t0) * 1000,
                          None, detail=t("engine.bounds.not_rigorous",
                                         detail=str(e)))
        except AttributeError as e:
            return Result("bounds", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                          "certo/bounds", (time.perf_counter() - t0) * 1000,
                          None, detail=t("engine.bounds.no_such_function",
                                         detail=str(e)))
        tried.append(prec)
        settled = numerics.settle(claim, lo, hi)
        if settled is not None or claim is None:
            break
        if (time.perf_counter() - t0) * 1000 > lim.timeout_ms:
            break

    ms = (time.perf_counter() - t0) * 1000
    meta = {"lo": str(lo), "hi": str(hi), "width": "{:.3e}".format(float(hi - lo)),
            "prec": prec, "backend": backend, "ladder": tried,
            "lo_float": float(lo), "hi_float": float(hi)}

    # No claim: the enclosure IS the result, and it is what the certificate
    # asserts. Measuring without deciding is a first-class mode here, the same
    # way `sweep --collect` measures without refuting.
    recorded = claim or ("in", str(lo), str(hi))

    if claim is not None and settled is None:
        return Result("bounds", Status.RESOURCE_EXHAUSTED, Verdict.INCONCLUSIVE,
                      "certo/bounds", ms, None,
                      detail=t("engine.bounds.undecided", prec=prec,
                               lo=float(lo), hi=float(hi)),
                      meta=meta)

    if settled is False:
        return Result("bounds", Status.SAT, Verdict.REFUTED, "certo/bounds",
                      ms, None,
                      detail=t("engine.bounds.refuted",
                               claim=numerics.render(claim),
                               lo=float(lo), hi=float(hi)),
                      meta=meta)

    cert = ball_certificate(
        describe=spec.describe or spec.title, backend=backend, prec=prec,
        lo=lo, hi=hi, claim=recorded, spec_path=spec_path,
        spec_sha256=_sha(spec_path), title=spec.title,
    )
    detail = (t("engine.bounds.proved", claim=numerics.render(claim), prec=prec)
              if claim else
              t("engine.bounds.measured", lo=float(lo), hi=float(hi), prec=prec))
    return Result("bounds", Status.UNSAT, Verdict.PROVED, "certo/bounds", ms,
                  cert, detail=detail, meta=meta)
