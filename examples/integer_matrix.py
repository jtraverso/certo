"""Exact integer linear algebra, checkable by multiplication.

A determinant from floating point is a number to be trusted. A determinant
from exact elimination is a number to be RERUN. Neither is a certificate.
What this produces is the elimination's own transforms:

    U . A = H          U unimodular, H in Hermite normal form
    U . A . V = S      U, V unimodular, S the Smith normal form

carried together with their INVERSES, which is what turns every claim into
integer matrix multiplication:

    $ certo matrix examples/integer_matrix.py
    PROVED  [unsat]
      Smith normal form of rank 3: invariant factors 2, 6, 12. Z^n modulo
      the row lattice has exactly this torsion
      certificate: integer_matrix (no solver needed)

Z^3 modulo the lattice these three relations generate is Z/2 + Z/6 + Z/12,
of order 144 -- and 144 is |det A|, which `determinant()` reports as -144.
That agreement is not a coincidence, it is the index, and it is the kind of
one-line claim a write-up makes and nobody checks.

WHAT EACH CHECK BUYS, and none of them repeats the elimination:

    U . U_inv = I        so det(U) is +1 or -1, and nothing else
    U . A = H            so A and H span the same row lattice
    H echelon, r pivots  so rank(A) = r, since U is invertible over Z
    prod h_ii            so |det A|, and with the sign of det(U), det A

THE SIGN IS THE ONE INTERESTING PART. `U . U_inv = I` pins |det(U)| and says
nothing about which sign it is -- and that sign IS the sign of det(A).
Recomputing det(U) over Z would cost what the elimination costs. It does not
have to be: det(U) was already known to be +1 or -1, and those two are
distinct modulo any odd prime. So one determinant of U mod a word-sized
prime, where nothing grows, settles it. Not probably -- exactly, because
there were only ever two candidates.

A MINOR IS THE SAME QUESTION ON A SUBMATRIX. `minor()` selects rows [0,1]
and columns [0,1] and asks for the determinant: 36. There is no separate
machinery for minors and there should not be.

RANK IS EXACT, NOT A THRESHOLD. `rectangle()` is 3 by 4 with the third row
the sum of the first two, and the answer is 2 -- decided by how many pivots
H has, not by comparing a singular value against an epsilon. Over Z there is
no epsilon to choose and no choice to defend.

WHAT IS NOT CLAIMED. That H is the ONLY Hermite form of A. It is, by
uniqueness, but uniqueness is a theorem about the definition rather than
something these checks establish; what they establish is that H is in the
form and is equivalent to A. And -- the one that actually costs people
months -- nothing here says the matrix you wrote down is the matrix your
paper is about. The right incidence matrix, the right basis, the right
orientation: that is the spec's claim, and it is exactly where a computation
stops being about the mathematics.
"""
from certo import MatrixSpec

# The relations among three lattice vectors: the rows generate a sublattice
# of Z^3, and the question is which one.
A = [[2, 4, 4],
     [-6, 6, 12],
     [10, -4, -16]]


def spec():
    """The invariant factors: the torsion of Z^3 modulo the row lattice."""
    return MatrixSpec(matrix=A, question="smith",
                      title="the quotient of Z^3 by three relations")


def determinant():
    return MatrixSpec(matrix=A, question="det", title="the index, exactly")


def minor():
    """A 2x2 minor: the same question, on the rows and columns you name."""
    return MatrixSpec(matrix=A, question="det", rows=[0, 1], cols=[0, 1],
                      title="one 2 by 2 minor")


def rectangle():
    """Rank of a matrix that is not square, exactly over Z."""
    return MatrixSpec(matrix=[[2, 4, 6, 8], [1, 3, 5, 7], [3, 7, 11, 15]],
                      question="rank", title="rank of a wide matrix")
