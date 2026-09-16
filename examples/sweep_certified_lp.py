"""sweep with a certificate from the predicate.

The pattern that makes a sweep CITABLE when its predicate solves an LP.

A predicate returning True/False leaves the sweep half-done: the certificate
attests WHICH FAMILY was examined, but not that the predicate was evaluated
correctly on each graph. If there is a floating-point LP inside, that is
precisely the part a referee would want to check.

The fix is to return `Outcome(ok, cert=...)`: `sweep` aggregates each
counterexample's certificate and `verify` checks them in cascade.

Example predicate: the optimum of the mixed K3/K4 fractional packing with
weights (2, 5) is an INTEGER. False as soon as overlapping triangles appear,
and every failure comes with the exact dual proving what the optimum really
is.

    certo sweep examples/sweep_certified_lp.py --cert out/cert_lp.json
    certo verify out/cert_lp.json
"""
from fractions import Fraction
from itertools import combinations

from certo import LPSpec, Outcome, SweepSpec
from certo.engines import lp

N = 5


def packing_lp(g):
    """The graph's mixed K3/K4 packing LP, with exact weights 2 and 5."""
    spec = LPSpec(sense="max", title="packing")
    items = []
    for size, gain in ((3, 2), (4, 5)):
        for s in combinations(range(g.n), size):
            if all(g.has_edge(a, b) for a, b in combinations(s, 2)):
                name = "K{}_{}".format(size, "".join(map(str, s)))
                spec.variable(name)
                items.append((name, set(s), gain))
    if not items:
        return None
    spec.objective({name: gain for name, _, gain in items})
    for e in combinations(range(g.n), 2):
        if not g.has_edge(*e):
            continue
        se = set(e)
        coeffs = {name: 1 for name, verts, _ in items if se <= verts}
        if coeffs:
            spec.constraint(coeffs, "<=", 1, name="e{}{}".format(*e))
    return spec


def integral_optimum(g):
    spec = packing_lp(g)
    if spec is None:
        return Outcome(ok=True, detail="no triangles: optimum 0")

    res = lp.opt(spec)
    if not res.meta.get("exact"):
        # No pretending: with no exact certificate, we do not conclude.
        return Outcome(ok=None, detail="could not be certified exactly")

    value = Fraction(res.meta["objective"])
    return Outcome(
        ok=(value.denominator == 1),
        cert=res.certificate,
        detail="W* = {}".format(res.meta["objective"]),
    )


def spec():
    return SweepSpec(
        n=N,
        filters=["connected"],
        predicate=integral_optimum,
        title="the mixed packing optimum is an integer (false)",
        describe=lambda g: "{} n={} m={}".format(g.to_graph6(), g.n, g.m),
    )
