"""The design is optimal AND it respects your regions. Both, certified.

A packing certificate proves an optimum. What it could not say, until now, is
the thing an argument usually needs next: **and the design holds the bounds I
put on each region, by this much, and that one cost me this.**

The shape comes from a real model, where the constraints read

    within-A load <= N_A

alongside a parity condition and a divisibility one. Not arbitrary linear
forms -- NAMED REGIONS, each meaning something in the proof. That distinction
is why they are declared separately from the resource capacities: a capacity
is part of the encoding, a load is part of the argument.

    $ certo opt examples/packing_with_loads.py
      EXACT optimum certified: 5 (denominator <= 1)
      2 declared loads, and what the design does to them:
        within_A         2 <= 2   BINDING
                         costs 1 per unit of bound -- relaxing it buys that much
        within_B         3 <= 5   slack 2

Read the second column. `within_A` is **binding** and its shadow price is 1:
relax that bound by one and the optimum goes up by exactly one. `within_B` has
slack of 2, so it is not what is holding you back, and tightening the argument
there buys nothing. That is the difference between a bound that is doing work
and a bound that is along for the ride, and it is free -- a load is a row, so
the dual already priced it.

WHAT THE CERTIFICATE CARRIES is each load's coefficients, bound, achieved
value and slack. `verify` recomputes the achieved value from the primal rather
than believing the declared one, so a certificate that understates what a
region used fails:

    [XX] load `within_A` holds, and at the declared value   2 <= 2, slack 0

Loads take `<=`, `>=` or `==`. The last is exact preservation -- "this region
carries exactly this much" -- which is what "preserve these local loads" means
when the argument depends on the value rather than on a ceiling.

Two things refused rather than accepted quietly: a weight on an item that is
not in the packing (the row would be silently weaker than intended), and a
load name that collides with a resource (the two would be indistinguishable in
the dual, which is the one place you go to read them apart).
"""
from certo import PackingSpec


def spec():
    # Six pairs over two disjoint regions of three lists each.
    pairs = [("dA0", "e01"), ("dA1", "e02"), ("dA2", "e12"),
             ("dB0", "e34"), ("dB1", "e35"), ("dB2", "e45")]
    items = [("p{}".format(i), res, 1) for i, res in enumerate(pairs)]

    return PackingSpec(
        items=items,
        capacities=1,
        title="a packing that has to respect two regions",
        loads=[
            # A ceiling that bites: the A-region could take three, and the
            # argument only allows two.
            ("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2),
            # One that does not: stated for the record, and the certificate
            # says plainly that it is not what constrains the answer.
            ("within_B", {"p3": 1, "p4": 1, "p5": 1}, "<=", 5),
        ],
    )
