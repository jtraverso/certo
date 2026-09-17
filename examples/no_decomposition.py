"""Divisible, and still not decomposable. The refutation that says so.

`cover` answers "is this a cover, and how large". It cannot answer the other
question, which in a write-up is often the interesting half:

    triangle-divisibility alone does not imply triangle-decomposability

and the way that sentence gets made true is by exhibiting an obstruction: a
graph whose every degree is even and whose edge count is divisible by three,
with NO decomposition into triangles. Both halves have to be established, and
they are established differently. The first is arithmetic. The second is a
non-existence over a finite domain, and the honest artefact for it is a
refutation, not an absence -- "I looked and found nothing" is a report about a
search; "here is a proof that nothing could have been found" is a certificate.

The graph here is K7 with two vertex-disjoint triangles removed. Fifteen
edges, so three divides it; six vertices drop from degree six to four and the
seventh stays at six, so every degree is even. Nine triangles survive, and no
five of them partition the fifteen edges.

    $ certo exists examples/no_decomposition.py
    PROVED  [unsat]
      NO exact cover exists over these 9 candidate parts, for a universe of 15.
      The DRAT refutation says so; it needs no solver to re-check
      certificate: drat (no solver needed)
      this says no cover exists USING THESE CANDIDATES [...]

THE SCOPE LINE IS THE POINT, and for once it is not a limitation. "No cover
over these candidates" is the same statement as "no cover" exactly when the
candidates are every part that could have been used -- and here the encoder
BUILDS that set, every triangle of the graph, rather than taking a list
somebody typed. So the coincidence is arranged rather than hoped for, and
`triangles_of` exists so that it cannot quietly stop holding.

TWO ANSWERS, TWO CERTIFICATES, and neither trusts the solver. When a cover
exists the model is a SUGGESTION: the parts it names go through `cover`'s own
verifier and are checked by counting. When none exists the DRAT proof is
checked by unit propagation. The solver is a search, and a search is never
the evidence here.

`smaller()` below is the companion obstruction and is over before it starts:
the 6-cycle has even degrees and six edges, and no triangles at all, so the
encoding contains the empty clause and the question is settled without a
solver touching it. Worth keeping because it is the example a reader meets
first, and because "there were no candidates" is a real answer rather than an
error.
"""
from itertools import combinations

from certo import CoverSpec
from certo.existence import triangles_of


def _graph(n, edges):
    """The cover question for a triangle decomposition: edges, and triangles."""
    return CoverSpec(
        universe=[list(e) for e in edges],
        # `parts` is what a cover certificate would check; here the question
        # is whether any assignment works, so what matters is `candidates`.
        parts=[],
        candidates=[[list(e) for e in tri] for tri in triangles_of(n, edges)],
        exact=True,
        title="a triangle decomposition of a divisible graph, if one exists",
    )


def _divisible(n, edges):
    """Even degrees and three dividing the edge count. The other half."""
    degree = {v: 0 for v in range(n)}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    return all(d % 2 == 0 for d in degree.values()), len(edges) % 3 == 0


def spec():
    """K7 minus two vertex-disjoint triangles: 15 edges, 9 triangles, no five
    of which partition them."""
    removed = {(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)}
    edges = [e for e in combinations(range(7), 2) if e not in removed]
    assert _divisible(7, edges) == (True, True)
    return _graph(7, edges)


def smaller():
    """The 6-cycle: divisible, and with no triangle to decompose into."""
    edges = [(i, (i + 1) % 6) for i in range(6)]
    assert _divisible(6, edges) == (True, True)
    return _graph(6, edges)
