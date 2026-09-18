"""The numbers two geometric theorems consume, computed instead of assumed.

Two implications sit at the end of the route this feeds:

    a regular unimodular cone of height one  =>  smooth chart, SNC fibre
    discrepancy zero and multiplicity one    =>  crepant, reduced fibre

Neither is proved here and neither should be. They are theorems about
varieties; certo's part is the arrow before them.

WHAT THIS REPLACES. An audit of the second implication, written against certo
0.9, was three loose integers and two formulas taken as HYPOTHESES:

    assume("discrepancy_formula",  discrepancy == height - 1)
    assume("multiplicity_formula", multiplicity == height)

Those formulas are exactly the step where a cone becomes a number, and nothing
was computing them from a cone.

    $ certo cone examples/toric_cone.py
    PROVED  [unsat]
      4 generators in dimension 4: multiplicity 1 in declared lattice,
      height one: yes
      u = 1/4, 1/4, 1/4, 1/4
      b            height 1        discrepancy 0
      bary         height 1        discrepancy 0   (subdivision)

THE LATTICE IS DECLARED, NEVER GUESSED, AND IT CHANGES THE ANSWER. `spec()`
and `in_the_ambient()` are the SAME cone read two ways: multiplicity 1 in the
lattice its generators are primitive in, and 16 in `Z^4`. Neither is an error.
A multiplicity read without its lattice is half a sentence, and `verify` says
so every time.

CREPANT IS A QUESTION ABOUT WHAT A SUBDIVISION ADDS. A generator's discrepancy
is zero BY CONSTRUCTION wherever a height functional exists -- that is what
`<u, v> = 1` says. The first version of this reported the A1 singularity as
"crepant" on that basis, which said nothing and sounded like something. With
no subdivision named the answer is now `None`, and `singular()` is there to
keep it that way.

A NON-SIMPLICIAL CONE STILL GETS AN ANSWER. `no_height()` is three rays in the
plane: they span no full-dimensional simplicial cone, so there is no
multiplicity in this sense and the certificate says which quantity is missing
and why -- rather than refusing and losing the other three. Those three rays
also have no common height functional, which is the thing worth knowing about
them.

WHAT IS NOT CLAIMED. That multiplicity one gives a smooth chart. That
discrepancy zero gives a crepant modification. That any fibre is SNC or
reduced. Those are the theorems, they are why the proof assistant is there,
and a certificate that quietly asserted them would be the substitution this
project exists to refuse.
"""
from certo import ConeSpec

#: A local cell of a four-dimensional fan, as ray generators. The shape a
#: resolution produces: four rays and a barycentre to subdivide by.
RAYS = {
    "v0": (4, 0, 0, 0),
    "m01": (2, 2, 0, 0),
    "m02": (2, 0, 2, 0),
    "b": (1, 1, 1, 1),
}
ORDER = ["v0", "m01", "m02", "b"]


def spec():
    """Read in the lattice the generators are primitive in."""
    return ConeSpec(
        rays=RAYS, order=ORDER,
        lattice=[list(RAYS[r]) for r in ORDER],
        subdivision={"bary": (1, 1, 1, 1)},
        title="a local cell, in the lattice its generators generate")


def in_the_ambient():
    """The same cone read in Z^4, where the answer is a different number."""
    return ConeSpec(
        rays=RAYS, order=ORDER, lattice=None,
        subdivision={"bary": (1, 1, 1, 1)},
        title="the same cell, read in the ambient Z^4")


def singular():
    """A cone that is not regular in any reading: multiplicity 2."""
    return ConeSpec(
        rays={"a": (1, 0), "b": (1, 2)}, order=["a", "b"],
        title="the A1 singularity, multiplicity two")


def no_height():
    """Generators with no functional taking the value one on all of them."""
    return ConeSpec(
        rays={"a": (1, 0), "b": (0, 1), "c": (1, 1)}, order=["a", "b", "c"],
        title="three rays in the plane: no common height")
