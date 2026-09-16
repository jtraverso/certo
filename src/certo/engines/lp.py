"""Motor LP/ILP.

El certificado es el DUAL, no la solucion: una solucion primal solo demuestra
que el optimo es >= algo; el dual demuestra que es <=. Juntos, optimalidad.

MODO EXACTO (por defecto). CBC trabaja en punto flotante y devuelve
10.66666656003499 donde la respuesta es 32/3 -- error de 2.5e-7, que es su
tolerancia. Con eso no se puede afirmar igualdad primal-dual ni citar una
constante. Asi que:

    resolver en flotante -> reconstruir racionales -> VERIFICAR en Fraction

y se acepta solo si la verificacion exacta pasa. Una reconstruccion mala no
verifica y se rechaza, asi que la heuristica del paso 2 no compromete nada.
El certificado resultante no depende de confiar en CBC.

Para ILP no hay dual. Se resuelve el entero para el primal y ademas la
relajacion continua, cuyo dual certifica la COTA superior. Queda dicho en el
resultado en vez de fingir optimalidad certificada.
"""
from __future__ import annotations

import time
from fractions import Fraction

import pulp

from .. import exact
from ..certificate import lp_dual_certificate
from ..i18n import t
from ..limits import Limits
from ..status import Result, Status, Verdict

ENGINE = "pulp/CBC"


def _build(spec, A, b, c, cons_names, integer):
    cat = pulp.LpInteger if integer else pulp.LpContinuous
    name = "".join(ch if ch.isalnum() or ch in "._-" else "_"
                   for ch in (spec.title or "opt"))
    prob = pulp.LpProblem(name, pulp.LpMaximize)
    x = {v: pulp.LpVariable(v, lowBound=0, cat=cat) for v in spec.var_names}
    prob += pulp.lpSum(float(c[j]) * x[v] for j, v in enumerate(spec.var_names))
    for i, row in enumerate(A):
        prob += (
            pulp.lpSum(float(row[j]) * x[v] for j, v in enumerate(spec.var_names))
            <= float(b[i]),
            cons_names[i],
        )
    return prob, x


def _duals(prob, cons_names):
    out = []
    for name in cons_names:
        con = prob.constraints.get(name)
        pi = getattr(con, "pi", None) if con is not None else None
        out.append(0.0 if pi is None else float(pi))
    return out


def opt(spec, limits: Limits | None = None, use_exact: bool = True) -> Result:
    lim = limits or Limits()
    t0 = time.perf_counter()

    for v, (lo, hi) in spec.bounds.items():
        if lo is not None and lo < 0:
            raise ValueError(t("engine.opt.negative_bound", var=v))

    A, b, c, cons_names = spec.as_leq_system()
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=max(1, lim.timeout_ms // 1000))

    prob, xvars = _build(spec, A, b, c, cons_names, spec.integer)
    code = prob.solve(solver)
    st_name = pulp.LpStatus[code]
    ms = lambda: (time.perf_counter() - t0) * 1000  # noqa: E731

    if st_name == "Infeasible":
        return Result("opt", Status.UNSAT, Verdict.UNSATISFIABLE, ENGINE, ms(), None,
                      detail=t("engine.opt.infeasible"))
    if st_name != "Optimal":
        return Result("opt", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE, ENGINE,
                      ms(), None, detail=t("engine.opt.cbc", status=st_name))

    sol_float = [float(xvars[v].value() or 0.0) for v in spec.var_names]

    # El dual siempre sale de la relajacion continua: en ILP no hay dual.
    if spec.integer:
        rprob, rx = _build(spec, A, b, c, cons_names, False)
        rprob.solve(solver)
        dual_src = rprob
        relax_x = [float(rx[v].value() or 0.0) for v in spec.var_names]
    else:
        dual_src, relax_x = prob, sol_float
    dual_float = _duals(dual_src, cons_names)

    # ---- certificacion exacta ------------------------------------------
    exact_ok, x_ex, y_ex, rep, denom = False, None, None, None, None
    if use_exact:
        # CBC no fija el signo del dual; deja que la comprobacion exacta decida.
        for cand in (dual_float, [-v for v in dual_float], [abs(v) for v in dual_float]):
            x_ex, y_ex, rep, denom = exact.certify(A, b, c, relax_x, cand)
            if x_ex is not None:
                exact_ok = True
                break

    if exact_ok:
        objective_ex = rep["objective"]
        if spec.sense == "min":
            objective_ex = -objective_ex
        cert = lp_dual_certificate(
            sense=spec.sense, objective=exact.serialize(rep["objective"]),
            dual=exact.serialize_all(y_ex), primal=exact.serialize_all(x_ex),
            A=[exact.serialize_all(r) for r in A], b=exact.serialize_all(b),
            c=exact.serialize_all(c), names=cons_names,
            var_names=list(spec.var_names), is_exact=True,
        )
        detail = t("engine.opt.exact", value=exact.serialize(objective_ex),
                   denom=denom)
        if spec.integer:
            detail = t("engine.opt.exact_ilp",
                       value=exact.serialize(rep["objective"]))
        meta_obj = exact.serialize(objective_ex)
        meta_sol = {v: exact.serialize(x_ex[j])
                    for j, v in enumerate(spec.var_names)} if not spec.integer else {
            v: repr(sol_float[j]) for j, v in enumerate(spec.var_names)}
    else:
        obj_max = float(pulp.value(prob.objective))
        objective = obj_max if spec.sense == "max" else -obj_max
        cert = lp_dual_certificate(
            sense=spec.sense, objective=obj_max, dual=[abs(v) for v in dual_float],
            primal=relax_x, A=[[float(v) for v in r] for r in A],
            b=[float(v) for v in b], c=[float(v) for v in c], names=cons_names,
            var_names=list(spec.var_names), is_exact=False,
        )
        why = "" if not use_exact else t("engine.opt.float.why")
        detail = t("engine.opt.float") + why
        meta_obj = objective
        meta_sol = {v: sol_float[j] for j, v in enumerate(spec.var_names)}

    return Result(
        "opt", Status.SAT, Verdict.SATISFIABLE, ENGINE, ms(), cert, detail,
        meta={"objective": meta_obj,
              "objective_float": float(exact.to_fraction(meta_obj)),
              "exact": exact_ok, "solution": meta_sol,
              "integer": spec.integer, "denominator": denom,
              "min_dual": exact.serialize(min(y_ex)) if exact_ok
              else min([abs(v) for v in dual_float], default=0.0)},
    )
