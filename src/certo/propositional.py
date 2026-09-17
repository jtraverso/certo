"""A propositional formula, as a CNF a DRAT proof can refute.

There was an asymmetry. `prove` decides logic -- disjunctions, implications,
booleans mixed with arithmetic, quantifiers -- and hands back an `unsat_core`
that re-checks by RUNNING A SOLVER AGAIN. `cases` refutes a CNF with a DRAT
proof that re-checks by unit propagation and nothing else. So the strongest
artefact in the project was reachable only by writing clauses by hand, and
anything with an `Or` in it fell back to trusting z3 twice.

This is the bridge, and it is the standard one. Tseitin: give every subformula
a name, constrain the name to mean what the subformula means, and the result
is a CNF in clauses linear in the size of the formula rather than the
exponential blow-up of distributing `Or` over `And`.

EQUISATISFIABLE, NOT EQUIVALENT, and that distinction is the whole reason to
write it down. The CNF has variables the formula never had. What survives is:

    the CNF is satisfiable  <=>  the formula is satisfiable
    a model of the CNF, restricted to the original variables, is a model of
        the formula

Both directions are sound for what this is used for, and neither says the two
formulas are the same object. `decode` drops the auxiliaries, so an answer
comes back in the variables somebody wrote.

TO PROVE RATHER THAN TO SATISFY, encode the NEGATION. A tautology is a formula
whose negation is unsatisfiable, so `prove=True` encodes `Not(phi)` and an
UNSAT answer with its DRAT proof establishes `phi`. The certificate then
refutes something the user never asserted, which reads wrong unless it is
said: the spec carries what the refutation MEANS, and `cases` prints it.

WHAT IT DOES NOT COVER, and refuses rather than mangling: quantifiers, and
atoms that are not propositional -- `x + y <= 3` is not a boolean variable,
and pretending it is one would produce a CNF whose refutation says nothing
about the arithmetic. Mixed problems stay with `prove`, where they belong.
"""
from __future__ import annotations

from .i18n import t as _t


class NotPropositional(ValueError):
    """Outside propositional logic. Refused rather than encoded as an atom."""


def _lit(cnf, expr, memo, atoms):
    """A literal standing for `expr`, adding the clauses that make it mean it."""
    import z3

    key = expr.get_id()
    if key in memo:
        return memo[key]

    if z3.is_true(expr):
        v = cnf.var("__true")
        cnf.add(v)
        memo[key] = v
        return v
    if z3.is_false(expr):
        v = cnf.var("__true")
        cnf.add(v)
        memo[key] = -v
        return -v

    if z3.is_not(expr):
        out = -_lit(cnf, expr.arg(0), memo, atoms)
        memo[key] = out
        return out

    if z3.is_and(expr) or z3.is_or(expr) or z3.is_implies(expr):
        if z3.is_implies(expr):
            parts = [-_lit(cnf, expr.arg(0), memo, atoms),
                     _lit(cnf, expr.arg(1), memo, atoms)]
            conj = False
        else:
            parts = [_lit(cnf, expr.arg(i), memo, atoms)
                     for i in range(expr.num_args())]
            conj = z3.is_and(expr)
        z = cnf.aux("and" if conj else "or")
        if conj:
            # z -> every part, and every part -> z
            for p in parts:
                cnf.add(-z, p)
            cnf.add(z, *[-p for p in parts])
        else:
            # z -> some part, and every part -> z
            cnf.add(-z, *parts)
            for p in parts:
                cnf.add(z, -p)
        memo[key] = z
        return z

    if z3.is_eq(expr) and expr.arg(0).sort() == z3.BoolSort():
        a = _lit(cnf, expr.arg(0), memo, atoms)
        b = _lit(cnf, expr.arg(1), memo, atoms)
        z = cnf.aux("iff")
        cnf.add(-z, -a, b)
        cnf.add(-z, a, -b)
        cnf.add(z, a, b)
        cnf.add(z, -a, -b)
        memo[key] = z
        return z

    if z3.is_distinct(expr) and expr.num_args() == 2 \
            and expr.arg(0).sort() == z3.BoolSort():
        a = _lit(cnf, expr.arg(0), memo, atoms)
        b = _lit(cnf, expr.arg(1), memo, atoms)
        z = cnf.aux("xor")
        cnf.add(-z, a, b)
        cnf.add(-z, -a, -b)
        cnf.add(z, -a, b)
        cnf.add(z, a, -b)
        memo[key] = z
        return z

    # An atom. It must be a propositional one: an arithmetic comparison
    # encoded as a boolean variable would give a CNF whose refutation says
    # nothing about the arithmetic, which is a wrong answer rather than a
    # missing feature.
    if expr.sort() != z3.BoolSort():
        raise NotPropositional(_t("prop.not_bool", got=str(expr)[:60],
                                  sort=str(expr.sort())))
    if expr.num_args() or not z3.is_const(expr):
        raise NotPropositional(_t("prop.not_atom", got=str(expr)[:60]))

    name = str(expr)
    atoms.add(name)
    v = cnf.var(name)
    memo[key] = v
    return v


def to_cnf(expr, prove=False, title=""):
    """A propositional formula as a `CNFSpec`.

    `prove=False` asks whether the formula is SATISFIABLE and encodes it.
    `prove=True` asks whether it is VALID and encodes its negation, so an
    UNSAT answer with a DRAT proof establishes the formula.
    """
    import z3

    from .cnf import CNF, CNFSpec

    if z3.is_quantifier(expr):
        raise NotPropositional(_t("prop.quantifier"))

    target = z3.Not(expr) if prove else expr
    cnf = CNF(title=title)
    memo, atoms = {}, set()
    top = _lit(cnf, target, memo, atoms)
    cnf.add(top)

    return CNFSpec(
        cnf=cnf, title=title,
        expect="unsat" if prove else "",
        meta={
            "propositional": True,
            "encoded": "not(formula)" if prove else "formula",
            "means": _t("prop.means_valid" if prove else "prop.means_sat"),
            "atoms": sorted(atoms),
            "auxiliaries": cnf.nvars - len(atoms),
        },
    )


def model_of(cnf, true_vars, atoms) -> dict:
    """A model in the variables somebody WROTE, with the auxiliaries dropped.

    Tseitin's extra variables are an artefact of the encoding. Reporting them
    beside the real ones would make a reader check whether `__or_7` was part
    of their problem.
    """
    positive = {cnf.name_of(v) for v in true_vars if v > 0}
    return {a: (a in positive) for a in sorted(atoms)}
