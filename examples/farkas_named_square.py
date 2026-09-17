"""The paper already wrote the square down. Hand it over.

`nlinarith` is `linarith` plus a fixed preprocessing step: multiply pairs of
hypotheses, add `x^2` for each variable and `(x - y)^2` for each pair, then run
the linear certificate search over the enlarged system. `farkas --nonlinear`
does the same and keeps the multipliers.

The fixed square set is where it stops. `(x - y)^2` is there; `(2x - y)^2` is
not, and no amount of search inside a fixed set finds a square outside it. So
the heuristic misses, and what comes back is `unknown_solver` -- "this route
found nothing", which is the honest answer and not a useful one.

The useful observation is that in a written proof THE SQUARE IS ALREADY THERE.
A margin estimate in a linear-programming argument reaches a line like

    12 u^2 - 6 u v + v^2  =  12 (u - v/4)^2 + v^2/4

and the author writes it because completing the square is how they got the
bound. That is the missing piece, in the source, in plain sight. It does not
have to be searched for; it has to be ACCEPTED.

    sp.assume("corner_square", (4*o - v) * (4*o - v) >= 0)
    sp.assume("tail_square", v * v >= 0)

A square of a real expression is non-negative, so assuming one assumes nothing
-- it is a tautology, and it cannot make a false claim provable. What it does
is put one more row in front of the linear search, and that row is the one the
search could not have built.

    $ certo farkas examples/farkas_named_square.py --nonlinear
    PROVED  [unsat]
      degree-2 Positivstellensatz (nlinarith) certificate found: 3 hypotheses
      with a non-zero multiplier
      constant: 0
      degree: 4
      rows: 15
      strict: True
      certificate: farkas (no solver needed, id a9fb7d92a83fef66)
      multipliers:
        corner_square          1/16
        tail_square            1/48
        __goal__               1
      Lean: nlinarith [corner_square, tail_square]

THE MULTIPLIERS ARE THE PROOF, and here they are the source's own arithmetic.
`1/16` and `1/48` are `12/16` and `1/4` divided by the twelve the source
carries, which is `12(u - v/4)^2 + v^2/4` read back. Nothing was reverse
engineered to make that happen: a degree-2 Positivstellensatz over a system
with one decomposition has one answer, and it is the decomposition.

AND THE CERTIFICATE NEEDS NO SOLVER. `certo prove` settles all three of the
comparisons below in one call, using Z3's nlsat, which is complete where
nlinarith is a guess -- and its certificate is an unsat core, which re-checks
by running a solver again. This route gives up completeness and gets an
artefact that re-checks by multiplying rationals and adding them up. For
something going into an appendix that is the better trade, and it is available
only because the square was written down.

WHERE THE SQUARE ISN'T NEEDED. `uniform()` below is the same shape and goes
through with no hint at all: its decomposition is `q(2o + q)/12`, a product of
two hypotheses and one variable squared, both of which the fixed set already
contains. Reaching for a hint before trying without one costs a little and
teaches nothing, so the order is: run it, and name a square only when the run
says it found nothing.
"""
import z3

from certo import Spec


def spec():
    """The comparison whose square is `(4o - v)^2` with `v = 2p - q`."""
    p, q, s = z3.Reals("p q s")
    o, v = p - s, 2 * p - q
    # Two disjoint blocks paid for internally: one of size s, one of size o.
    separated = s * (s - 1 - q) / 2 + o * (o - 1) / 2
    comparison = (2 * p * p - 2 * p * q - q * q) / 12

    sp = Spec(title="the separated cover exceeds its comparison value - p/2")
    # Tautologies, both of them. They add rows, not assumptions.
    sp.assume("corner_square", (4 * o - v) * (4 * o - v) >= 0)
    sp.assume("tail_square", v * v >= 0)
    sp.claim(separated >= comparison - p / 2)
    return sp


def hot_set():
    """`(2s - q)^2` is the square here, and two sign hypotheses do the rest.

    Multipliers come back as `the_square 1/12`, `q_nonneg*o_nonneg 1/6`,
    `o_nonneg 1/3` -- which is `(2s - q)^2 + 2qo + 4o`, all over twelve.
    """
    p, q, s = z3.Reals("p q s")
    o = p - s
    hot = s * (s - 1 - q) / 2 + (s * o + o * (o - 1) / 2) / 3
    comparison = (2 * p * p - 2 * p * q - q * q) / 12

    sp = Spec(title="the hot-set cover exceeds its comparison value - p/2")
    sp.assume("q_nonneg", q >= 0)
    sp.assume("o_nonneg", p - s >= 0)
    sp.assume("the_square", (2 * s - q) * (2 * s - q) >= 0)
    sp.claim(hot >= comparison - p / 2)
    return sp


def uniform():
    """No hint needed: `q*o` and `q^2` are both in the fixed square set.

    Multipliers: `q_nonneg*o_nonneg 1/6`, `sq_q 1/12`. Run this one first to
    see what the heuristic manages on its own.
    """
    p, q, s = z3.Reals("p q s")
    o = p - s
    uni = (s * (s - 1 - q) / 2 + s * o + o * (o - 1) / 2) / 3
    comparison = (2 * p * p - 2 * p * q - q * q) / 12

    sp = Spec(title="the uniform cover exceeds its comparison value - p/6")
    sp.assume("q_nonneg", q >= 0)
    sp.assume("o_nonneg", p - s >= 0)
    sp.claim(uni >= comparison - p / 6)
    return sp
