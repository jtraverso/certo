"""synth (CEGIS): synthesise a constant with a certificate.

Shape of the problem:  THERE EXIST (a, b)  FOR ALL x in [1, 20] :  a*x + b >= x^2

This is the "improve a constant" pattern: the coefficients are the
implementation variables, the input is universally quantified, and the
counterexamples in the certificate are exactly the values of x that pin the
answer down.

Note the banner: this is a BOUNDED search, not a theorem. See
synth_prove_identity.py for the step that closes that gap.

    certo synth examples/synth_constant.py --trace
"""
import z3

from certo import SynthSpec


def spec():
    a, b = z3.Ints("a b")   # what we are looking for
    x = z3.Int("x")         # universally quantified

    return SynthSpec(
        title="a*x + b >= x^2 on [1,20]",
        impl_vars=[a, b],
        input_vars=[x],
        helper_vars=[],
        impl_constraints=z3.And(a >= 0, a <= 40, b >= 0, b <= 40),
        behavior=z3.And(x >= 1, x <= 20),
        correctness=(a * x + b >= x * x),
    )
