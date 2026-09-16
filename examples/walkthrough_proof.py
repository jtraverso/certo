"""The walkthrough's assembly: three lemmas, and the boundary drawn.

Two of them are BRIDGES. "This packing has fractional optimum 15/2" is a fact
about an LP, not a first-order formula, and reading it as a statement about
the mathematics is a modelling step no checker can make. `compose` does not
refuse them -- it names them, and repeats them every time the proof is
verified.

Produce the two certificates first:

    certo opt   examples/walkthrough.py --gap            --cert out/gap.json
    certo mixed examples/walkthrough.py --prove-optimal  --cert out/optimal.json
    certo compose examples/walkthrough_proof.py
"""
import z3

from certo import ProofSpec, Spec

mu, nu, gap = z3.Reals("mu nu gap")


def _arithmetic():
    """The only part that is pure algebra: the gap is the difference."""
    s = Spec(title="the gap is what is left over")
    s.assume("def_gap", gap == mu - nu)
    s.assume("mu_value", mu * 2 == 15)
    s.assume("nu_value", nu == 7)
    s.claim(gap * 2 == 1)
    return s


def spec():
    p = ProofSpec(title="the canonical core has integrality gap exactly 1/2")

    # A definition, not a lemma: `gap` is what the word means. Stating it as
    # an ambient hypothesis rather than smuggling it into a bridge keeps the
    # bridges to what they actually are -- claims about the packing.
    p.assume("def_gap", gap == mu - nu)

    p.lemma("gap_is_half", certificate="out/gap.json",
            states=(mu * 2 == 15),
            bridge="the exact LP dual gives the fractional optimum 15/2; "
                   "reading that as a statement about this packing is what "
                   "the encoding means")

    p.lemma("optimum_is_7", certificate="out/optimal.json",
            states=(nu == 7),
            bridge="branch and bound closed every leaf with a certificate and "
                   "the tree covers the integer domain, so 7 is the integral "
                   "optimum -- of the encoded packing")

    p.lemma("arithmetic", proves=_arithmetic())

    p.conclude(gap * 2 == 1)
    return p
