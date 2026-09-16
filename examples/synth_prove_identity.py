"""synth --prove-candidate: discover bounded, prove universal.

The two steps of the workflow, chained, each with its own certificate:

  1. BOUNDED SYNTHESIS. Find integers A, B such that
         (x-1)(x-2) + A*x + B = x^2 - x
     testing x in [1, 20]. That finds the candidate, but proves nothing about
     any other x.

  2. UNIVERSAL PROOF. Fix the candidate and prove the identity for EVERY real
     x. That is where the theorem is.

Note that step 2 changes the SORT: the search runs over bounded integers, the
proof over the reals. Not a whim: non-linear integer arithmetic with
quantifiers is undecidable, while the real case is decidable for polynomials.
That is why the universal obligation is declared, not inferred.

The answer is A=2, B=-2.

    certo synth examples/synth_prove_identity.py --prove-candidate \
        --cert out/identity.json
    certo verify out/identity.json
"""
import z3

from certo import Spec, SynthSpec


def universal(vals):
    """The general statement with the candidate fixed. Over the REALS."""
    x = z3.Real("x")
    A, B = z3.RealVal(vals["A"]), z3.RealVal(vals["B"])

    s = Spec(title="polynomial identity with A={}, B={}".format(vals["A"], vals["B"]))
    # No hypotheses: the identity holds for every real. If any were needed
    # they would be named, and `certo core` would say which are redundant.
    s.claim((x - 1) * (x - 2) + A * x + B == x * x - x)
    return s


def spec():
    A, B = z3.Ints("A B")
    x = z3.Int("x")

    return SynthSpec(
        title="coefficients of a polynomial identity",
        impl_vars=[A, B],
        input_vars=[x],
        impl_constraints=z3.And(A >= -10, A <= 10, B >= -10, B <= 10),
        behavior=z3.And(x >= 1, x <= 20),
        correctness=((x - 1) * (x - 2) + A * x + B == x * x - x),
        universal=universal,
    )
