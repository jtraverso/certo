"""Ten thousand linear programs, and the one that wins -- proved, not observed.

The shape comes from a script written by hand. Enumerate every bipartition of
a graph's edges, solve one linear program per bipartition in floating point,
take the largest, and then re-solve just that one in exact rationals to confirm
the number.

That confirms the WINNER and leaves the claim unmade. "No bipartition does
better" is a statement about all of them, and re-solving the best one says
nothing about the other 16,383. Reading a float maximum as THE maximum is the
same step `cover --optimize` was built for after a valid cover was read as an
optimal one.

    $ certo family examples/family_max.py
    SATISFIABLE  [sat]
      the maximum over 64 items is 5, attained at mask=000000
      argmax: mask=000000
      items: 64
      certificate: family_extremum (needs a solver, id abbdd604ffe87db7)

    $ certo verify out/family_max.json
    VALID  family_extremum certificate (by rebuilding each item's program from
                                        the spec and re-checking its vector)
      [ok] the item ids match the family they were recorded over
      [ok] every item in the family is accounted for  (64 of 64)
      [ok] the winner ATTAINS the value: an exact primal and dual that meet
      [ok] every other item is bounded by it, by weak duality
           (63 bounds checked; failing: -; never bounded: -)

TWO CLAIMS, AND THEY ARE NOT SYMMETRIC. That asymmetry is the whole design.

  The WINNER is attained: an exact primal and an exact dual whose values meet,
  so that item's optimum IS the claimed value rather than a bound on it.

  Every OTHER item is bounded: a dual `y >= 0` with `A^T y >= c` and
  `b.y <= V`. That is all it takes. A dual does not have to be OPTIMAL to
  bound -- it has to be feasible, and weak duality does the rest. So the
  expensive half of the search never has to be exact; only the checking does.

NOTHING STORES AN LP. Each item's program is rebuilt from `lp(item)` at
verification time, and the stored vector is checked against what comes out.
Carrying one program per item would be both enormous and unchecked: a dual for
a different item's program fits perfectly, which is exactly the hole a
branch-and-bound tree turned out to have.

So `verify` NEEDS THE SPEC FILE, the way a sweep's replay does, and says so
loudly when it does not have it instead of checking less while looking the
same:

    WARNING: the item programs are NOT stored, so without the spec the vectors
    here are numbers about nothing and NOTHING was checked

WHAT IT DOES NOT CLAIM: that the family is the one you meant. Completeness of
`items` is the spec's claim, the way a sweep's domain is, and `verify` repeats
that too.

The instance below is a small stand-in with the real structure: a fractional
packing whose available items depend on a binary choice per vertex, so every
one of the `2^6` choices is its own linear program and they genuinely differ.

WHAT IT COSTS, said rather than discovered: 64 items take about thirteen
seconds, because every one is solved EXACTLY. That is roughly a fifth of a
second each, so sixteen thousand of them is the better part of an hour. The
bound half does not have to be exact in principle -- any feasible dual works --
and making that cheap is the obvious next move if somebody needs the full
sweep. Right now the honest number is on the page instead of in a surprise.
"""
from itertools import combinations

from certo import FamilySpec, LPSpec

N = 6
EDGES = list(combinations(range(N), 2))


def _lp_for(mask: int) -> LPSpec:
    """One program per subset of vertices, marked by the bits of `mask`.

    A triangle may be packed only when its three vertices agree -- all marked
    or all unmarked. So the ITEM SET changes with the mask, not just the
    numbers, which is what makes the family worth a certificate rather than a
    single parametric bound.
    """
    marked = {v for v in range(N) if (mask >> v) & 1}
    lp = LPSpec(sense="max", title="mask={:06b}".format(mask))

    usable = [t for t in combinations(range(N), 3)
              if set(t) <= marked or not (set(t) & marked)]
    for t in usable:
        lp.variable("t{}{}{}".format(*t), 0, None)
    lp.objective({"t{}{}{}".format(*t): 1 for t in usable})

    # Each edge carries capacity one, shared by the triangles that use it.
    for e in EDGES:
        row = {"t{}{}{}".format(*t): 1 for t in usable
               if set(e) <= set(t)}
        if row:
            lp.constraint(row, "<=", 1, name="e{}{}".format(*e))
    if not usable:
        # An empty program is still a program, and its optimum is zero. Giving
        # it a variable keeps the shape uniform rather than special-casing it.
        lp.variable("none", 0, 0)
        lp.objective({"none": 1})
    return lp


def spec():
    return FamilySpec(
        items=list(range(1 << N)),
        lp=_lp_for,
        key=lambda m: "mask={:06b}".format(m),
        title="the best of 64 packing programs, and why none beats it",
    )
