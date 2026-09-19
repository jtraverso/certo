"""bisect: the smallest set whose deletion fixes a property.

The question does not look like a SAT question, which is why people write an
integer program for it instead: *how few vertices can I delete to make this
graph 3-colourable?* A team that needed exactly this reported numbers from a
hand-written ILP and had to retract part of the conclusion; their summary
afterwards was "I wasn't missing a tool, I was missing the encoding".

Three pieces, none of them new:

  `at_most_k`   the counting constraint that turns `cases` from a decision
                procedure into an optimiser. Sequential counter, O(n*k)
                clauses -- the pairwise encoding is C(n, k+1), which with 35
                literals and k=6 is 6.7 million.

  `cases`       SAT gives the deletion set AND the colouring; UNSAT gives a
                DRAT proof that no deletion of that size exists. Both bounds,
                both certified, and the lower one solver-free to re-check.

  `bisect`      sweeps k. Do NOT write the `for k in range(...)` that stops at
                the first SAT: it reads `unknown_solver` as `unsat` and
                reports a threshold that is not one.

The instance is five disjoint copies of K6 with q = 3. A clique on m vertices
needs m - q deletions -- all its vertices take distinct colours, so at most q
survive -- and the copies are disjoint, so D_3 = 5 * (6 - 3) = 15. The
threshold is therefore 14: no deletion of 14 works, and one of 15 does.

    certo bisect examples/smallest_deletion.py --cert out/deletion.json
    certo verify out/deletion.json

See docs/CASES.md, "The smallest set that fixes this".
"""
from itertools import combinations

from certo import CNF, BisectSpec, CNFSpec

BLOCKS, SIZE, COLOURS = 5, 6, 3
N = BLOCKS * SIZE
EDGES = [(a, b) for blk in range(BLOCKS)
         for a, b in combinations(range(blk * SIZE, (blk + 1) * SIZE), 2)]


def deletable(k: int) -> CNFSpec:
    """Satisfiable exactly when `k` deletions make the graph q-colourable."""
    cnf = CNF("D_{} <= {}".format(COLOURS, k))
    y = [cnf.var("y{}".format(v)) for v in range(N)]
    z = [[cnf.var("z{}_{}".format(v, c)) for c in range(COLOURS)]
         for v in range(N)]
    for v in range(N):
        # Deleted, or coloured, and not both: `exactly_one` over the colours
        # TOGETHER WITH the deletion flag is what makes the two exclusive.
        cnf.exactly_one(z[v] + [y[v]])
    for a, b in EDGES:
        for c in range(COLOURS):
            cnf.add(-z[a][c], -z[b][c])
    cnf.at_most_k(y, k)
    return CNFSpec(cnf=cnf, title=cnf.title)


def spec():
    # For a CNFSpec, "holds" means UNSAT -- no deletion of that size exists --
    # and that is true for SMALL k, so the threshold wanted is the largest one.
    return BisectSpec(
        build=lambda t: deletable(int(t)),
        lo=0, hi=20, direction="max_true", integer=True,
        title="the largest k with no k-deletion to 3-colourable",
    )
