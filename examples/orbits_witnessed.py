"""Forty copies of one object, and a permutation proving each one is it.

A combinatorial search produces relabelled copies of the same object by the
hundred. `canonicalize` collapses them: hand over a function from item to a
hashable form, equal exactly for items in the same orbit, and a sweep that
reported forty counterexamples reports one, forty times over.

That works, and it asks to be believed. `canonicalize` is arbitrary Python,
so "these forty share a canonical form" is the SPEC'S CLAIM, and all a
certificate could check was that the arithmetic of the decomposition held
together -- the counts add up, the representatives are distinct, each one
belongs to the orbit it heads. None of that is the question.

    labelling=lambda item: {source_point: label, ...}

is the other bargain. Hand over the PERMUTATION instead of the form: certo
applies it, the result is the canonical form, and the permutation travels in
the certificate. "Member and representative are the same object relabelled"
stops being a claim and becomes an arithmetic fact anybody can re-run.

    $ certo sweep examples/orbits_witnessed.py
    REFUTED  [sat]
      REFUTED: 40 counterexamples out of 40 examined -- 40 labelled,
      1 up to symmetry

    $ certo verify out/orbits_witnessed.json
      [ok] the orbits partition the domain  (1 orbits covering 40 of 40 items)
      [ok] each orbit has its own representative
      [ok] each representative belongs to its orbit
      [ok] every member of every orbit carries its permutation
           (40 witnesses; orbits missing some: -)
      [ok] each member IS the representative relabelled, by re-applying the
           stored permutation  (40 re-applied, 0 carried but not decodable,
           failing: -)
      WARNING: what the witnesses show is that members of an orbit are the
      SAME object relabelled. They do not show that two different
      representatives are different objects -- that needs the labelling to be
      isomorphism-invariant, which is the part certo did not compute and
      cannot check.

The first three lines were there before and are arithmetic about the
decomposition. The two after them are new and are about the OBJECTS.

THE OBJECT HERE IS THE ONE THAT FORCED IT. A 1-factorisation of K6: the
fifteen edges as the ground set, the five perfect matchings as the blocks.
Colour refinement returns ONE class, because every edge looks like every other
one -- the object is vertex-transitive, which is exactly the case refinement
cannot help with. So certo's own canonical form refuses:

    this family is too symmetric to canonicalise exactly on 15 points
    (over 200000 candidate relabellings). Refusing rather than guessing.

and it is right to. 15! is 1,307,674,368,000. Nor does knowing the group
rescue it: the automorphism group has 120 elements, so quotienting by ALL of
it still leaves 10,897,286,400 cosets, fifty-four thousand times over the cap.
Coset pruning is not the missing ingredient, because |Aut| is small and n! is
not.

WHICH IS THE POINT. Computing a canonical labelling well is a hard search, and
a tool built for it does it far better than this one ever will. So nauty finds
the labelling, certo checks it, and the artefact carries both -- the same
division of labour `parametric` makes with its dual and `farkas` with its
multipliers. There is no cap on this route, because nothing is searched.

WHAT IS CHECKED, exactly:

  * the permutation is a BIJECTION of the ground set. A map that is not is
    not a relabelling: it renames the object into a different one, and the
    form it produces would be of something else;
  * every member of every orbit carries one -- a witness for some of them
    makes the orbit checkable in part, which is the same as not checkable;
  * applying it lands on the same object the representative's own
    permutation lands on.

WHAT IS NOT, and is said in a warning rather than implied: that two DIFFERENT
representatives are different objects. Every witness here shows two items are
the same; nothing here shows two items are not. That would need the labelling
to be isomorphism-invariant, which is the part certo did not compute and
cannot check.

`canonicalize` and `labelling` are refused together. One asks to be believed
and the other asks to be checked, and running both would leave it unclear
which one the orbits came from.
"""
import random
from itertools import combinations

from certo import DomainSpec
from certo.structures import SetFamily

#: The ground set is the fifteen edges of K6.
EDGES = list(combinations(range(6), 2))
INDEX = {e: i for i, e in enumerate(EDGES)}


def _one_factorisation() -> SetFamily:
    """K6 split into five perfect matchings, by the standard rotation."""
    blocks = []
    for r in range(5):
        matching = [(5, r)] + [tuple(sorted(((r + k) % 5, (r - k) % 5)))
                               for k in (1, 2)]
        blocks.append(sorted(INDEX[tuple(sorted(e))] for e in matching))
    return SetFamily(15, blocks)


def _relabelled_copies(n=40, seed=7):
    """One object, `n` times, under random relabellings of the ground set.

    Each copy is paired with the permutation that carries it BACK -- which is
    what a canonical labelling is: the map from the object's own points to the
    labels its canonical form uses. Here it is known by construction. In real
    use it comes from nauty, and certo checks it either way.
    """
    base = _one_factorisation()
    rng = random.Random(seed)
    out = {}
    for _ in range(n):
        order = list(range(15))
        rng.shuffle(order)
        forward = dict(enumerate(order))            # base's point -> copy's
        copy = base.relabelled(forward)
        back = {label: source for source, label in forward.items()}
        out[copy] = {p: back[p] for p in range(15)}
    return out


_COPIES = _relabelled_copies()


def spec():
    return DomainSpec(
        items=list(_COPIES),
        # Everything fails, on purpose. The orbit structure certo reports is
        # the structure of what FAILED -- which is the question, and the
        # reason the decomposition exists. A passing sweep has no
        # counterexamples to collapse and reports no orbits.
        predicate=lambda f: False,
        key=lambda f: f.key(),
        labelling=lambda f: _COPIES[f],
        title="forty labellings of one object, each with the permutation",
    )
