"""A claim that sounds obviously right, refuted in milliseconds.

The shape is one a user actually wrote: a density constraint, and the belief
that it "forces `G` almost complete, hence the case is trivial". That belief is
the kind that is cheap to hold and expensive to check -- it reads as true,
nothing in a proof assistant objects to it until you try to prove it, and by
then you have spent the afternoon.

    $ certo prove examples/refute_density.py
    REFUTED  [sat]
      REFUTED: there is a counterexample that satisfies the hypotheses and
      violates the claim
      the counterexample:
        dens = 7/8
        kappa = 4
      certificate: model (no solver needed)

Read the counterexample, not just the verdict. `dens = 7/8` sits inside every
hypothesis -- the floor at `kappa = 4` is `3/4`, and `7/8` clears it -- and it
is not a complete graph. That single number tells you which way to fix the
statement, and it arrives in the same millisecond as the refusal.

The certificate is a MODEL, which is solver-free: re-checking it is
substituting the values into the formula and evaluating. Nobody has to trust
z3, or certo, or this file.

What makes this worth running before a formalisation rather than after: a
false claim costs nothing here and costs hours there, and the two failures
look identical from the outside until you try.
"""
import z3

from certo import Spec


def spec():
    dens, kappa = z3.Reals("dens kappa")
    s = Spec(title="does the density bound force G almost complete?")

    # The regime, as stated.
    s.assume("dens_is_a_density", z3.And(dens > 0, dens <= 1))
    s.assume("kappa_large", kappa >= 4)
    s.assume("dens_floor", dens > 1 - 1 / kappa)

    # The belief: that the floor leaves only COMPLETE graphs, so the
    # remaining case is trivial. It does not.
    s.claim(dens >= 1)
    return s
