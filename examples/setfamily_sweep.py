"""A sweep over set families, with the type doing the boilerplate.

Which 3-block families of pairs on 5 points are NOT intersecting? Ninety of
the 120 fail, and they are two objects relabelled: a triangle of pairs missing
one edge, and a pair plus a disjoint pair.

Note what the spec does not say. No `key`: a SetFamily names itself. No
`canonicalize` function: it has an exact canonical form under relabelling the
ground set. No `reduce`: it knows that one step smaller means dropping a block,
and then a point.

    certo sweep examples/setfamily_sweep.py --cert out/families.json
    certo verify out/families.json
"""
from certo import DomainSpec, SetFamily


def spec():
    return DomainSpec(
        title="intersecting families of three pairs on five points",
        items=lambda: list(SetFamily.all_families(5, 2, 3)),
        predicate=lambda f: f.intersecting(),
        canonicalize="auto",
        reduce="auto",
    )
