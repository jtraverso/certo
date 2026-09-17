"""A fraction inequality that holds for every n, in one line of arithmetic.

The middle of a long argument is full of steps like

    (n - 2) / n^2  <=  1 / n        for every n >= 2

-- a window width, a step bound, an error term. Nobody wants to stop and prove
one, and `certo prove` will settle it: Z3's nlsat is complete over the reals
and the answer comes back immediately. But its certificate is an unsat core,
which re-checks by running a solver again. For a line of arithmetic inside a
proof somebody will archive, that is a heavy artefact for a light fact.

This is the light one.

    $ certo ratio examples/ratio_window.py
    PROVED  [unsat]
      for all n >= 2: (n - 2) / (n^2) <= (1) / (n)
      difference: 2*n
      certificate: ratio_bound (no solver needed)

Clear the denominators and the claim is `1 * n^2 - (n - 2) * n >= 0`, which
expands to `2n`, whose coefficients are non-negative -- and `n >= 2`, so it
is. Reading that is arithmetic.

CLEARING DENOMINATORS IS THE STEP THAT CAN GO WRONG, so it is the step that
gets checked. Multiplying both sides by `n^2 * n` keeps the direction only
because both are POSITIVE on the ray. "n^2 is positive" is obvious;
`n^2 - 3n + 1 > 0 for n >= 3` is not, and a denominator that went negative
somewhere would flip the inequality and make the certificate exactly
backwards. So each denominator goes through the same shift test, and one that
cannot be shown positive is a REFUSAL rather than an assumption.

    $ certo verify out/ratio_window.json
    VALID  ratio_bound certificate (checked by cross-multiplying, expanding,
                                    and reading signs -- no solver)
      [ok] both denominators are positive on the whole ray
           (left n^2, right n)
      [ok] the difference is the two sides cross-multiplied, expanded  (2*n)
      [ok] the difference is non-negative on the whole ray  (2*n)

The difference is REBUILT from the two sides at verification rather than read
from the payload, so a certificate carrying a friendlier difference than its
own sides produce does not pass.

`strictly()` below is the same claim with `<`, which needs one thing more: the
constant term of the shifted difference must be positive, because that term is
the value AT the floor. `>= ` is not offered at all -- it is the same claim
with the sides swapped, and two spellings of one statement is how a sign error
hides.

`too_tight()` is the honest failure. `(n - 2) / n^2 <= 1 / n^2` is FALSE at
n = 3, and what comes back names the difference it could not sign rather than
suggesting the route was close.
"""
from certo import RatioSpec
from certo.polynomials import Poly

RING = ("n",)
N = Poly.var(RING, "n")


def K(c):
    return Poly.const(RING, c)


def spec():
    """The window bound: `(n-2)/n^2 <= 1/n` for every `n >= 2`."""
    return RatioSpec(
        parameters={"n": 2},
        left=(N - K(2), N * N),
        right=(K(1), N),
        title="a normalised edit window, for every n at once",
    )


def strictly():
    """The same, with `<`. Needs the difference strictly positive at the floor."""
    return RatioSpec(
        parameters={"n": 2},
        left=(N - K(2), N * N),
        right=(K(1), N),
        relation="<",
        title="the same window, strictly",
    )


def too_tight():
    """False at n = 3, and the refusal says which difference it could not sign."""
    return RatioSpec(
        parameters={"n": 2},
        left=(N - K(2), N * N),
        right=(K(1), N * N),
        title="a bound that is simply not true",
    )
