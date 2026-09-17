"""Averaging over the group, as a certificate rather than a sentence.

Five examples in this repository begin with a symmetrised program, and the
sentence that gets them there is always some version of

    averaging over the automorphism group, an optimal solution may be assumed
    constant on each orbit

certo certifies everything downstream of that sentence -- the reduced
program's optimum, its dual, its branches -- and nothing about the sentence
itself. It is a bridge, and it is load-bearing.

It does not have to be. The averaging argument has exactly three hypotheses,
and given a generating set all three are FINITE CHECKS:

    the action permutes the variables      each generator is a bijection
    the constraint set is invariant        sigma(row) is a row, same sense
                                           and same right-hand side
    the objective is invariant             c[sigma(v)] == c[v]

With those, take any optimum `x` and average it over the group. The feasible
region is convex and every `sigma(x)` is feasible, so the average is feasible.
The objective is invariant and linear, so the average has the same value. And
the average is constant on orbits by construction. So an optimal solution
constant on orbits EXISTS, and restricting to those loses nothing.

THE QUOTIENT IS THEN ARITHMETIC. One variable per orbit; each coefficient the
SUM over the orbit, because substituting `x_v = z_orbit(v)` into a row does
exactly that. Rows that become identical are one row. Both directions hold:
a quotient solution lifts to a feasible original of the same value, and an
original optimum averages down to a quotient one.

WHERE THE GROUP COMES FROM is not this module's problem, and never was. nauty
computes it; `parametric` takes a dual; `labelling` takes a permutation. This
takes generators and CHECKS them -- and a generator that is not an
automorphism is refused by name, because a wrong group does not give a weaker
reduction, it gives a wrong one.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotSymmetric(ValueError):
    """Raised with the generator and the reason: a bare failure helps nobody."""


def _row_key(coeffs, sense, rhs):
    """A constraint as something two of them can be compared by."""
    from .exact import to_fraction

    return (tuple(sorted((v, str(to_fraction(c)))
                         for v, c in coeffs.items() if to_fraction(c))),
            sense, str(to_fraction(rhs)))


def _apply(perm, coeffs):
    return {perm.get(v, v): c for v, c in coeffs.items()}


def check_generator(spec, name, perm) -> None:
    """The three hypotheses of the averaging argument, for one generator."""
    from .exact import to_fraction

    variables = list(spec.var_names)
    mapped = {perm.get(v, v) for v in variables}
    if sorted(perm) != sorted(v for v in perm if v in set(variables)) \
            or mapped != set(variables):
        raise NotSymmetric(_t("symmetry.not_a_permutation", name=name))

    for v in variables:
        if to_fraction(spec.obj.get(v, 0)) != \
                to_fraction(spec.obj.get(perm.get(v, v), 0)):
            raise NotSymmetric(_t("symmetry.objective_moves", name=name,
                                  var=v))
        if spec.bounds.get(v) != spec.bounds.get(perm.get(v, v)):
            raise NotSymmetric(_t("symmetry.bounds_move", name=name, var=v))

    rows = {_row_key(c, s, r) for _n, c, s, r in spec.cons}
    for cname, coeffs, sense, rhs in spec.cons:
        moved = _row_key(_apply(perm, coeffs), sense, rhs)
        if moved not in rows:
            raise NotSymmetric(_t("symmetry.constraint_escapes", name=name,
                                  row=cname))


def orbits(variables, generators) -> list:
    """The orbits of the variables, by union-find over the generators."""
    parent = {v: v for v in variables}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for perm in generators.values():
        for v, w in perm.items():
            a, b = find(v), find(w)
            if a != b:
                parent[a] = b

    groups: dict = {}
    for v in variables:
        groups.setdefault(find(v), []).append(v)
    return [sorted(members) for _root, members in
            sorted(groups.items(), key=lambda kv: sorted(kv[1]))]


def quotient(spec, parts):
    """The reduced program: one variable per orbit, coefficients summed.

    Substituting `x_v = z_orbit(v)` into a row sums that row's coefficients
    over each orbit. Rows that collapse to the same thing are one row -- they
    were images of each other under the group, which is why there were several.
    """
    from .exact import to_fraction
    from .spec import LPSpec

    name_of = {v: "orbit_{}".format(i) for i, part in enumerate(parts)
               for v in part}
    out = LPSpec(sense=spec.sense, title=spec.title)
    for i, part in enumerate(parts):
        lo, hi = spec.bounds[part[0]]
        out.variable("orbit_{}".format(i), lo, hi)

    obj: dict = {}
    for v, c in spec.obj.items():
        key = name_of[v]
        obj[key] = obj.get(key, Fraction(0)) + to_fraction(c)
    out.objective({k: v for k, v in obj.items() if v})

    seen = set()
    for cname, coeffs, sense, rhs in spec.cons:
        row: dict = {}
        for v, c in coeffs.items():
            key = name_of[v]
            row[key] = row.get(key, Fraction(0)) + to_fraction(c)
        row = {k: v for k, v in row.items() if v}
        key = _row_key(row, sense, rhs)
        if key in seen:
            continue
        seen.add(key)
        out.constraint(row, sense, to_fraction(rhs), name=cname)
    return out


def certify(spec, generators) -> dict:
    """Check the three hypotheses, then build the quotient."""
    if not generators:
        raise NotSymmetric(_t("symmetry.no_generators"))
    perms = {str(n): {str(a): str(b) for a, b in p.items()}
             for n, p in dict(generators).items()}
    for name, perm in sorted(perms.items()):
        check_generator(spec, name, perm)

    parts = orbits(list(spec.var_names), perms)
    reduced = quotient(spec, parts)
    return {
        "generators": perms,
        "orbits": parts,
        "quotient": reduced,
        "variables": len(spec.var_names),
        "reduced_variables": len(parts),
        "rows": len(spec.cons),
        "reduced_rows": len(reduced.cons),
    }
