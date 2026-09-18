"""The whole interval a variable may take, not one point of it.

`check --hypotheses-only` answers "is this regime inhabited?" and hands back a
model. A user asking whether their repaired window was sound got `a = 0` --
true, and not the answer they needed. What they needed was `a <= 1/3`, the
range, and they derived it by hand.

    $ certo range examples/variable_range.py --var a
    SATISFIABLE  [sat]
      a ranges over [0, 1/3], and that is the whole interval -- not one point
      a <= 1/3
        cheb x 1/3
      a >= 0
        a_nonneg x 1

BOTH ENDS ARE FARKAS COMBINATIONS. `a <= 1/3` follows from the hypotheses
exactly when some non-negative combination of them yields it, and LP duality
gives the tightest one, so the multipliers ARE the proof: `1/3` times the row
`3a - 1 <= 0`. Checking that is adding fractions.

THE VARIABLES ARE FREE. A regime is not a packing -- `a` may be negative, and
a dual derived under `x >= 0` would certify a bound that does not hold. That is
why the dual constraint here is an equality.

WHAT IT DOES NOT ESTABLISH. The spec's CLAIM is never read: this bounds the
variable over the hypotheses, which is the regime and not the theorem. And an
endpoint whose binding row is strict is reported OPEN rather than rounded shut.
"""
import z3

from certo import Spec


def spec():
    a, b = z3.Reals("a b")
    s = Spec(title="the repaired window: how far can a go?")
    s.assume("cheb", 3 * a <= 1)
    s.assume("window", a + b <= 1)
    s.assume("b_nonneg", b >= 0)
    s.assume("a_nonneg", a >= 0)
    s.claim(a <= 1)                 # never read by `range`
    return s


def open_end():
    """The same window with a STRICT row: the supremum is not attained."""
    a = z3.Real("a")
    s = Spec(title="a strict row makes the endpoint open")
    s.assume("cheb_strict", 3 * a < 1)
    s.assume("a_nonneg", a >= 0)
    s.claim(a <= 1)
    return s


def empty():
    """An empty regime is its own answer, not an infinite interval."""
    a = z3.Real("a")
    s = Spec(title="no a at all")
    s.assume("hi", a <= 1)
    s.assume("lo", a >= 3)
    s.claim(a <= 1)
    return s
