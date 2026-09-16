"""opt with a PackingSpec: cliques competing for edges.

The same mixed K3/K4 packing as lp_mixed_packing.py, but built from the
combinatorial description instead of assembling the LP by hand. Constraint
names are edge names, so the dual reads directly as a load per edge.

    certo opt examples/packing_mixed.py --by-type
"""
from certo import PackingSpec
from certo.graphs import Graph

N = 6


def spec():
    g = Graph.from_edges(N, [(i, j) for i in range(N) for j in range(i + 1, N)])
    return PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5},
                                        title="mixed K3/K4 packing on K6")
