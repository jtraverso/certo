"""The walkthrough's algebra: an identity that follows from the constraints.

Two loads on the separator, each at most 1/2 of the shared capacity, and the
gain is twice their sum. Does gain = 2 follow when both are tight? `ideal`
answers with cofactors: expand the product, compare coefficients, done.

    certo ideal examples/walkthrough_ideal.py --cert out/identity.json
"""
import z3

from certo import IdealSpec


def spec():
    a, b, g = z3.Reals("a b g")
    return IdealSpec(
        title="tight loads force the gain",
        variables=["a", "b", "g"],
        equations=[a * 2 - 1,          # a = 1/2
                   b * 2 - 1,          # b = 1/2
                   g - 2 * (a + b)],   # g = 2(a+b)
        claim=g - 2,                   # therefore g = 2
    )
