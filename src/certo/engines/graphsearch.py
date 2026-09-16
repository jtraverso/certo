"""Motor de enumeracion exhaustiva: enum y sweep.

El certificado de `sweep` cubre DOS cosas distintas y conviene no mezclarlas:

  1. QUE FAMILIA se examino -- eso lo certifica la parte `graph_set`;
  2. QUE EL PREDICADO se evaluo bien en cada grafo -- eso NO lo puede
     certificar el motor, porque el predicado es codigo del usuario.

Si tu predicado resuelve un LP en punto flotante, un barrido sin (2) no es
citable por mucho que (1) sea impecable. Por eso el predicado puede devolver
un `Outcome` con su propio certificado y `sweep` los agrega.

Los seis estados se propagan: un predicado que revienta o no concluye en un
grafo ya no tumba el barrido entero, pero impide afirmar "se cumple en todos".
Un contraejemplo, en cambio, refuta aunque otros grafos hayan fallado.
"""
from __future__ import annotations

import time

from .. import exact
from ..certificate import graph_set_certificate, sweep_certificate
from ..i18n import t
from ..graphs import enumerate_graphs, filter_name
from ..limits import Limits
from ..spec import Outcome
from ..status import Result, Status, Verdict


def enum(n, filters=None, limits: Limits | None = None, use_geng=True) -> Result:
    t0 = time.perf_counter()
    graphs, engine, total = enumerate_graphs(n, filters, use_geng=use_geng)
    g6 = [g.to_graph6() for g in graphs]
    cert = graph_set_certificate(n, [filter_name(f) for f in (filters or [])], g6)
    ms = (time.perf_counter() - t0) * 1000
    return Result(
        "enum", Status.SAT, Verdict.SATISFIABLE, engine, ms, cert,
        detail=t("engine.enum.summary", count=len(g6), n=n,
                 filtered=t("engine.enum.filtered", total=total,
                            filters=", ".join(filter_name(f) for f in filters))
                 if filters else ""),
        meta={"count": len(g6), "enumerated": total, "n": n,
              "filters": list(filters or [])},
    )


def _evaluate(spec, g) -> Outcome:
    """Normaliza lo que devuelva el predicado a un Outcome, y recolecta."""
    if spec.predicate is None:
        out = Outcome(ok=True)          # modo calibracion pura
    else:
        try:
            r = spec.predicate(g)
        except Exception as e:  # noqa: BLE001
            return Outcome(ok=None, detail="{}: {}".format(type(e).__name__, e),
                           errored=True)
        out = r if isinstance(r, Outcome) else Outcome(ok=bool(r))

    if out.value is None and spec.collect is not None:
        try:
            out.value = spec.collect(g)
        except Exception as e:  # noqa: BLE001
            out.detail = (out.detail + " | collect fallo: {}".format(e)).strip(" |")
    return out


def sweep(spec, limits: Limits | None = None, use_geng=True,
          cert_mode: str = "failures") -> Result:
    """Corre el predicado sobre toda la familia. Esto es validar exhaustivamente.

    cert_mode: 'failures' (solo los contraejemplos), 'all' (todos, caro),
               'none' (ninguno).
    """
    t0 = time.perf_counter()
    graphs, engine, total = enumerate_graphs(spec.n, spec.filters, use_geng=use_geng)

    failures, errors, unknowns, certs, values = [], [], [], [], []
    for g in graphs:
        out = _evaluate(spec, g)
        g6 = g.to_graph6()
        if out.value is not None:
            values.append({"g6": g6, "value": exact.serialize(out.value)})
        if out.errored:
            errors.append({"g6": g6, "detail": out.detail})
            continue
        if out.ok is None:
            unknowns.append({"g6": g6, "detail": out.detail})
            continue
        if not out.ok:
            failures.append(g)
            if cert_mode in ("failures", "all") and out.cert is not None:
                certs.append({"g6": g6, "cert": out.cert.to_dict(),
                              "detail": out.detail})
            elif cert_mode in ("failures", "all"):
                certs.append({"g6": g6, "cert": None, "detail": out.detail})
        elif cert_mode == "all" and out.cert is not None:
            certs.append({"g6": g6, "cert": out.cert.to_dict(),
                          "detail": out.detail})

    ms = (time.perf_counter() - t0) * 1000
    counts = {
        "enumerated": total,
        "in_family": len(graphs),
        "examined": len(graphs) - len(errors) - len(unknowns),
        "failures": len(failures),
        "errors": len(errors),
        "inconclusive": len(unknowns),
    }
    family_g6 = [g.to_graph6() for g in graphs]
    uncertified = sum(1 for c in certs if c["cert"] is None)

    calib = _calibration(values, spec.worst)
    cert = sweep_certificate(
        n=spec.n, filters=[filter_name(f) for f in (spec.filters or [])],
        family_g6=family_g6,
        entries=certs, mode=cert_mode, counts=counts,
        values=values, stats=calib["stats"] if calib else None,
    )

    base = {**counts, "counterexamples": [g.to_graph6() for g in failures],
            "describe": _describe(spec, failures[:5]),
            "errors_detail": errors[:5], "inconclusive_detail": unknowns[:5],
            "predicate_certificates": len(certs) - uncertified,
            "predicate_uncertified": uncertified}
    if calib:
        base["calibration"] = calib

    # Calibracion pura: sin predicado no hay nada que refutar, solo medir.
    if spec.predicate is None and calib:
        return Result(
            "sweep", Status.SAT, Verdict.SATISFIABLE, engine, ms, cert,
            detail=t("engine.sweep.calibration", count=len(graphs),
                     summary=calib["summary"]),
            meta=base)

    # Un contraejemplo refuta aunque otros grafos hayan fallado.
    if failures:
        note = ""
        if errors or unknowns:
            note = t("engine.sweep.refuted.note", n=len(errors) + len(unknowns))
        return Result(
            "sweep", Status.SAT, Verdict.REFUTED, engine, ms, cert,
            detail=t("engine.sweep.refuted", failures=len(failures),
                     examined=counts["examined"], note=note),
            meta=base)

    if errors or unknowns:
        return Result(
            "sweep", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE, engine, ms, cert,
            detail=t("engine.sweep.partial", examined=counts["examined"],
                     n=len(errors) + len(unknowns)),
            meta=base)

    return Result(
        "sweep", Status.UNSAT, Verdict.PROVED, engine, ms, cert,
        detail=t("engine.sweep.proved", count=len(graphs), n=spec.n),
        meta=base)


def _calibration(values, worst="min"):
    """min, max, media y los extremos CON su grafo.

    Refutar dice que la afirmacion es falsa; calibrar dice cuanto y donde. Lo
    segundo es lo que se cita.
    """
    if not values:
        return None
    st = exact.stats([v["value"] for v in values])
    ordered = sorted(values, key=lambda v: exact.to_fraction(v["value"]),
                     reverse=(worst == "max"))
    arg_worst, arg_best = ordered[0], ordered[-1]
    return {
        "count": st["count"],
        "min": exact.fmt(st["min"]), "max": exact.fmt(st["max"]),
        "mean": exact.fmt(st["mean"]),
        "worst_sense": worst,
        "worst": [{"g6": v["g6"], "value": exact.fmt(v["value"])}
                  for v in ordered[:5]],
        "argworst": arg_worst["g6"], "argbest": arg_best["g6"],
        "summary": t("engine.sweep.summary",
                     min=exact.fmt(st["min"]),
                     argmin=arg_worst["g6"] if worst == "min" else arg_best["g6"],
                     max=exact.fmt(st["max"]),
                     argmax=arg_worst["g6"] if worst == "max" else arg_best["g6"],
                     mean=exact.fmt(st["mean"])),
        "stats": {k: exact.serialize(v) for k, v in st.items() if k != "count"},
    }


def _describe(spec, graphs):
    if spec.describe is None:
        return [str(g) for g in graphs]
    out = []
    for g in graphs:
        try:
            out.append(spec.describe(g))
        except Exception as e:  # noqa: BLE001
            out.append("describe fallo: {}".format(e))
    return out


def sweep_range(spec, lo: int, hi: int, limits: Limits | None = None,
                stop_on_first: bool = False, cert_mode: str = "failures",
                use_geng: bool = True, on_size=None) -> Result:
    """From which n does it start failing? bisect applied to the order.

    Lives here rather than in the CLI so the MCP server gets it too: a mode
    only one front end can reach is a mode half the users never see.
    """
    from ..certificate import sweep_range_certificate

    t0 = time.perf_counter()
    entries, first, stopped = [], None, False
    original_n = spec.n
    try:
        for n in range(lo, hi + 1):
            spec.n = n
            res = sweep(spec, limits, use_geng=use_geng, cert_mode=cert_mode)
            row = {"n": n, "verdict": res.verdict.value, "detail": res.detail,
                   "cert": res.certificate.to_dict() if res.certificate else None}
            entries.append(row)
            if on_size is not None:
                on_size(row)
            if res.verdict is Verdict.REFUTED and first is None:
                first = n
                if stop_on_first:
                    stopped = True
                    break
    finally:
        spec.n = original_n

    cert = sweep_range_certificate(entries, first, stopped)
    ms = (time.perf_counter() - t0) * 1000
    meta = {"sizes": [e["n"] for e in entries], "first_failure": first,
            "stopped_early": stopped,
            "verdicts": {e["n"]: e["verdict"] for e in entries}}
    if first is not None:
        return Result("sweep", Status.SAT, Verdict.REFUTED, "certo/range", ms,
                      cert, detail=t("engine.range.first", lo=lo, hi=hi,
                                     first=first), meta=meta)
    return Result("sweep", Status.UNSAT, Verdict.PROVED, "certo/range", ms,
                  cert, detail=t("engine.range.none", lo=lo, hi=hi), meta=meta)
