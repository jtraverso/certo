"""shrink: minimise a graph counterexample.

Predicate (false): "every connected graph is chordal". The minimal
counterexample has to be C4, the 4-cycle: n=4, m=4. It is the smallest known
obstruction.

    certo shrink examples/shrink_nonchordal.py --cert out/shrink.json
    certo verify out/shrink.json
"""
from certo import SweepSpec
from certo.graphs import is_chordal

N = 7


def spec():
    return SweepSpec(
        n=N,
        filters=["connected"],
        predicate=is_chordal,
        title="(false) every connected graph is chordal",
        describe=lambda g: "{} n={} m={}".format(g.to_graph6(), g.n, g.m),
    )
