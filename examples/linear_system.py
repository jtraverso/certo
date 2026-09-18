"""`A x = b` exactly -- and the two things it does not tell you.

The certificate for a solved linear system is almost embarrassing: it is the
solution, and checking it is one matrix-vector product. That is the point. A
number from a numerical library is a number to be trusted; `x` with `A` and
`b` beside it is a number to be multiplied. And because the system travels
with the answer, the check is against the system that was STATED rather than
the one somebody remembers stating -- a solution to a slightly different
matrix being the failure mode that is otherwise invisible.

The system here is real and small enough to check by hand: `A` is the
edge-by-triangle incidence matrix of `K4`, six edges by four triangles, and
`A a = y` asks which triangle weights represent a given edge vector exactly.

    $ certo solve examples/linear_system.py
    PROVED  [sat]
      one solution, exactly, in 4 unknown(s) over the rationals
      x = 1, 1, 1, -1

TWO THINGS IT DOES NOT SAY, and `verify` repeats both every time.

NOT NON-NEGATIVE. `spec()` asks to represent twice the star at vertex 0 --
`y = (2,2,2,0,0,0)`, which is non-negative everywhere. The representation
exists, it is UNIQUE, and it uses a weight of -1. There is no other answer to
choose instead: the matrix has full column rank, so the negative weight is not
an artefact of how the elimination happened to go. A rational solution to the
equations of a packing is not a packing, and this is what that looks like when
it is not a slogan.

NOT INTEGRAL, over the rationals. `over_the_integers()` is the SAME matrix
with `y` all ones: over the rationals the answer is `(1/2, 1/2, 1/2, 1/2)`,
and over the integers there is none. The invariant factors are `1, 1, 1, 2`,
and it is that last `2` that blocks it. Same system, two domains, two
different true answers -- which is why the domain is a declaration here and
not a default somebody discovers later.

UNSOLVABLE IS CERTIFIED TOO. `unrepresentable()` asks for an edge vector no
combination of triangles produces, and the answer carries `y` with `y.A = 0`
and `y.b != 0`. A negative result with nothing behind it is a claim; this one
is two more products.

UNDERDETERMINED IS NOT ROUNDED TO "A SOLUTION". `underdetermined()` returns a
particular solution AND a basis of the kernel, because reporting one point of
an affine subspace as though it were the answer is how a free parameter
disappears from a write-up.
"""
import itertools
from fractions import Fraction

from certo import LinearSystemSpec

VERTICES = range(4)
EDGES = [tuple(sorted(e)) for e in itertools.combinations(VERTICES, 2)]
TRIANGLES = list(itertools.combinations(VERTICES, 3))

#: Six edges by four triangles: `A[e][t]` is 1 when edge `e` lies in `t`.
INCIDENCE = [[1 if (e[0] in t and e[1] in t) else 0 for t in TRIANGLES]
             for e in EDGES]


def spec():
    """Twice the star at vertex 0, and the negative weight you cannot avoid."""
    return LinearSystemSpec(
        matrix=INCIDENCE, rhs=[2, 2, 2, 0, 0, 0],
        title="represent 2x the star at a vertex by triangles")


def over_the_integers():
    """The same matrix, all-ones target: `1/2` each over Q, nothing over Z."""
    return LinearSystemSpec(
        matrix=INCIDENCE, rhs=[1, 1, 1, 1, 1, 1], domain="integer",
        title="the same system, asked over the integers")


def unrepresentable():
    """An edge vector no combination of triangles produces, and the proof."""
    return LinearSystemSpec(
        matrix=INCIDENCE, rhs=[1, 1, 0, 0, 1, 1],
        title="an edge vector outside the triangle span")


def underdetermined():
    """Three conditions on four unknowns: a solution SET, not a solution."""
    return LinearSystemSpec(
        matrix=[[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1]],
        rhs=[Fraction(1), Fraction(1), Fraction(1)],
        title="one condition short")
