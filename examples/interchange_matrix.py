"""The matrix certo certified, and the number that says it was the right one.

`matrix` certifies the matrix it is given, exactly and without a solver. What
it cannot do is notice that the matrix is not the one your proof is about --
and the way that happens is not exotic. Somebody types the coordinates into
Python from a Lean file, or from a paper, and one entry is wrong. The
certificate is then perfect and about a different object.

A user put it in one line: **you can perfectly certify the wrong matrix.**

WHAT CLOSES IT is not a stronger certificate. It is a number both sides
compute SEPARATELY from their own copy, and compare:

    h = 0
    h = (h * B + rows) mod p
    h = (h * B + cols) mod p
    for each row, in order, for each entry, in order:
        h = (h * B + (entry mod p)) mod p

    p = 2^61 - 1,  B = 1000003

Horner, and nothing else. It needs no library on either side, which is the
whole point: a digest somebody has to install something to reproduce is a
digest nobody reproduces. Lean closes the comparison with `decide`; a referee
closes it with patience.

    $ certo matrix examples/interchange_matrix.py
    PROVED  [unsat]
      Smith normal form of rank 4: invariant factors 1, 2, 2, 4
      this matrix carries a FINGERPRINT, 126522541908390224. Whoever holds
      the object can compute the same number from their own copy [...]

THE SPEC NEVER SEES THE COORDINATES. `spec()` names a FILE. The entries are
written by whatever holds the object, and certo reads them -- which is the
difference between a transcription and a hand-off. `RAYS` and `CELL` at the
top of this file stand in for the other side of the boundary so the example
runs on its own; in a real route they are not here at all.

WHAT IT CATCHES, measured rather than asserted -- each of these gives a
different number:

    one entry 4 -> 5          a sign flipped
    a zero -> one             the matrix transposed
    two rows swapped          a row missing
    a column of zeros added

and a file edited by hand after it was written is REFUSED on load, because the
file carries the number it claims and recomputing it costs nothing. That last
one is the case that actually happens: somebody fixes "just one entry".

WHAT IT IS NOT is cryptographic. It catches a typo, a transposition, a wrong
sign, a missing row -- the things that happen when data is retyped. It is not
a defence against somebody building a collision on purpose, and nothing here
pretends otherwise. If the threat is an adversary rather than a keyboard, hash
the bytes: the certificate's provenance already does that for the spec.

AND IT DOES NOT MAKE THE CERTIFICATE AN AXIOM. The other side re-imports data
and checks its own equations. certo establishes what the matrix is; what the
matrix MEANS stays where it was.
"""
import json
import pathlib

from certo import MatrixSpec
from certo.interchange import dump

#: Four rays of a cone, as coordinates. In a real route these are not typed
#: here -- they are written by whatever holds the object, and this file only
#: names the file they were written to.
RAYS = {
    "v0": (4, 0, 0, 0),
    "m01": (2, 2, 0, 0),
    "m02": (2, 0, 2, 0),
    "b": (1, 1, 1, 1),
}
CELL = ("v0", "m01", "m02", "b")

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "interchange_cell.json"


def _write_if_missing():
    """Stand in for the other side of the boundary.

    In a real route this file arrives from Lean, or from a script that holds
    the coordinates. Writing it here keeps the example runnable; the point is
    that `spec()` below reads a FILE and never sees the coordinates.
    """
    if not DATA.exists():
        matrix = [[RAYS[ray][row] for ray in CELL] for row in range(4)]
        dump(matrix, DATA, name="one local cell, four rays",
             note="written by the side that holds the object")


def spec():
    _write_if_missing()
    return MatrixSpec(matrix=str(DATA), question="smith",
                      title="a cell whose coordinates certo never retyped")


def fingerprint_of_the_data():
    """What the other side compares against, and how it gets it."""
    _write_if_missing()
    return json.loads(DATA.read_text(encoding="utf-8"))["fingerprint"]
