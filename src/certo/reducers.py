"""Standard `reduce` functions for `shrink`.

`shrink` needs to know what "one step smaller" means, and there is no answer
that is right for every domain -- so it used to demand one. That is honest and
it is also friction: writing `lambda s: [s - {x} for x in s]` by hand, for the
tenth time, is not where the thinking is.

These are the shapes that keep coming back. They are defaults, not guesses: a
spec that passes its own `reduce` is untouched, and `auto` refuses rather than
inventing a reduction for a type it does not recognise.

Two properties every reducer here has, because `shrink` depends on both:

  * It returns items that are STRICTLY smaller under some measure, so the
    descent terminates.
  * It is DETERMINISTIC and ordered, so the recorded descent -- which stores
    the index taken at each step -- replays to the same place.
"""
from __future__ import annotations

from .i18n import t


def sets(item):
    """Drop one element. For a set, frozenset or anything set-like."""
    ordered = sorted(item, key=repr)
    kind = type(item)
    return [kind(x for x in ordered if x != drop) for drop in ordered]


def sequences(item):
    """Drop one element, keeping order. For lists and tuples."""
    kind = type(item)
    return [kind(item[:i] + item[i + 1:]) for i in range(len(item))]


def decrement(item, floor=0):
    """Lower one coordinate by one. For tuples of integers -- parameter grids.

    The natural reduction on a grid is not "drop a coordinate" but "make one
    of them smaller", which is why sequences() is the wrong default here.
    """
    if isinstance(item, int):
        return [item - 1] if item > floor else []
    out = []
    for i, v in enumerate(item):
        if isinstance(v, int) and v > floor:
            out.append(tuple(item[:i]) + (v - 1,) + tuple(item[i + 1:]))
    return [type(item)(x) for x in out] if not isinstance(item, tuple) else out


def graphs(item, edges_too=False):
    """Delete one vertex; optionally one edge as well.

    Vertices first and edges second is deliberate: a vertex takes more away,
    so a descent that tries it first reaches a small witness in fewer steps,
    and 1-minimal under vertex deletion is what a write-up usually wants.

    Reuses `shrink`'s own deletion helpers rather than reimplementing them:
    two definitions of "delete a vertex" that drift apart would make the
    recorded descent replay to a different graph.
    """
    from .engines.shrink import _delete_edge, _delete_vertex

    out = [_delete_vertex(item, v) for v in range(item.n)]
    if edges_too:
        out += [_delete_edge(item, e) for e in item.edges()]
    return out


def masks(item, width=None):
    """Clear one set bit. For integers used as subset masks."""
    n = width if width is not None else max(item.bit_length(), 1)
    return [item & ~(1 << i) for i in range(n) if item >> i & 1]


def hypotheses(item):
    """Drop one named hypothesis. For a list of (name, value) pairs."""
    return sequences(item)


def auto(item):
    """Pick a reducer from the item's type, or say it cannot.

    Refusing is the point. A silent wrong reduction produces a "minimal"
    witness that is minimal for the wrong relation, and nothing downstream
    would notice.
    """
    from .graphs import Graph

    if isinstance(item, Graph):
        return graphs(item)
    if isinstance(item, (set, frozenset)):
        return sets(item)
    if isinstance(item, tuple):
        # A tuple of integers is a parameter point, not a collection: making a
        # coordinate smaller is the reduction, not deleting a coordinate.
        if item and all(isinstance(v, int) for v in item):
            return decrement(item)
        return sequences(item)
    if isinstance(item, list):
        return sequences(item)
    if isinstance(item, int) and not isinstance(item, bool):
        return decrement(item)
    raise TypeError(t("reducers.unknown", type=type(item).__name__))


CATALOGUE = {
    "auto": auto,
    "sets": sets,
    "sequences": sequences,
    "decrement": decrement,
    "graphs": graphs,
    "masks": masks,
    "hypotheses": hypotheses,
}


def resolve(reduce):
    """A callable, or a name from the catalogue. Anything else is an error."""
    if callable(reduce):
        return reduce
    if isinstance(reduce, str):
        try:
            return CATALOGUE[reduce]
        except KeyError:
            raise ValueError(t("reducers.no_such", name=reduce,
                               known=", ".join(sorted(CATALOGUE))))
    raise TypeError(t("reducers.bad", got=type(reduce).__name__))
