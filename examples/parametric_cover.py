"""A cover program's exact value on a whole family, and where the value changes.

The companion example `parametric_bound.py` is a PACKING: maximise, `<=` rows,
and the certificate bounds the optimum from above. Symmetrised covers are the
other half of the same duality and turn up at least as often -- a paper that
says "averaging over the automorphism group, an optimal fractional cover may be
assumed constant on each edge orbit" has just written one down.

This is that shape, at its smallest. Two edge orbits in a graph built from a
clique of size `p` joined to `q` independent vertices: the `p(p-1)/2` clique
edges carry weight `x`, the `pq` cross edges carry weight `y`. Two triangle
types exist, so

    minimise   C(p,2) x + p q y        subject to   3x >= 1,  x + 2y >= 1

and the claim in the source is a closed form with a THRESHOLD in it:

    optimum = (C(p,2) + pq) / 3     when q <= p - 1
            = C(p,2)                when q >= p - 1

Two branches, two different vertices of the same two-dimensional polytope, and
the papers that state this prove it the way one does at a blackboard: name the
vertices, observe the objective is affine, and say duality finishes it. What
duality finishes it WITH is never written down, because writing it down means
one dual per branch and a check that each stays feasible along its branch.

That is exactly a certificate, and there are two of them here.

    $ certo parametric examples/parametric_cover.py
    PROVED  [unsat]
      for all p >= 3, s >= 0, the optimum is at least 1/2*p^2 - 1/2*p
      columns: 2
      sense: min
      and that is every value with p >= 3, s >= 0 -- not a sample of them

`1/2*p^2 - 1/2*p` is `C(p,2)`, and on that branch the bound is not merely
valid but exact: it equals the optimum of the same program solved by an exact
rational simplex at every one of the branch's first 49 points.

THE THRESHOLD IS THE DUAL'S FEASIBILITY, and that is the part worth seeing.
The branch below is `q >= p - 1`, written as `q = p - 1 + s` with `s >= 0` so
that the regime is a ray and the shift test applies. Its dual puts everything
on the mixed triangle and nothing on the clique triangle:

    y(clique triangle) = 0,    y(mixed triangle) = C(p,2)

and its one non-trivial feasibility row is the cross-edge column,

    p q - 2 C(p,2)  =  p(q - p + 1)  =  p s   >=  0,

which is non-negative exactly when `q >= p - 1`. The dual stops being feasible
precisely where the closed form changes branch. Nothing was tuned to make that
happen; it is what a threshold in a piecewise-linear value function IS.

    $ certo verify cert.json
    VALID  parametric_bound certificate (checked by expanding polynomials and
                                         reading signs, no solver)
      [ok] every dual entry is non-negative on the whole ray  (negative: -)
      [ok] the dual is feasible on the whole ray, column by column
           (2 columns checked, failing: -)
      [ok] the bound is b.y, expanded  (1/2*p^2 - 1/2*p)
      optimum >= 1/2*p^2 - 1/2*p for all p >= 3, s >= 0

A COVER'S DUAL IS NOT A CONSTANT. In the packing shape the multipliers are
rates and a rational number each. Here the dual is a packing -- `C(p,2)`
triangles -- and a packing of a growing object grows with it. So dual entries
are polynomials in the parameters, and `y >= 0` becomes the same shift test as
every other row rather than a comparison.

WHAT THIS DOES AND DOES NOT SAY. It gives the LOWER bound, for every `p` and
every `q >= p - 1` at once. The matching upper bound is the feasible cover
`(x, y) = (1, 0)` evaluated directly, which needs no certificate because
substituting a point into an inequality is not a proof obligation. Together
they are the branch. And it says nothing about the other branch, which is a
second spec with a second dual: `uniform()` below, reachable by pointing
`spec()` at it. Its bound comes out as

    1/2*q^2 + 2/3*q*s + 1/6*s^2 + 1/2*q + 1/6*s

which is `(C(p,2) + pq)/3` with `p = q + 1 + s`, again exact against the
simplex at all 49 grid points. TWO specs, because they are two claims; one
command that certified both would be hiding the threshold rather than proving
it.
"""
from fractions import Fraction

from certo import ParametricSpec
from certo.polynomials import Poly

# The regime is `q >= p - 1`, so `s = q - p + 1` is the natural coordinate:
# on `s >= 0` the whole branch is a ray and the shift test applies.
RING = ("p", "s")
P = Poly.var(RING, "p")
S = Poly.var(RING, "s")
Q = P - Poly.const(RING, 1) + S          # q = p - 1 + s
C2 = P * (P - Poly.const(RING, 1)) * Poly.const(RING, Fraction(1, 2))


def K(c):
    return Poly.const(RING, c)


def saturated():
    """The branch `q >= p - 1`, where the optimum is C(p,2)."""
    return ParametricSpec(
        parameters={"p": 3, "s": 0},
        sense="min",
        # z = (x, y): the weight on a clique edge and on a cross edge.
        objective={"x": C2, "y": P * Q},
        constraints=[
            # three clique vertices
            ("clique_triangle", {"x": K(3)}, ">=", K(1)),
            # two clique vertices and one independent vertex
            ("mixed_triangle", {"x": K(1), "y": K(2)}, ">=", K(1)),
        ],
        # A feasible packing, read off the vertex (x, y) = (1, 0). Not a
        # constant: it is C(p,2) triangles.
        dual={"clique_triangle": K(0), "mixed_triangle": C2},
        title="the cover value of a complete-split family, on q >= p - 1",
    )


def uniform():
    """The other branch, `q <= p - 1`, where the optimum is (C(p,2)+pq)/3.

    Same program, opposite side of the threshold, so the ray runs the other
    way: `p = q + 1 + s` with `s >= 2` keeps `p >= 3` and `q <= p - 1`.
    """
    ring = ("q", "s")
    q = Poly.var(ring, "q")
    s = Poly.var(ring, "s")
    one = Poly.const(ring, 1)
    p = q + one + s
    c2 = p * (p - one) * Poly.const(ring, Fraction(1, 2))

    return ParametricSpec(
        parameters={"q": 0, "s": 2},
        sense="min",
        objective={"x": c2, "y": p * q},
        constraints=[
            ("clique_triangle", {"x": Poly.const(ring, 3)}, ">=", one),
            ("mixed_triangle", {"x": one, "y": Poly.const(ring, 2)}, ">=", one),
        ],
        # The uniform vertex (1/3, 1/3): both triangle types carry weight.
        dual={"clique_triangle": (c2 - p * q * Poly.const(ring, Fraction(1, 2)))
                                 * Poly.const(ring, Fraction(1, 3)),
              "mixed_triangle": p * q * Poly.const(ring, Fraction(1, 2))},
        title="the cover value of a complete-split family, on q <= p - 1",
    )


def spec():
    return saturated()
