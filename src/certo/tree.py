"""The root problem, and every node's problem derived from it.

A branch-and-bound certificate says the strongest thing certo says: NO DESIGN
DOES BETTER. To mean it, the account has to cover every design, and each node
has to be closed by something about THAT node.

Storing a certificate per node does not give the second half. A certificate
for a node's relaxation is a valid certificate for SOME linear program, and
nothing in it says which node it belongs to -- so a certificate for an easy
subtree, attached to a hard one, reads exactly like a complete proof. That is
not hypothetical: a tree with two node certificates exchanged verified.

So a node's problem is not stored. It is DERIVED, here, from the root system
and the node's own fixings, by the one function below -- and the producer
calls the same function the verifier does, so there is no second reading of
what "the node's LP" means for the two of them to disagree about.

The compression falls out. The root system is written once instead of once per
node, and what a node carries is its fixings, its bound, and the two vectors
that close it.
"""
from __future__ import annotations

from fractions import Fraction


def system_of(spec) -> dict:
    """The root LP, exactly, in a form that survives a round trip through JSON."""
    from . import exact

    def num(x):
        return exact.serialize(exact.to_fraction(x))

    return {
        "sense": spec.sense,
        "var_names": list(spec.var_names),
        "bounds": {v: [None if lo is None else num(lo),
                       None if hi is None else num(hi)]
                   for v, (lo, hi) in spec.bounds.items()},
        "obj": {v: num(c) for v, c in spec.obj.items()},
        "cons": [[name, {v: num(c) for v, c in coeffs.items()}, sense, num(rhs)]
                 for name, coeffs, sense, rhs in spec.cons],
        "kinds": {v: spec.kind_of(v) for v in spec.var_names},
    }


def spec_of(system: dict):
    """Back to an `LPSpec`. The inverse of `system_of`, used by `verify`."""
    from .exact import to_fraction
    from .spec import LPSpec

    out = LPSpec(sense=system["sense"])
    kinds = system.get("kinds") or {}
    for v in system["var_names"]:
        lo, hi = system["bounds"].get(v, [None, None])
        out.variable(v,
                     None if lo is None else to_fraction(lo),
                     None if hi is None else to_fraction(hi),
                     kind=kinds.get(v, "continuous"))
    out.objective({v: to_fraction(c) for v, c in system["obj"].items()})
    for name, coeffs, sense, rhs in system["cons"]:
        out.constraint({v: to_fraction(c) for v, c in coeffs.items()},
                       sense, to_fraction(rhs), name=name)
    return out


def restrict(spec, fixed: dict):
    """The relaxation at a node: the fixed variables gone, the rest free.

    Returns `(LPSpec, const)`, where `const` is what the fixed variables
    already contribute to the objective -- an `LPSpec` has no constant term,
    so it travels separately rather than being folded in and lost.
    """
    from .exact import to_fraction
    from .spec import LPSpec

    out = LPSpec(sense=spec.sense, title=spec.title)
    free = [v for v in spec.var_names if v not in fixed]
    for v in free:
        lo, hi = spec.bounds[v]
        out.variable(v, lo, hi)
    out.objective({v: c for v, c in spec.obj.items() if v in set(free)})
    const = sum((to_fraction(spec.obj.get(v, 0)) * to_fraction(val)
                 for v, val in fixed.items()), Fraction(0))
    for name, coeffs, sense, rhs in spec.cons:
        moved = sum((to_fraction(c) * to_fraction(fixed[v])
                     for v, c in coeffs.items() if v in fixed), Fraction(0))
        rest = {v: c for v, c in coeffs.items() if v not in fixed}
        out.constraint(rest, sense, to_fraction(rhs) - moved, name=name)
    return out, const


def fixings(pairs) -> dict:
    """A node's `fixed` list, as the dictionary `restrict` wants."""
    return {v: x for v, x in pairs}
