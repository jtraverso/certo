"""Puente hacia z3: serializacion de formulas y modelos.

Todo lo que entra en un certificado pasa por aqui, para que el certificado se
pueda releer sin la sesion de Python que lo produjo.
"""
from __future__ import annotations

import z3


def sort_name(e) -> str:
    s = e.sort()
    if s == z3.IntSort():
        return "Int"
    if s == z3.RealSort():
        return "Real"
    if s == z3.BoolSort():
        return "Bool"
    raise ValueError("sort no soportado (por ahora): " + str(s))


def value_repr(v):
    """Valor de z3 -> algo serializable en JSON y re-parseable sin perdida."""
    if z3.is_int_value(v):
        return v.as_long()
    if z3.is_rational_value(v):
        return str(v.as_fraction())  # '3/4' exacto, nunca float
    if z3.is_true(v):
        return True
    if z3.is_false(v):
        return False
    if z3.is_algebraic_value(v):
        return str(v.approx(20)) + " (algebraico, aproximado)"
    return str(v)


def assignment(model, variables) -> dict:
    """{nombre: (sort, valor)} con model_completion para no dejar huecos."""
    out = {}
    for v in variables:
        val = model.eval(v, model_completion=True)
        out[str(v)] = (sort_name(v), value_repr(val))
    return out


def smt2(*exprs) -> str:
    """Formulas -> texto SMT-LIB2 con sus declaraciones."""
    s = z3.Solver()
    for e in exprs:
        s.add(e)
    return s.to_smt2()


def free_consts(*exprs) -> list:
    """Constantes libres que aparecen en las formulas, ordenadas por nombre."""
    seen, out = set(), []
    stack = list(exprs)
    while stack:
        e = stack.pop()
        if z3.is_const(e) and e.decl().kind() == z3.Z3_OP_UNINTERPRETED:
            if str(e) not in seen:
                seen.add(str(e))
                out.append(e)
        else:
            stack.extend(e.children())
    return sorted(out, key=str)


def const(name: str, sort: str):
    """Reconstruye una constante z3 desde (nombre, sort) serializados."""
    return {"Int": z3.Int, "Real": z3.Real, "Bool": z3.Bool}[sort](name)


def value_of(sort: str, val):
    """Reconstruye un valor z3 desde su forma serializada."""
    if sort == "Int":
        return z3.IntVal(val)
    if sort == "Real":
        return z3.RealVal(val)
    if sort == "Bool":
        return z3.BoolVal(val)
    raise ValueError("sort no soportado: " + str(sort))
