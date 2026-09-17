"""Does every hypothesis earn its place -- or is the theorem overstated?

`core` answers the other half. It says WHICH hypotheses an unsat core needed
and drops the rest, which catches a theorem stated with slack. It cannot catch
the opposite mistake, and the opposite mistake is the expensive one:

    a theorem stated TOO STRONGLY, formalised, and only then found to be
    about a smaller class than the paper claims

A month goes into that. The test costs one satisfiability query per
hypothesis: drop it, and go looking for a counterexample to what remains.

    $ certo audit examples/hypothesis_audit.py
    SATISFIABLE  [sat]
      2 hypotheses are REDUNDANT (n_large, connected): the claim still follows
      without them, so the theorem is weaker than it looks. 1 are needed
      [REDUNDANT]  n_large
      [needed]     m_bounded   without it: connected=True, m=6, n=5
      [REDUNDANT]  connected
      this does NOT say the hypothesis set is minimal [...]

TWO of them, and the second was a surprise while writing this file. `connected`
was put in as an obvious red herring. `n_large` was not -- `n >= 5` reads like
it must matter -- and it does not, because `m <= n - 2` already gives `m <= n`
on its own. That is the whole point: the hypothesis that turns out to be doing
no work is rarely the one somebody suspected.

THE WITNESS IS THE POINT, not the verdict. Knowing `m_bounded` is needed is
worth little; knowing that `n = 5, m = 6` breaks it is what tells you whether
you wrote the hypothesis you meant. A theorem whose hypotheses were never
tested this way is one nobody has looked at from underneath.

THREE ANSWERS, AND THE THIRD IS NOT FOLDED INTO THE OTHERS. `needed`,
`redundant`, and `unknown` when the budget ran out. Not finding a
counterexample is not the absence of one, and a report that quietly counted
`unknown` as `needed` would be telling you the theorem is tight when nobody
checked.

CHECKING IS EVALUATION, NOT SEARCH. A `needed` verdict carries the assignment;
re-checking substitutes it and confirms the kept hypotheses hold while the
goal does not. So the certificate does not ask you to take the search on
trust, only the statement of the problem.

WHAT IT DOES NOT SAY, and `verify` repeats it every time: that the hypothesis
set is MINIMAL. Hypotheses are dropped ONE at a time, and a pair can be
jointly redundant with neither redundant alone. That is a different and much
larger search, and claiming it here would be the overstatement this command
exists to catch.

`tight()` below is a theorem where every hypothesis is genuinely needed, which
is what a healthy one looks like: three witnesses and no redundancy.
"""
import z3

from certo import Spec

N, M = z3.Ints("n m")


def spec():
    """A claim with one hypothesis that is doing no work.

    `connected` is a red herring: nothing in the claim depends on it, so the
    theorem is really about all graphs and not just connected ones. That is a
    weaker statement than intended and a stronger one than stated, which is
    exactly the confusion this command is for.
    """
    connected = z3.Bool("connected")
    s = Spec(title="a theorem with one hypothesis doing no work")
    s.assume("n_large", N >= 5)
    s.assume("m_bounded", M <= N - 2)
    s.assume("connected", connected)
    s.claim(M <= N)
    return s


def tight():
    """Every hypothesis needed, each with the assignment that breaks it."""
    s = Spec(title="a theorem whose hypotheses all earn their place")
    s.assume("n_large", N >= 5)
    s.assume("m_positive", M >= 1)
    s.assume("m_bounded", M <= N - 2)
    s.claim(z3.And(M >= 1, M + 2 <= N, N >= 5))
    return s
