"""The other half of R(3,3): the CNF on K5 is SATISFIABLE.

The model is a 2-colouring of K5 with no monochromatic triangle, so
R(3,3) > 5. Together with the UNSAT proof on K6 (`examples/ramsey.py`) that
pins the number exactly -- and `examples/compose_proof.py` assembles the two
into one certificate.

A separate file rather than a flag, so each certificate keeps clean
provenance: editing the spec after a run makes `verify` say so, which is the
point.

    certo cases examples/ramsey_k5.py --cert out/r33_k5.json
"""

from itertools import combinations

from certo import CNF, CNFSpec

N = 5
BREAK_SYMMETRY = False


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
