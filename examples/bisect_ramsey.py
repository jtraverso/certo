"""bisect: compute R(3,3) by finding the threshold, certified on both sides.

For each n it builds the CNF "K_n admits a 2-colouring with no monochromatic
triangle". Bisect's convention with a CNF: "holds" = UNSAT = no such
colouring exists.

The threshold is R(3,3) = 6, and the certificate brackets it:
  - good side n=6: verified DRAT proof (no colouring exists)
  - bad side  n=5: the model, i.e. the pentagon

    certo bisect examples/bisect_ramsey.py --trace --cert out/r33_bisect.json
    certo verify out/r33_bisect.json
"""
from itertools import combinations

from certo import CNF, BisectSpec, CNFSpec


def build(n):
    cnf = CNF(title="K{} with no monochromatic triangle".format(n))

    def x(i, j):
        return cnf.var("e{}_{}".format(min(i, j), max(i, j)))

    for i, j in combinations(range(n), 2):
        x(i, j)
    for t in combinations(range(n), 3):
        a, b, c = x(t[0], t[1]), x(t[0], t[2]), x(t[1], t[2])
        cnf.add(-a, -b, -c)
        cnf.add(a, b, c)
    return CNFSpec(cnf=cnf, title="R(3,3) on K{}".format(n))


def spec():
    return BisectSpec(build=build, lo=3, hi=8, direction="min_true",
                      integer=True, title="R(3,3)")
