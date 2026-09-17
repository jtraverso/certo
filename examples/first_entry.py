"""Where a walk first crosses the line, and by how little it overshoots.

A proof walks along a finite path -- successive edits, successive copies,
successive rounds -- watching a quantity, and stops at the first index where
it crosses a line. Everything after that is about the crossing point, so the
crossing point had better be the one claimed. Two things are asserted and they
are easy to conflate:

    it crosses HERE          a_k is on the far side
    it had not crossed yet   a_j is on the near side for EVERY j < k

The second is the one that carries the weight and the one that goes wrong. An
off-by-one, or a `<=` where the argument needed `<`, and the "first" index is
not first -- and every later step rests on it.

    $ certo entry examples/first_entry.py
    PROVED  [unsat]
      first crosses 1/2 at index 9, where the value is 3/5 -- and by at most
      the step bound, so inside [1/2, 7/10)
      certificate: first_entry (no solver needed)

THE WINDOW is why this is a command and not a loop. With a bound `delta` on
the step size, the step BEFORE the crossing was on the near side, so

    a_k  <=  a_{k-1} + delta  <  threshold + delta

and the walk does not merely cross, it crosses by at most `delta`. That is
what a first-entry argument is usually for. Only the LAST step is used for it,
though `delta` is checked against every step of the prefix: a bound that fails
earlier is a bound somebody got wrong, and `bad_step()` below is that case.

THE PREFIX IS THE WHOLE EVIDENCE. Nothing past the crossing is part of either
claim, so the certificate carries `a_0 .. a_k` and stops. The tail of the
sequence -- which is usually where the length is -- never travels.

    $ certo verify out/first_entry.json
    VALID  first_entry certificate (by re-finding the crossing in exact
                                    rationals, no solver)
      [ok] the sequence crosses at the claimed index  (3/5)
      [ok] it had NOT crossed at any earlier index  (earlier crossings at: -)
      [ok] the index is the end of the stored prefix  (9)
      [ok] every step of the prefix respects the declared bound  (1/5)
      [ok] the window is the threshold plus one step  (7/10)

`strictly()` is the same walk with `>` instead of `>=`, which moves the index
when a value lands exactly on the line -- the distinction that gets lost when
somebody writes "the first time it reaches" and means one of the two.

`never()` is the honest non-answer: a walk that stays below. What comes back
is REFUTED with the reason, and no certificate, because there is no first
index when there is no crossing.
"""
from fractions import Fraction

from certo import EntrySpec

#: A walk that rises in steps of at most 1/5 and passes 1/2 partway along.
WALK = [Fraction(n * (n + 1), 150) for n in range(12)]


def spec():
    """The crossing, with the step bound that turns it into a window."""
    return EntrySpec(
        values=WALK,
        threshold=Fraction(1, 2),
        step_bound=Fraction(1, 5),
        title="the first index past the line, and how far past",
    )


def strictly():
    """`>` rather than `>=`. It matters exactly when a value lands on the line."""
    return EntrySpec(
        values=[Fraction(i, 4) for i in range(8)],
        threshold=Fraction(1),
        strict=True,
        title="the first index strictly past the line",
    )


def never():
    """A walk that stays below. There is no first index, and that is the answer."""
    return EntrySpec(
        values=[Fraction(1, 2 + i) for i in range(10)],
        threshold=Fraction(2),
        title="a walk that never crosses",
    )


def bad_step():
    """A step bound that fails before the crossing, so the window is not there."""
    return EntrySpec(
        values=WALK,
        threshold=Fraction(1, 2),
        step_bound=Fraction(1, 100),
        title="a step bound somebody got wrong",
    )
