"""The quotient as an EQUIVALENCE, not as two optima that agree.

`reduce` checks a symmetry argument and then compares optima. Comparing two
computed optima does not show a reduction is correct -- it shows two numbers
came out the same, which is also what a wrong reduction with a compensating
error does. The stronger statement is the one a formalisation wants, and it
turns out to be easier:

    the physical program and the quotient have the SAME SET of attainable
    values, by an explicit projection and lifting that preserve the objective

    $ certo quotient examples/equitable_quotient.py
    PROVED  [unsat]
      226 rows and 3147 columns reduce to 13 and 49, with the SAME attainable
      values: projection and lifting both preserve feasibility and the
      objective

Equality of optima follows, and the proof needs no duality. `Proj(x)_j` is the
total mass of a column class, `Lift(z)_C = z_j / M_j` spreads a class mass
evenly, and `Proj(Lift(z)) = z`.

THE FAMILY is six vertex classes: three forming a clique between them and
internally, and three host classes each complete to the core classes it serves
and to nothing else. Objects are the K3 and K4 subgraphs, gains two and five,
capacity one on every edge. At `t = 2` that is 30 vertices, 226 edges and 3147
cliques, and the quotient is 13 by 49.

THE PARTITION IS AN INPUT, and that is the design. A group action produces
one; so does a colour refinement; so does somebody who knows what the classes
are. Separating the finite-sum core from the group theory is what a proof
assistant wants anyway, and it means a partition nobody can name a group for
is still certifiable.

TWO REGULARITIES, AND THEY ARE DIFFERENT QUANTITIES. This is the part that is
easy to get wrong, and getting it wrong produced a quotient reporting 6 where
the physical program gives 4:

    H_ij   one resource of class i is used by this much of object class j
    B_ij   one object of class j uses this much of resource class i

Lifting needs H -- every physical row must see the same load -- and the
quotient's own matrix needs B. The double count `N_i . H_ij = M_j . B_ij` ties
them, so it is a CONSEQUENCE of the two rather than a third hypothesis, and it
is checked anyway because it is exactly what catches one having been used as
the other. At `t = 2` there are 133 non-zero class pairs; on the stable branch
the grid is 13 by 55.

THE CONSTANCY CHECKS ARE NOT A FORMALITY. `capacity_breaks_the_class()` is K4
with triangles only and one edge dropped to capacity zero. Intact, the
physical value is 4 and so is the quotient's. Capped, the physical value is 2
-- and aggregating over a class that now mixes capacities zero and one would
report 10/3. The partition is REFUSED, naming `e01` and `e02`:

    class `edge` is not constant in capacity: `e01` has 0 and `e02` has 1

WHAT IS NOT CLAIMED: INTEGRALITY. The equivalence is between the FRACTIONAL
programs. On that same intact K4 the fractional programs both give 4 while the
integer packing gives 2, so an integer orbit mass need not lift to integer
objects and a quotient certificate is never evidence about an integer program.
`verify` says so every time.
"""
import itertools
from fractions import Fraction

from certo import EquitableQuotientSpec, LPSpec

#: Six vertex classes with sizes `c*t`. The core three are pairwise adjacent
#: and internally complete; each host class is complete to the core classes it
#: serves and to nothing else, hosts included.
CLASSES = ("A", "B", "C", "F", "U", "V")
SIZE = {"A": 1, "B": 3, "C": 2, "F": 1, "U": 5, "V": 3}
NEIGHBOURS = {
    "A": {"A", "B", "C", "F", "V"},
    "B": {"A", "B", "C", "F", "U"},
    "C": {"A", "B", "C", "F", "U", "V"},
    "F": {"A", "B", "C"},
    "U": {"B", "C"},
    "V": {"A", "C"},
}
GAIN = {3: 2, 4: 5}
T = 2


def _graph(t):
    verts = [(c, i) for c in CLASSES for i in range(SIZE[c] * t)]
    adj = {frozenset(e) for e in itertools.combinations(verts, 2)
           if e[1][0] in NEIGHBOURS[e[0][0]]}
    return verts, adj


def _name(vs):
    return "_".join(sorted("{}{}".format(*v) for v in vs))


def physical(t=T):
    """One variable per K3 or K4, one row per edge, capacity one.

    No symmetry anywhere: the program is written out from the objects, which
    is what makes the partition below something to CHECK rather than a
    restatement of how it was built.
    """
    verts, adj = _graph(t)
    cliques = [(k, S) for k in (3, 4)
               for S in itertools.combinations(verts, k)
               if all(frozenset(p) in adj for p in itertools.combinations(S, 2))]

    p = LPSpec(sense="max", title="G_{}: physical packing".format(t))
    for _k, S in cliques:
        p.variable("x_" + _name(S), 0, None)
    p.objective({"x_" + _name(S): GAIN[k] for k, S in cliques})

    touching = {}
    for _k, S in cliques:
        for pair in itertools.combinations(S, 2):
            touching.setdefault("e_" + _name(pair), []).append("x_" + _name(S))
    for e in sorted(adj, key=_name):
        row = touching.get("e_" + _name(e))
        if row:
            p.constraint({c: 1 for c in row}, "<=", 1, name="e_" + _name(e))
    return p, cliques, touching


def partition(t=T):
    """The classes the group induces, written down as plain data.

    An edge class is the unordered pair of vertex classes; a clique class is
    the multiplicity vector. Nothing here knows about a group -- the partition
    is the input, and whether it supports the equivalence is the question.
    """
    _p, cliques, touching = physical(t)
    rows = {}
    for name in touching:
        parts = name[2:].split("_")
        rows[name] = "".join(sorted(s[0] for s in parts))
    columns = {}
    for k, S in cliques:
        alpha = tuple(sum(1 for v in S if v[0] == c) for c in CLASSES)
        columns["x_" + _name(S)] = "k{}_{}".format(k, "".join(map(str, alpha)))
    return rows, columns


def spec():
    p, _c, _t = physical()
    rows, columns = partition()
    return EquitableQuotientSpec(
        lp=p, rows=rows, columns=columns,
        title="G_2: six vertex classes, cliques as objects")


def capacity_breaks_the_class():
    """The acceptance control: one resource at a different capacity.

    On K4 with triangles only, the physical value is 4 and so is the
    quotient's. Drop one edge to capacity zero and the physical value is 2 --
    but aggregating over a class that now mixes two capacities would report
    10/3. The partition must be REFUSED, and it is.
    """
    verts = list(range(4))
    tris = list(itertools.combinations(verts, 3))
    p = LPSpec(sense="max", title="K4, triangles, one edge capped")
    for s in tris:
        p.variable("x{}{}{}".format(*s), 0, None)
    p.objective({"x{}{}{}".format(*s): 2 for s in tris})
    for e in itertools.combinations(verts, 2):
        p.constraint({"x{}{}{}".format(*s): 1 for s in tris
                      if e[0] in s and e[1] in s},
                     "<=", 0 if e == (0, 1) else 1,
                     name="e{}{}".format(*e))
    return EquitableQuotientSpec(
        lp=p,
        rows={"e{}{}".format(*e): "edge"
              for e in itertools.combinations(verts, 2)},
        columns={"x{}{}{}".format(*s): "tri" for s in tris},
        title="a class that mixes two capacities")


_ = Fraction
