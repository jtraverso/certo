"""sweep: when most of the counterexamples are the same one, relabelled.

Triples summing to 6, over ordered triples from 1..4. Ten of them fail, and
they are three objects: {1,2,3} in its six orderings, {1,1,4} in three, and
{2,2,2} alone. Reading ten ids tells you almost nothing; reading three
representatives with their sizes tells you what the obstruction is.

`canonicalize` says when two items are the same object relabelled. Nothing
here knows what the group is, and it does not need to.

The honest boundary, and `verify` repeats it: that two items sharing a
canonical form really are in the same orbit is the SPEC'S claim -- the
function is arbitrary Python. What is checked is that the decomposition holds
together: every counterexample in exactly one orbit, no shared
representatives, and the sizes adding up.

    certo sweep examples/sweep_orbits.py --cert out/orbits.json
    certo verify out/orbits.json
"""
from certo import DomainSpec


def spec():
    return DomainSpec(
        title="ordered triples, but the property only sees the multiset",
        items=[(a, b, c) for a in range(1, 5) for b in range(1, 5)
               for c in range(1, 5)],
        predicate=lambda t: sum(t) != 6,
        key=lambda t: "({},{},{})".format(*t),
        canonicalize=lambda t: tuple(sorted(t)),
        # `shrink` can start from any of them without a hand-written reduce.
        reduce="auto",
    )
