"""shrink: MUS over the Ramsey instance on K7.

The formula says "K7 with no monochromatic triangle": 70 clauses over 21
variables, unsatisfiable. But R(3,3) = 6, so six vertices already suffice.

The MUS comes down to 38 clauses over the 15 edges of a K6: the minimisation
REDISCOVERS that six vertices are enough. The certificate carries the DRAT
proof of the MUS and, for each surviving clause, a model of the MUS without
it: unsatisfiability and minimality, both without a solver.

    certo shrink examples/mus_ramsey.py --cert out/mus.json
    certo verify out/mus.json
"""
from itertools import combinations

from certo import CNF, CNFSpec

N = 7


def spec():
    cnf = CNF(title="no monochromatic triangle in K{}".format(N))

    def x(i, j):
        return cnf.var("e{}_{}".format(min(i, j), max(i, j)))

    for i, j in combinations(range(N), 2):
        x(i, j)
    for t in combinations(range(N), 3):
        a, b, c = x(t[0], t[1]), x(t[0], t[2]), x(t[1], t[2])
        cnf.add(-a, -b, -c)
        cnf.add(a, b, c)

    return CNFSpec(cnf=cnf, title="MUS of R(3,3) over K7", expect="unsat",
                   meta={"n": N})
