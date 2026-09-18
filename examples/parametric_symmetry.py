"""By symmetry, for a FAMILY -- and the boundary is where it goes wrong.

`reduce` checks the averaging argument on one program. A write-up does not
symmetrise one program: it symmetrises `S(p,q)` and writes the answer as a
formula in `p` and `q`. Between the instances somebody ran and the symbolic
identity the proof uses there is a step, and that step is this command.

THE FAMILY. `S(p,q)` is a clique on `p` vertices joined to `q` independent
ones, and the question is the fractional triangle cover. Its automorphism
group is `S_p x S_q`, with two edge orbits -- `C(p,2)` clique edges and `pq`
cross edges -- so an optimal cover may be taken constant on each, and the
program collapses to two variables.

    $ certo reduce --parametric examples/parametric_symmetry.py
    PROVED  [unsat]
      the symbolic quotient agrees with the family at all 35 window points:
      2 orbits over parameters (p, q), in 4 regime(s) of the row conditions
      objects: 1/2*p^2 + p*q - 1/2*p
      regimes: ['(none)', 'KKI', 'KKK', 'KKK,KKI']

THE OBJECTIVE IS NOT DECLARED, and that is deliberate. Substituting one
variable per orbit into `sum_e z_e` sums each orbit, so the objective IS the
multiplicities. Declaring it separately would let the two disagree, and an
objective that disagrees with the orbit sizes is an accounting error no
amount of solving catches.

FOUR REGIMES, NOT ONE PROGRAM. A triangle type that does not exist
contributes no constraint, so the program's SHAPE changes at the boundary --
and the value function changes with it:

    (none)     p=2, q=0     no triangles at all
    KKI        p=2, q>=1    two clique vertices and one independent
    KKK        p>=3, q=0    three clique vertices
    KKK,KKI    p>=3, q>=1   both

The regimes are DERIVED from the declared conditions, not listed by hand, so
they can be compared against the branches of a piecewise closed form. A
formula with three branches over a program with four regimes is a formula
missing a case.

WHAT THE WINDOW IS FOR. `overstated()` is the same family with one condition
forgotten -- `3x >= 1` carried into `p = 2`, where there are no triangles on
three clique vertices to justify it. It is REFUTED at 7 of the 35 points,
the first being `p=2, q=0`. That is the whole value: the declaration is
FALSIFIABLE, and the boundary is where it falsifies.

Four other ways to get it wrong, each caught the same way: a multiplicity of
`pq/2` instead of `pq` (30 points), `p^2/2` instead of `C(p,2)` (35 points),
a coefficient of 3 where the row wants 2 (30 points), and an orbit declared
that does not exist (35 points).

TWO LEVELS, AND THE CERTIFICATE KEEPS THEM APART.

  SYMBOLIC, wherever the declaration holds: which orbits, which rows, what
  coefficients, which regimes. That the multiplicities account for every
  object. None of it needs an instance.

  PER INSTANCE, on the window: that the declared group really HAS these
  orbits at these sizes, and that the quotient averaging produces really is
  the symbolic one evaluated there. This needs the objects, and it is finite.

The second does not become the first by adding points, and `verify` says so
every time. What the window buys is falsifiability, not proof.

THE LEAN FILE SPLITS THE SAME WAY. `certo export --lean` writes the
multiplicity identity as a theorem `ring` closes outright, the window points
as examples `norm_num` closes, and exactly one `sorry` -- on the claim that
the orbit structure is uniform in the parameters, which certo checked on 35
points and nowhere else.

WHAT IS NOT CLAIMED. The VALUE. This says the quotient is the right program;
it says nothing about what its optimum is. Solve it with `opt` at a point, or
bound it for every parameter with `parametric`, which is the command built
for exactly that hand-off.
"""
import itertools
from fractions import Fraction

from certo import LPSpec, ParametricSymmetrySpec
from certo.polynomials import Poly

RING = ("p", "q")
P = Poly.var(RING, "p")
Q = Poly.var(RING, "q")


def K(c):
    return Poly.const(RING, c)


#: C(p,2) clique edges and pq cross edges. The objective is these, because
#: substituting one variable per orbit into `sum_e z_e` sums each orbit.
CLIQUE = (P * P - P).scaled(Fraction(1, 2))
CROSS = P * Q


# --- the family, built from the objects rather than from the formulas ------


def split_graph(p, q):
    """K_p joined to q independent vertices. Clique 0..p-1, rest p..p+q-1."""
    clique, indep = list(range(p)), list(range(p, p + q))
    edges = [tuple(sorted(e)) for e in itertools.combinations(clique, 2)]
    edges += [(a, b) for a in clique for b in indep]
    return clique, indep, sorted(set(edges))


def cover_lp(p, q):
    """The fractional triangle cover: one variable per EDGE, one row per
    triangle, and no symmetry assumed anywhere."""
    clique, indep, edges = split_graph(p, q)
    have = set(edges)
    prog = LPSpec(sense="min", title="cover of S({},{})".format(p, q))
    for e in edges:
        prog.variable("e{}_{}".format(*e), 0, None)
    prog.objective({"e{}_{}".format(*e): 1 for e in edges})
    for a, b, c in itertools.combinations(clique + indep, 3):
        if all(pair in have for pair in ((a, b), (a, c), (b, c))):
            prog.constraint(
                {"e{}_{}".format(*pair): 1
                 for pair in ((a, b), (a, c), (b, c))},
                ">=", 1, name="t{}_{}_{}".format(a, b, c))
    return prog


def generators(p, q):
    """S_p on the clique and S_q on the independent set, induced on edges."""
    clique, indep, edges = split_graph(p, q)

    def induced(sigma):
        return {"e{}_{}".format(*e):
                "e{}_{}".format(*sorted((sigma.get(e[0], e[0]),
                                         sigma.get(e[1], e[1]))))
                for e in edges}

    gens = {}
    if p >= 2:
        gens["clique_swap"] = induced({0: 1, 1: 0})
    if p >= 3:
        gens["clique_cycle"] = induced({v: (v + 1) % p for v in clique})
    if q >= 2:
        gens["indep_swap"] = induced({indep[0]: indep[1], indep[1]: indep[0]})
    if q >= 3:
        gens["indep_cycle"] = induced(
            {indep[i]: indep[(i + 1) % q] for i in range(q)})
    return gens


def spec():
    return ParametricSymmetrySpec(
        parameters=RING,
        orbits={"clique": CLIQUE, "cross": CROSS},
        sense="min",
        rows=[
            # three clique vertices: only when there are three of them
            ("KKK", {"clique": K(3)}, ">=", K(1), [P - K(3)]),
            # two clique vertices and one independent vertex
            ("KKI", {"clique": K(1), "cross": K(2)}, ">=", K(1),
             [P - K(2), Q - K(1)]),
        ],
        instance=lambda p, q: (cover_lp(p, q), generators(p, q)),
        window=[(p, q) for p in range(2, 7) for q in range(0, 7)],
        title="complete split graph under S_p x S_q",
    )


def overstated():
    """The same family with one condition dropped: what the command is for.

    `3x >= 1` comes from three mutually adjacent clique vertices. Carry it
    into `p = 2` and the program has a constraint about triangles that are
    not there -- which is precisely the error the boundary regimes hide.
    """
    base = spec()
    base.rows = [("KKK", {"clique": K(3)}, ">=", K(1), []), base.rows[1]]
    base.title = "the same family, with `p >= 3` forgotten"
    return base
