"""bounds: a transcendental constant, enclosed rigorously.

The quantity is `e / pi`, and the claim is that it is below 0.866. That is
true but not by much -- the value is 0.865255979..., so a sloppy computation
would be answering a question it has not settled.

What comes back is an INTERVAL in exact rationals, plus the claim it settles.
The certificate can then be checked by comparing fractions: no Arb, no mpmath,
nothing to trust. Re-deriving the interval is a separate check and is reported
separately, because that is the half that needs the library.

Try `claim=("<", "0.8652")` to see the other useful answer: the enclosure ends
up straddling the bound, and the result says `resource_exhausted`, which means
"this did not settle it", never "it is false".

    certo bounds examples/bounds_constant.py --cert out/epi.json
    certo verify out/epi.json
"""
from certo import BoundSpec


def spec():
    return BoundSpec(
        value=lambda m: m.e / m.pi,
        claim=("<", "0.866"),
        describe="e / pi",
        prec=64,
        title="e / pi < 0.866",
    )
