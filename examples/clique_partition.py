"""Somebody hands you a clique partition. Is it one, and how large?

Two things have to be true and neither is visible by looking:

  every part really is a CLIQUE -- all the pairs among its vertices are edges
  of the graph, not just some of them;

  every edge is covered EXACTLY once -- not zero times, which makes it not a
  cover, and not twice, which makes the count a lie.

Checking both is counting. No solver, no search, and no trust in whatever
produced the partition, which is exactly why it belongs in a certificate.

The instance here is the classic one: K7, whose 21 edges partition into 7
triangles. That is the Steiner triple system of order 7, and it is worth
using because anyone can check a line of it by hand and because it is tight --
21 edges, 7 parts, 3 edges each, nothing to spare.

    $ certo cover examples/clique_partition.py
    PROVED  [unsat]
      an EXACT COVER: 7 parts, every one of the 21 elements in exactly one
      certificate: exact_cover (no solver needed)

    $ certo verify out/clique_partition.json
    VALID  exact_cover certificate (checked by counting, no solver)
      [ok] every element of the universe is covered  (0 missed: -)
      [ok] no part covers anything outside the universe  (0 foreign elements)
      [ok] and covered exactly once  (0 covered more than once: -)
      [ok] the declared number of parts is the number of parts
      [ok] every part really is a clique of the graph  (0 parts are not)

THE THREE WAYS IT GOES WRONG all report differently, because they are
different problems:

  A part that is not a clique is not a cover question at all -- it is a
  statement about the graph, and the run stops with the offending pairs named
  rather than producing a certificate for something that is not a clique
  partition.

  An edge covered twice is REFUTED: the parts are cliques and they do cover,
  but "exactly once" is false, and the size is therefore not what it looks
  like. With `exact=False` the same data is a valid cover, and the certificate
  would say so in those words.

  An edge covered zero times is refuted the same way and named.

WHAT THIS DOES NOT SAY is that 7 is the smallest possible. It is an upper
bound with an artefact attached. The other half -- that no smaller partition
exists -- is a lower bound, and the exact rational dual from `certo opt` on
the same edge set is one. Where the two meet, the number is proved, and that
is the pairing `opt --gap` already makes for packings.

Finding a minimum clique partition is NP-hard, and this is deliberately not
that. Bring your own partition, from whatever found it.
"""
from itertools import combinations

from certo import CoverSpec

#: The Fano plane, read as seven triangles on seven points. Every pair of
#: points lies in exactly one line, which is precisely the property being
#: certified -- so the example is its own smallest interesting case.
FANO = [(0, 1, 3), (1, 2, 4), (2, 3, 5), (3, 4, 6),
        (4, 5, 0), (5, 6, 1), (6, 0, 2)]


def spec():
    return CoverSpec(
        universe=list(combinations(range(7), 2)),
        parts=FANO,
        cliques=True,
        max_size=3,
        title="K7 partitioned into 7 triangles",
    )
