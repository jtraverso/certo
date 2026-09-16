"""Exhaustive sweep over an arbitrary finite domain.

`graphsearch.sweep` answers the same question for graphs; this answers it for
anything you can enumerate. The contract is identical on purpose -- the same
six states, the same predicate certificates, the same calibration -- because
the only thing that really changes is where the items come from.

What it cannot do, and says so: certify that the domain is COMPLETE. The list
of items is whatever the spec produced. For graphs, `enumerate` at least
guarantees non-isomorphism; here the domain is the user's to define.
"""
from __future__ import annotations

import time

from .. import exact
from ..certificate import domain_sweep_certificate
from ..i18n import t
from ..limits import Limits
from ..spec import Outcome
from ..status import Result, Status, Verdict
from .graphsearch import _calibration


def _evaluate(spec, item) -> Outcome:
    if spec.predicate is None:
        out = Outcome(ok=True)
    else:
        try:
            r = spec.predicate(item)
        except Exception as e:  # noqa: BLE001
            return Outcome(ok=None, errored=True,
                           detail="{}: {}".format(type(e).__name__, e))
        out = r if isinstance(r, Outcome) else Outcome(ok=bool(r))

    if out.value is None and spec.collect is not None:
        try:
            out.value = spec.collect(item)
        except Exception as e:  # noqa: BLE001
            out.detail = (out.detail + " | collect failed: {}".format(e)).strip(" |")
    return out


def sweep_domain(spec, limits: Limits | None = None,
                 cert_mode: str = "failures") -> Result:
    t0 = time.perf_counter()
    items = spec.enumerate()

    failures, errors, unknowns, certs, values = [], [], [], [], []
    for item in items:
        out = _evaluate(spec, item)
        key = spec.id_of(item)
        if out.value is not None:
            values.append({"g6": key, "value": exact.serialize(out.value)})
        if out.errored:
            errors.append({"g6": key, "detail": out.detail})
            continue
        if out.ok is None:
            unknowns.append({"g6": key, "detail": out.detail})
            continue
        if not out.ok:
            failures.append(key)
            if cert_mode in ("failures", "all"):
                certs.append({"g6": key, "detail": out.detail,
                              "cert": out.cert.to_dict() if out.cert else None})
        elif cert_mode == "all" and out.cert is not None:
            certs.append({"g6": key, "cert": out.cert.to_dict(),
                          "detail": out.detail})

    ms = (time.perf_counter() - t0) * 1000
    counts = {
        "enumerated": len(items), "in_family": len(items),
        "examined": len(items) - len(errors) - len(unknowns),
        "failures": len(failures), "errors": len(errors),
        "inconclusive": len(unknowns),
    }
    calib = _calibration(values, spec.worst)
    uncertified = sum(1 for c in certs if c["cert"] is None)

    cert = domain_sweep_certificate(
        ids=[spec.id_of(i) for i in items], entries=certs, mode=cert_mode,
        counts=counts, values=values,
        stats=calib["stats"] if calib else None, title=spec.title,
    )

    described = []
    if spec.describe:
        for item in items:
            if spec.id_of(item) in failures[:5]:
                try:
                    described.append(spec.describe(item))
                except Exception as e:  # noqa: BLE001
                    described.append("describe failed: {}".format(e))

    base = {**counts, "counterexamples": failures[:50], "describe": described,
            "errors_detail": errors[:5], "inconclusive_detail": unknowns[:5],
            "predicate_certificates": len(certs) - uncertified,
            "predicate_uncertified": uncertified}
    if calib:
        base["calibration"] = calib

    if spec.predicate is None and calib:
        return Result("sweep", Status.SAT, Verdict.SATISFIABLE, "certo/domain",
                      ms, cert,
                      detail=t("engine.sweep.calibration", count=len(items),
                               summary=calib["summary"]), meta=base)

    if failures:
        note = (t("engine.sweep.refuted.note", n=len(errors) + len(unknowns))
                if errors or unknowns else "")
        return Result("sweep", Status.SAT, Verdict.REFUTED, "certo/domain", ms,
                      cert, detail=t("engine.sweep.refuted",
                                     failures=len(failures),
                                     examined=counts["examined"], note=note),
                      meta=base)

    if errors or unknowns:
        return Result("sweep", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                      "certo/domain", ms, cert,
                      detail=t("engine.sweep.partial",
                               examined=counts["examined"],
                               n=len(errors) + len(unknowns)), meta=base)

    return Result("sweep", Status.UNSAT, Verdict.PROVED, "certo/domain", ms,
                  cert, detail=t("engine.domain.proved", count=len(items)),
                  meta=base)
