"""A valid cover, and how far it is from the minimum. Both, in one command.

`cover` certifies that a partition is real and says how large it is. That is
an UPPER bound, and a user read one as an optimum -- reporting a construction
of 780 parts where the obvious one uses about 41, and calling the difference a
property of the graph rather than a fact about their construction.

Nothing in the cover certificate was wrong. The missing half was the lower
bound, and it lived in `opt` over an LP they had to rebuild by hand.

    $ certo cover examples/cover_optimize.py --optimize --prove-optimal
    PROVED  [unsat]
      an EXACT COVER: 21 parts, every one of the 21 elements in exactly one

      and how close that is to the minimum:
        your cover      21 parts   (an UPPER bound, certified above)
        relaxation      7   (a LOWER bound, exact rational dual -- fractional,
                             so not a cover you can build)
        integer optimum 7   (PROVED by branch and bound)
      your cover uses 21; the minimum is 7.

The instance is K7 covered by its 21 single edges. Perfectly valid, and three
times worse than the Fano plane's seven triangles -- which is the same shape
of mistake, small enough to see at a glance.

`candidates` IS REQUIRED, and refused rather than guessed. A cover is only
minimal relative to what you were willing to use: here, single edges and
triangles. The set of all cliques of a graph is usually enormous and almost
never what anyone meant, so assuming it would answer a question nobody asked.

THREE NUMBERS, THREE STATUSES, and the labels travel with them:

  your cover is an upper bound and it is CERTIFIED -- the parts are cliques
  and every edge is covered exactly once;

  the relaxation is a lower bound with an exact rational dual, and it is
  FRACTIONAL, so it is a number and not a cover you can build;

  the optimum is PROVED, and only appears when branch and bound finishes. When
  it does not, what comes back is the incumbent, the bound and the gap,
  labelled inconclusive -- because a search that runs out still knows those.

The lower bound here needs an exact dual on a 98-row degenerate LP, which is
the case where rounding a float solver's dual stops working: 49 tight rows and
7 active variables leave about 10^8 candidate bases. `certo` solves that dual
with an exact rational simplex instead, and then checks it the same way it
checks a rounded guess.
"""
from itertools import combinations

from certo import CoverSpec


def spec():
    edges = list(combinations(range(7), 2))
    triangles = [list(c) for c in combinations(range(7), 3)]

    return CoverSpec(
        universe=edges,
        # Valid, and nowhere near minimal: every edge as its own part.
        parts=[list(e) for e in edges],
        # What we were willing to use. Without this there is nothing to be
        # minimal with respect to.
        candidates=[list(e) for e in edges] + triangles,
        cliques=True,
        title="a valid cover, and the minimum it is three times away from",
    )
