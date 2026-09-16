"""R(3,3) = 6, assembled from two finite computations and one arithmetic step.

Both halves of a Ramsey number are finite checks, and they are different
checks:

    R(3,3) <= 6     the CNF "2-colour K6 with no monochromatic triangle" is
                    UNSATISFIABLE, with a verified DRAT proof.
    R(3,3) >  5     the same CNF on K5 is SATISFIABLE, and the model IS the
                    colouring.

Neither is a formula. A DRAT proof talks about propositional variables called
`e0_1`, not about a Ramsey number, and the step from "this encoding is
unsatisfiable" to "R(3,3) <= 6" is the encoding's MEANING -- a modelling
decision that no checker can confirm. So both enter as BRIDGES: verified on
their own, declared in prose, and reported by name every time the assembled
proof is verified.

What is then genuinely checked is the arithmetic on top, and the link: that
each bridge is used downstream exactly as declared, that the final step uses
nothing that was not declared, and that the theorem follows.

Produce the two certificates first (one run per size):

    certo cases examples/ramsey.py     --cert out/r33_k6.json
    certo cases examples/ramsey_k5.py  --cert out/r33_k5.json

    certo compose examples/compose_proof.py
"""
import z3

from certo import ProofSpec, Spec

# Plain integer constants. Nothing here knows what a Ramsey number is; the
# bridges are what tie these symbols to the two computations.
R33 = z3.Int("R33")
n = z3.Int("n")


def _floor_pairs():
    """A lemma that is true, cheap, and not needed. It gets reported."""
    s = Spec(title="a complete graph on at least 3 vertices has an edge")
    s.assume("n_ge_3", n >= 3)
    s.claim(n * (n - 1) >= 6)
    return s


def spec():
    p = ProofSpec(title="R(3,3) = 6, and K_n forces a monochromatic triangle")
    p.assume("n_ge_6", n >= 6)

    p.lemma("upper", certificate="out/r33_k6.json",
            states=(R33 <= 6),
            bridge="the DRAT proof shows the K6 encoding is unsatisfiable; "
                   "reading that as R(3,3) <= 6 is what the encoding means")

    p.lemma("lower", certificate="out/r33_k5.json",
            states=(R33 > 5),
            bridge="the model is a 2-colouring of K5 with no monochromatic "
                   "triangle, so R(3,3) > 5")

    p.lemma("spare", proves=_floor_pairs())

    p.conclude(z3.And(R33 == 6, n >= R33))
    return p
