"""cases: R(3,3) <= 6 as a finite case with a DRAT proof.

Variable x_ij = "edge {i,j} is red". For every triangle, forbid all three of
its edges having the same colour:

    (~x_ij | ~x_ik | ~x_jk)   not all red
    ( x_ij |  x_ik |  x_jk)   not all blue

With N=5 it is SATISFIABLE: the witness is the 2-colouring with no
monochromatic triangle, i.e. R(3,3) > 5.
With N=6 it is UNSATISFIABLE, and the verified DRAT proof is R(3,3) <= 6.

    certo cases examples/ramsey.py --proof out/r33.drat --cert out/r33.json
    certo verify out/r33.json

Set N=5 to see the satisfiable side.
"""
from itertools import combinations

from certo import CNF, CNFSpec

N = 6
BREAK_SYMMETRY = False  # with N=6 the instance is tiny; set True to try it


def spec():
    cnf = CNF(title="no monochromatic triangle in K{}".format(N))

    def x(i, j):
        i, j = min(i, j), max(i, j)
        return cnf.var("e{}_{}".format(i, j))

    for i, j in combinations(range(N), 2):
        x(i, j)  # fix the variable order before breaking symmetry

    for t in combinations(range(N), 3):
        a, b, c = x(t[0], t[1]), x(t[0], t[2]), x(t[1], t[2])
        cnf.add(-a, -b, -c)
        cnf.add(a, b, c)

    if BREAK_SYMMETRY:
        cnf.break_vertex_symmetry(x, N)

    return CNFSpec(
        cnf=cnf,
        title="R(3,3): K{} with no monochromatic triangle".format(N),
        expect="unsat" if N >= 6 else "sat",
        meta={"n": N, "symmetry_broken": BREAK_SYMMETRY},
    )
