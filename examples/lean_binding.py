"""What the certificate assumed, against what the Lean lemma actually gives.

The ledger knows which specs ran. Nothing connected a certificate to the
declaration meant to justify it, and the gap cost a user real work: they
certified a bound ASSUMING the fine counting estimate, and found on writing the
Lean that the packaged `patCount_K4_le` uses density `<= 1` and gives something
useless. Nothing warned them. They saw it by going to read the statement, three
modules later.

    $ certo prove examples/counting_bound.py --cert out/counting_bound.json
    $ certo bind examples/lean_binding.py
    REFUTED  [sat]
      PaperIV.MomentErrors.N1_from_counting does NOT provide what fine_count
      assumed: the certificate rests on something stronger than the
      declaration gives

certo reads the certificate's provenance, loads the spec it came from, finds
the hypothesis named in `discharges`, and asks whether what you say the
declaration PROVIDES entails it. `covers()` below is the same binding with the
fine estimate, and it passes.

IT REMAINS A BRIDGE, and `verify` says so every time. Nothing here reads
Mathlib: that `provides` renders the declaration faithfully is your claim,
exactly as a `compose` bridge is. What changes is WHEN it bites -- at bind
time, while you are looking at the statement -- and that `status` can count it.

A SPEC THAT MOVED is reported STALE rather than read as if it had not. The
certificate carries the hash of the file it was made from, and a binding
checked against a statement that has since changed would be worse than none.
"""
import z3

from certo import BindSpec

DECL = "PaperIV.MomentErrors.N1_from_counting"


def spec():
    count, n = z3.Reals("count n")
    return BindSpec(
        certificate="out/counting_bound.json",
        declaration=DECL,
        discharges="fine_count",
        # what the PACKAGED lemma gives: density <= 1, so the cube is lost
        provides=(count <= n**4),
        title="the packaged lemma uses density <= 1")


def covers():
    """The same binding against the estimate the certificate actually needs."""
    count, dens, n = z3.Reals("count dens n")
    return BindSpec(
        certificate="out/counting_bound.json",
        declaration=DECL + "_fine",
        discharges="fine_count",
        provides=(count <= dens * dens * dens * n**4),
        title="the fine estimate does cover it")
