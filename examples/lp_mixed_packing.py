"""opt: fractional mixed K3/K4 packing with weights (2, 5) over K_n.

The LP that shows up in a clique-partition problem: each copy of K3 is worth
2 and each K4 is worth 5 (its edge count minus one), and each edge can be
used at most once.

For K_n the optimum is 5*n*(n-1)/12, attained by K4s alone. For n=6 that is
25/2 -- and the certificate says 25/2, not 12.500000250000001.

    certo opt examples/lp_mixed_packing.py
"""
from itertools import combinations

from certo import LPSpec

N = 6


def spec():
    lp = LPSpec(sense="max", title="mixed K3/K4 packing over K{}".format(N))

    tris = list(combinations(range(N), 3))
    quads = list(combinations(range(N), 4))
    for t in tris:
        lp.variable("T" + "".join(map(str, t)))
    for q in quads:
        lp.variable("Q" + "".join(map(str, q)))

    obj = {}
    for t in tris:
        obj["T" + "".join(map(str, t))] = 2
    for q in quads:
        obj["Q" + "".join(map(str, q))] = 5
    lp.objective(obj)

    for e in combinations(range(N), 2):
        se = set(e)
        coeffs = {}
        for t in tris:
            if se <= set(t):
                coeffs["T" + "".join(map(str, t))] = 1
        for q in quads:
            if se <= set(q):
                coeffs["Q" + "".join(map(str, q))] = 1
        lp.constraint(coeffs, "<=", 1, name="e{}{}".format(*e))

    return lp
