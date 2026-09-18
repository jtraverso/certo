"""The quotient as an EQUIVALENCE, not as two optima that agree.

`reduce` certifies a symmetry argument and then compares optima. Comparing two
computed optima does not show the reduction is correct -- it shows two numbers
came out the same, which is what a wrong reduction with a compensating error
also does. What a formalisation actually needs is stronger and, it turns out,
easier:

    the physical program and the quotient have the SAME SET of attainable
    values, by an explicit projection and lifting that preserve the objective

Equality of optima is then a corollary, and the proof needs no duality.

THE NORMALISATION IS FIXED HERE AND NOWHERE ELSE. The reduced variable is the
TOTAL MASS of a column class,

    z_j = sum over C in class j of x_C,

the quotient is `max sum_j w_j z_j` subject to `sum_j B_ij z_j <= N_i b_i`,
and the lifting is `x_C = z_j / M_j`. Mixing this with a variable meaning
"mass per copy" changes the matrix, the objective AND the multiplicity
factors, so the convention is not negotiable inside one certificate.

THE HYPOTHESIS THAT DOES THE WORK is per-row regularity:

    for every physical row e in class i, and every column class j,
    sum over C in class j of A_eC  equals  B_ij, the same for every such e

and the load-bearing word is EVERY. Constancy of a block TOTAL does not imply
it. A block can have the right sum while individual rows inside the class see
different amounts, and then projection still works while lifting does not --
the quotient reports a value the physical program cannot attain. That is not
hypothetical: a single edge given capacity zero among capacity-one edges
breaks it, and the aggregate program happily reports a larger optimum.

So capacities are checked constant on row classes, weights and bounds constant
on column classes, and regularity is checked row by row against the physical
matrix. A partition that fails any of them is REFUSED, naming the two rows
that disagree.

WHERE THE PARTITION COMES FROM IS NOT THIS MODULE'S PROBLEM. A group action
produces one, and `reduce` is exactly that route; so does a colour refinement,
so does a person who knows what the classes are. Taking the partition as input
and checking it is what separates the finite-sum core from the group theory,
which is the separation a proof assistant wants anyway.

WHAT IS NOT CLAIMED, and `verify` repeats it: INTEGRALITY. The equivalence is
between the fractional programs. An integer orbit mass need not lift to
integer objects -- on K4 with triangles only, the fractional programs agree
and the integer packing is strictly smaller -- so a quotient certificate is
never evidence about an integer program.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t


class NotEquitable(ValueError):
    """Raised with the two rows that disagree, never bare."""


def _classes(names, assignment, what) -> dict:
    """Group names by class, refusing anything that is not a partition."""
    missing = [n for n in names if n not in assignment]
    if missing:
        raise NotEquitable(_t("equitable.unassigned", what=what,
                              names=", ".join(map(str, missing[:4])),
                              n=len(missing)))
    stray = [n for n in assignment if n not in set(names)]
    if stray:
        raise NotEquitable(_t("equitable.stray", what=what,
                              names=", ".join(map(str, stray[:4]))))
    out: dict = {}
    for n in names:
        out.setdefault(str(assignment[n]), []).append(n)
    return out


def _constant(values, label, what):
    """One value shared by a whole class, or a refusal naming two that differ."""
    first = None
    for name, v in values:
        if first is None:
            first = (name, v)
        elif v != first[1]:
            raise NotEquitable(_t("equitable.not_constant", what=what,
                                  cls=label, a=first[0], b=name,
                                  va=str(first[1]), vb=str(v)))
    return first[1]


def analyse(lp, row_class, col_class) -> dict:
    """Every hypothesis the equivalence needs, checked against the matrix.

    Returns the reduced data -- `B`, the class sizes, the capacities and the
    weights -- or raises with the specific pair that broke it.
    """
    from .exact import to_fraction

    cols = _classes(list(lp.var_names), col_class, "column")
    row_names = [n for n, _c, _s, _r in lp.cons]
    rows = _classes(row_names, row_class, "row")

    by_name = {n: (c, s, r) for n, c, s, r in lp.cons}
    senses = {}
    caps = {}
    for i, members in sorted(rows.items()):
        senses[i] = _constant([(e, by_name[e][1]) for e in members], i, "sense")
        caps[i] = _constant([(e, to_fraction(by_name[e][2])) for e in members],
                            i, "capacity")

    weights, bounds = {}, {}
    for j, members in sorted(cols.items()):
        weights[j] = _constant(
            [(c, to_fraction(lp.obj.get(c, 0))) for c in members], j, "weight")
        bounds[j] = _constant([(c, lp.bounds.get(c)) for c in members], j,
                              "bound")

    # TWO regularities, and they are different quantities. Confusing them
    # builds a quotient that is wrong in a way no optimum comparison catches
    # until you compare against the physical program: on K4 with triangles it
    # reports 6 where the physical value is 4.
    #
    #   H_ij  for ONE resource of class i, how many objects of class j use it
    #   B_ij  for ONE object of class j, how many resources of class i it uses
    #
    # Lifting needs H (each physical row must see the same load) and the
    # quotient's matrix needs B (each aggregated row counts consumption). They
    # are tied by a double count of the incident pairs,
    #
    #   N_i . H_ij  =  M_j . B_ij
    #
    # which is therefore a CONSEQUENCE of the two rather than a third
    # hypothesis -- and checking it anyway is what catches an implementation
    # that computed one and used it as the other.
    #
    # Both are walked SPARSELY: a row touches the columns it touches. Sweeping
    # every column for every row gives the same answer and, on a family whose
    # physical program has tens of thousands of columns, is the difference
    # between a second and an afternoon.
    of_column = {c: j for j, members in cols.items() for c in members}
    of_row = {e: i for i, members in rows.items() for e in members}

    H: dict = {}
    for i, members in sorted(rows.items()):
        per_row = []
        for e in members:
            totals: dict = {}
            for c, v in by_name[e][0].items():
                f = to_fraction(v)
                if f:
                    j = of_column[c]
                    totals[j] = totals.get(j, Fraction(0)) + f
            per_row.append((e, {j: v for j, v in totals.items() if v}))
        for j, v in _constant(per_row, i, "regularity").items():
            H[(i, j)] = v

    down: dict = {}
    for e, coeffs in ((n, c) for n, c, _s, _r in lp.cons):
        i = of_row[e]
        for c, v in coeffs.items():
            f = to_fraction(v)
            if f:
                down.setdefault(c, {})
                down[c][i] = down[c].get(i, Fraction(0)) + f

    B: dict = {}
    for j, members in sorted(cols.items()):
        per_col = [(c, {k: v for k, v in down.get(c, {}).items() if v})
                   for c in members]
        for i, v in _constant(per_col, j, "consumption").items():
            B[(i, j)] = v

    N = {i: len(m) for i, m in rows.items()}
    M = {j: len(m) for j, m in cols.items()}
    off = [(i, j) for (i, j) in set(H) | set(B)
           if N[i] * H.get((i, j), Fraction(0))
           != M[j] * B.get((i, j), Fraction(0))]
    if off:
        i, j = off[0]
        raise NotEquitable(_t("equitable.double_count", i=i, j=j,
                              lhs=str(N[i] * H.get((i, j), 0)),
                              rhs=str(M[j] * B.get((i, j), 0)), n=len(off)))

    return {"rows": rows, "columns": cols, "B": B, "H": H, "capacities": caps,
            "weights": weights, "senses": senses, "bounds": bounds,
            "N": N, "M": M}


def quotient(lp, data):
    """`max sum_j w_j z_j` s.t. `sum_j B_ij z_j <= N_i b_i`, `z_j >= 0`.

    The objective is the class weight times the TOTAL MASS, which is what
    `z_j = sum_{C in j} x_C` makes it: no multiplicity factor appears here,
    because it is already inside `z`.
    """
    from .spec import LPSpec

    out = LPSpec(sense=lp.sense, title=(lp.title or "") + " / quotient")
    for j in sorted(data["columns"]):
        lo, hi = data["bounds"][j] or (0, None)
        top = None if hi is None else Fraction(hi) * data["M"][j]
        out.variable("z_" + j, 0, top)
    out.objective({"z_" + j: w for j, w in sorted(data["weights"].items())
                   if w})
    for i in sorted(data["rows"]):
        coeffs = {"z_" + j: v for (ii, j), v in sorted(data["B"].items())
                  if ii == i}
        if coeffs:
            out.constraint(coeffs, data["senses"][i],
                           data["capacities"][i] * data["N"][i], name=i)
    return out


def project(x, data) -> dict:
    """`z_j = sum over the fibre`, the normalisation everything else assumes."""
    from .exact import to_fraction

    return {j: sum((to_fraction(x.get(c, 0)) for c in members), Fraction(0))
            for j, members in data["columns"].items()}


def lift(z, data) -> dict:
    """`x_C = z_j / M_j`: the class mass spread evenly over its members."""
    out = {}
    for j, members in data["columns"].items():
        share = Fraction(z.get(j, 0)) / len(members)
        for c in members:
            out[c] = share
    return out


def certify(spec) -> dict:
    """The hypotheses, the reduced data, and the two maps."""
    lp = spec.lp.to_lp() if hasattr(spec.lp, "to_lp") else spec.lp
    data = analyse(lp, spec.rows, spec.columns)
    reduced = quotient(lp, data)

    # `Proj(Lift(z)) = z` is the half that says nothing was lost, and it is
    # an identity about the fibre sizes -- checked on the basis rather than
    # asserted, because it is cheap and because asserting it is how a wrong
    # normalisation survives.
    roundtrip = []
    for j in sorted(data["columns"]):
        back = project(lift({j: Fraction(1)}, data), data)
        if back.get(j) != 1 or any(v for k, v in back.items() if k != j):
            roundtrip.append(j)

    return {
        "row_classes": {i: sorted(map(str, m))
                        for i, m in sorted(data["rows"].items())},
        "column_classes": {j: sorted(map(str, m))
                           for j, m in sorted(data["columns"].items())},
        "N": data["N"], "M": data["M"],
        "B": {"{}|{}".format(i, j): str(v)
              for (i, j), v in sorted(data["B"].items())},
        "H": {"{}|{}".format(i, j): str(v)
              for (i, j), v in sorted(data["H"].items())},
        "capacities": {i: str(v) for i, v in sorted(data["capacities"].items())},
        "weights": {j: str(v) for j, v in sorted(data["weights"].items())},
        "senses": data["senses"],
        "bounds": {j: (list(v) if v else None)
                   for j, v in sorted(data["bounds"].items())},
        "sense": lp.sense,
        "physical_rows": len(lp.cons),
        "physical_columns": len(lp.var_names),
        "roundtrip_failures": roundtrip,
        "quotient": _system(reduced),
    }


def _system(lp) -> dict:
    from .tree import system_of

    return system_of(lp)
