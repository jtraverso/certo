"""sweep: exhaustive validation over an enumerated family.

Predicate: every non-empty chordal graph has a simplicial vertex (its
neighbourhood induces a clique). A classical theorem of Dirac; here it is
checked for a fixed n, which is NOT the theorem but would catch a mistake in
`is_chordal` or in the statement.

    certo sweep examples/sweep_simplicial.py

Set `TEST_FALSE = True` to see the REFUTED shape with counterexamples.
"""
from itertools import combinations

from certo import SweepSpec

N = 6
TEST_FALSE = False


def has_simplicial_vertex(g):
    if g.n == 0:
        return True
    for v in range(g.n):
        nb = sorted(g.neighbors(v))
        if all(g.has_edge(a, b) for a, b in combinations(nb, 2)):
            return True
    return False


def every_graph_is_chordal(g):
    """Deliberately false: shows the REFUTED output."""
    from certo.graphs import is_chordal

    return is_chordal(g)


def spec():
    if TEST_FALSE:
        return SweepSpec(
            n=N, filters=["connected"], predicate=every_graph_is_chordal,
            title="(false) every connected graph is chordal",
            describe=lambda g: "{} m={}".format(g.to_graph6(), g.m),
        )
    return SweepSpec(
        n=N,
        filters=["chordal", "connected"],
        predicate=has_simplicial_vertex,
        title="every connected chordal graph has a simplicial vertex",
        describe=lambda g: "{} m={}".format(g.to_graph6(), g.m),
    )
