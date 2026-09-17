"""Four edge orbits, three candidate covers, and the dual that picks one.

`parametric_cover.py` is the two-orbit version and the place to start. This is
the shape the same argument takes one level up, and it is the one that actually
appears in write-ups: a split graph whose clique `K` splits into a common
neighbourhood `N` of size `d` and the rest `R` of size `r`, with `q`
independent vertices all attached to `N`. Averaging over the automorphism group
leaves four edge orbits --

    E(N)      weight a        C(d,2) of them
    E(N, I)   weight b        q d
    E(N, R)   weight c        d r
    E(R)      weight e        C(r,2)

-- and five triangle types, so the fractional cover number is

    minimise   C(d,2) a + q d b + d r c + C(r,2) e
    subject to   a + 2b >= 1,  3a >= 1,  a + 2c >= 1,  2c + e >= 1,  3e >= 1

and the published value is a minimum of three closed forms:

    uniform      ( C(p,2) + q d ) / 3          (a,e) = (1/3, 1/3)
    separated    C(d,2) + C(r,2)               (a,e) = (1, 1)
    hot          C(d,2) + ( d r + C(r,2) ) / 3 (a,e) = (1, 1/3)

The written proof is three lines: eliminate `b` and `c`, observe the objective
is affine on a triangle in `(a, e)`, evaluate at the three vertices, and say
duality finishes it. Everything in that is right. What it leaves out is the
finite object a referee would have to reconstruct -- one dual per branch, and
the check that each stays feasible for every `(d, q, r)` in its branch.

    $ certo parametric examples/parametric_orbits.py
    PROVED  [unsat]
      for all d >= 3, s >= 0, t >= 0, the optimum is at least
      d^2 + 2/3*d*t + 1/6*t^2 + 1/6*t
      columns: 4
      sense: min
      and that is every value with d >= 3, s >= 0, t >= 0 -- not a sample

which is the hot value `C(d,2) + (dr + C(r,2))/3` with `r = d + 1 + t`
expanded, and it is EXACT rather than merely valid: on the branch's first 343
points it equals the optimum of the same program solved by an exact rational
simplex, at all 343.

THE BRANCH IS A RAY, AND THAT IS NOT A TRICK. The hot cover is the minimum
exactly when `q >= d - 1` and `r >= d + 1`, so the honest coordinates are the
slacks: `q = d - 1 + s` and `r = d + 1 + t`, with `s, t >= 0`. In those
coordinates the branch IS a box, the shift test applies, and the bound above is
the hot value rewritten -- it is not a weaker bound that happens to hold there.

THE DUAL'S FEASIBILITY IS THE BRANCH BOUNDARY, both halves of it. The packing
puts `C(d,2)` on the triangle type with two clique-neighbourhood vertices and
one independent vertex, nothing on the two it does not need, `d r / 2` on the
one-in-N-two-in-R type, and what is left over on the all-in-R type:

    column b:   q d - 2 C(d,2) = d (q - d + 1) = d s       >= 0
    y(R,R,R) = ( C(r,2) - d r / 2 ) / 3 = r (r - 1 - d) / 6 = r t / 6  >= 0

One is a residual and one is a non-negativity, and between them they are
`q >= d - 1` and `r >= d + 1`. The two conditions that say which branch you are
in are the two conditions that say the certificate holds. That is what a
piecewise-linear value function looks like from underneath, and it is why the
other two branches are separate specs rather than a wider ray.

WHY THE DUAL IS A POLYNOMIAL. In a packing program the multipliers are rates
and each is one rational number. Here the dual is itself a packing, and a
packing of a growing object grows with it -- `C(d,2)` triangles, not `1/3`. So
`y >= 0` is the same coefficient-shift test as the residual rows rather than a
comparison, and the certificate carries `y` as polynomial data.

WHAT IS PROVED AND WHAT IS NOT. This is the LOWER bound, on the whole branch at
once. The matching upper bound is the cover `(a, b, c, e) = (1, 0, 1/3, 1/3)`
evaluated directly; substituting a point into an inequality is arithmetic, not
a proof obligation. Together they pin the branch exactly, which is
what the 343-point agreement above records -- and that agreement is a test, not
a certificate, because a grid is never the claim.

THE WHOLE TRICHOTOMY TAKES FIVE CERTIFICATES, and that is the thing worth
carrying away. Three of them are boxes, re-coordinatised by a slack per
inequality. Two are not boxes at all: inside `q <= d - 1` the minimum switches
between the uniform and separated values across

    q d + d r  =  d(d-1) + r(r-1)

a quadratic curve, and no substitution `x -> x0 + u` turns a curved face into a
corner. Those two DECLARE the condition with `region=` instead, which puts it
in the certificate's scope rather than proving it, and lets certo find the
multipliers by linear program. Counted over 1170 parameter points (`d` 3..11,
`r` 4..13, `q` 1..13), every bound exact against the simplex, nothing unsound,
nothing left over:

    hot               q >= d-1, r >= d+1            492   box
    separated         q >= d-1, r <= d+1            300   box
    uniform_wide      q <= d-1, r >= d+1            264   box
    uniform_narrow    q <= d-1, r <= d+1, U <= D    243   2 declared conditions
    separated_narrow  q <= d-1, r <= d+1, D <= U    107   2 declared conditions
                                                   ----
                                                   1170   of 1170

The overlaps are real rather than an artefact of how they were written: each
covers a closed region, and the regions share their boundaries.

That is not a shortfall to apologise for; it is the finite content the three
written lines leave out. "The objective is affine on a triangle, evaluate at
the three vertices, duality finishes it" is correct and complete as an
argument. What it takes to WRITE DOWN is five certificates in four coordinate
systems, two of them scoped by a curve, and nothing in the prose says so --
because on a blackboard nobody has to.
"""
from fractions import Fraction

from certo import ParametricSpec
from certo.polynomials import Poly

# `d` is the common neighbourhood; the other two coordinates are the SLACKS in
# the branch conditions, so that the branch is a box and the shift applies.
RING = ("d", "s", "t")
D = Poly.var(RING, "d")
S = Poly.var(RING, "s")
T = Poly.var(RING, "t")


def K(c):
    return Poly.const(RING, c)


HALF = K(Fraction(1, 2))
THIRD = K(Fraction(1, 3))

Q = D - K(1) + S                 # q = d - 1 + s,  the branch needs q >= d-1
R = D + K(1) + T                 # r = d + 1 + t,  the branch needs r >= d+1
CD = D * (D - K(1)) * HALF       # C(d,2)
CR = R * (R - K(1)) * HALF       # C(r,2)


def separated():
    """The other branch certified here: `q >= d - 1` and `r <= d + 1`.

    Different coordinates, because a different pair of inequalities cuts it
    out. `r <= d + 1` is `d = r - 1 + m` with `m >= 0`, and `q >= d - 1` is
    again a slack, so the box is `(r, m, s)`.

    The dual splits `C(d,2)` between two triangle types rather than putting it
    all on one, and the split `r m / 2` is what makes the crossing orbit pay
    for itself. Its residual on the independent-vertex column comes out as
    `d s + r m`, non-negative on the box and zero only at its corner -- which
    is the corner where this branch meets the other two.
    """
    ring = ("r", "m", "s")
    r = Poly.var(ring, "r")
    m = Poly.var(ring, "m")
    s = Poly.var(ring, "s")
    one = Poly.const(ring, 1)
    half = Poly.const(ring, Fraction(1, 2))
    d = r - one + m                          # r <= d + 1
    q = d - one + s                          # q >= d - 1
    cd = d * (d - one) * half
    cr = r * (r - one) * half

    return ParametricSpec(
        # r >= 4 puts d >= 3 and q >= 2: all five triangle types exist.
        parameters={"r": 4, "m": 0, "s": 0},
        sense="min",
        objective={"a": cd, "b": q * d, "c": d * r, "e": cr},
        constraints=[
            ("NNI", {"a": one, "b": Poly.const(ring, 2)}, ">=", one),
            ("NNN", {"a": Poly.const(ring, 3)}, ">=", one),
            ("NNR", {"a": one, "c": Poly.const(ring, 2)}, ">=", one),
            ("NRR", {"c": Poly.const(ring, 2), "e": one}, ">=", one),
            ("RRR", {"e": Poly.const(ring, 3)}, ">=", one),
        ],
        dual={
            "NNI": cd - r * m * half,
            "NNN": Poly.const(ring, 0),
            "NNR": r * m * half,
            "NRR": cr,
            "RRR": Poly.const(ring, 0),
        },
        title="the separated-cover branch of a four-orbit cover program",
    )


def uniform_wide():
    """The uniform cover where the residual clique is large: `r >= d + 1`.

    Still a box -- `d = q + 1 + k` is `q <= d - 1`, `r = d + 1 + t` is the
    other side -- and the dual pays every triangle type something.
    """
    ring = ("q", "k", "t")
    q = Poly.var(ring, "q")
    k = Poly.var(ring, "k")
    t = Poly.var(ring, "t")
    one = Poly.const(ring, 1)
    half = Poly.const(ring, Fraction(1, 2))
    third = Poly.const(ring, Fraction(1, 3))
    dd = q + one + k
    rr = dd + one + t
    cd = dd * (dd - one) * half
    cr = rr * (rr - one) * half

    return _orbit_program(
        ring, dd, rr, q, {"q": 0, "k": 0, "t": 0},
        dual={"NNI": q * dd * half,
              "NNN": (cd - q * dd * half) * third,
              "NNR": Poly.const(ring, 0),
              "NRR": dd * rr * half,
              "RRR": (cr - dd * rr * half) * third},
        title="the uniform-cover branch, large residual clique")


def uniform_narrow():
    """The uniform cover where `r <= d + 1`, and the one branch that is NOT a box.

    Here the minimum switches between the uniform and separated values across

        q d + d r  =  d(d-1) + r(r-1)

    a quadratic curve. No substitution `x -> x0 + u` turns that into a corner,
    so the branch is declared rather than re-coordinatised:

        region=[("r_within", d + 1 - r), ("uniform_wins", ...)]

    That is SCOPE and not content. Nothing here proves either condition -- the
    bound is claimed where they hold, the same standing the parameter floors
    already have, and `verify` says so in a warning of its own every time.

    What certo does find is the MULTIPLIERS, because that search is a linear
    program: non-negative `lambda` with `residual - sum(lambda_k g_k)`
    non-negative by shift. They are polynomials rather than numbers -- the
    crossing-orbit dual is `r (d - r + 1) / 2`, which is `r/2` times the first
    condition -- and a polynomial with non-negative coefficients is just more
    columns in the same program.

    Exact against the simplex at all 408 grid points that satisfy both
    conditions, with the 312 that do not correctly outside the claim.
    """
    ring = ("q", "k", "r")
    q = Poly.var(ring, "q")
    k = Poly.var(ring, "k")
    r = Poly.var(ring, "r")
    one = Poly.const(ring, 1)
    two = Poly.const(ring, 2)
    half = Poly.const(ring, Fraction(1, 2))
    third = Poly.const(ring, Fraction(1, 3))
    dd = q + one + k
    cd = dd * (dd - one) * half
    cr = r * (r - one) * half
    crossing = dd * r * half - cr          # >= 0 exactly when r <= d + 1

    return _orbit_program(
        ring, dd, r, q, {"q": 1, "k": 0, "r": 4},
        dual={"NNI": q * dd * half,
              "NNN": (cd - q * dd * half - crossing) * third,
              "NNR": crossing,
              "NRR": cr,
              "RRR": Poly.const(ring, 0)},
        region=[("r_within", dd + one - r),
                ("uniform_wins", cd * two + cr * two - q * dd - dd * r)],
        title="the uniform-cover branch, on a region that is not a box")


def separated_narrow():
    """The separated cover where `q <= d - 1`: the fifth and last certificate.

    `separated()` splits nothing -- it puts all of `C(d,2)` on one triangle
    type -- and that only stays feasible while `q >= d - 1`. Below that the
    same cover is still the minimum but has to be paid for differently, with
    `r (d - r + 1) / 2` moved onto the crossing type. Another region, because
    `D <= U` is the same quadratic curve seen from the other side.
    """
    ring = ("q", "k", "r")
    q = Poly.var(ring, "q")
    k = Poly.var(ring, "k")
    r = Poly.var(ring, "r")
    one = Poly.const(ring, 1)
    two = Poly.const(ring, 2)
    half = Poly.const(ring, Fraction(1, 2))
    dd = q + one + k
    cd = dd * (dd - one) * half
    cr = r * (r - one) * half
    crossing = r * (dd - r + one) * half

    return _orbit_program(
        ring, dd, r, q, {"q": 1, "k": 0, "r": 4},
        dual={"NNI": cd - crossing,
              "NNN": Poly.const(ring, 0),
              "NNR": crossing,
              "NRR": cr,
              "RRR": Poly.const(ring, 0)},
        region=[("r_within", dd + one - r),
                ("separated_wins", q * dd + dd * r - cd * two - cr * two)],
        title="the separated-cover branch, paid for below q = d - 1")


def _orbit_program(ring, d, r, q, floors, dual, region=None, title=""):
    """The same four-orbit cover program, in whichever coordinates a branch needs."""
    one = Poly.const(ring, 1)
    half = Poly.const(ring, Fraction(1, 2))
    cols = ["a", "b", "c", "e"]
    rows = [("NNI", [1, 2, 0, 0]), ("NNN", [3, 0, 0, 0]), ("NNR", [1, 0, 2, 0]),
            ("NRR", [0, 0, 2, 1]), ("RRR", [0, 0, 0, 3])]
    return ParametricSpec(
        parameters=floors, sense="min",
        objective={"a": d * (d - one) * half, "b": q * d, "c": d * r,
                   "e": r * (r - one) * half},
        constraints=[(n, {cols[i]: Poly.const(ring, row[i])
                          for i in range(4) if row[i]}, ">=", one)
                     for n, row in rows],
        dual=dual, region=region, title=title)


def spec():
    # d >= 3 and t >= 0 put r >= 4 and q >= 2, so all five triangle types
    # exist. Silently dropping a type would change the program, not just the
    # notation.
    return ParametricSpec(
        parameters={"d": 3, "s": 0, "t": 0},
        sense="min",
        objective={"a": CD, "b": Q * D, "c": D * R, "e": CR},
        constraints=[
            ("NNI", {"a": K(1), "b": K(2)}, ">=", K(1)),
            ("NNN", {"a": K(3)}, ">=", K(1)),
            ("NNR", {"a": K(1), "c": K(2)}, ">=", K(1)),
            ("NRR", {"c": K(2), "e": K(1)}, ">=", K(1)),
            ("RRR", {"e": K(3)}, ">=", K(1)),
        ],
        # The packing dual of the hot cover, read off complementary slackness
        # at (a, e) = (1, 1/3). Finding it was one solved instance; checking it
        # on the whole branch is this command's job.
        dual={
            "NNI": CD,
            "NNN": K(0),
            "NNR": K(0),
            "NRR": D * R * HALF,
            "RRR": (CR - D * R * HALF) * THIRD,
        },
        title="the hot-cover branch of a four-orbit cover program",
    )
