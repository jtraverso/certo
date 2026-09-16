"""A spec that is well-formed, provable, and about nothing.

`certo prove` settles this in a few milliseconds and reports PROVED, with the
vacuity warning attached -- which is the right answer and arrives after
somebody has already decided the run was a success.

`certo lint` asks the same question first, for one solver call on a strictly
easier problem than the proof:

    $ certo lint examples/lint_vacuous_regime.py
    Spec -- for `certo prove / check / core`
      [XX] the hypotheses contradict each other, so any proof will be VACUOUS
           -- valid and about nothing. The clash is: kappa_large, density_high, sparse
      1 errors, 0 warnings, 0 notes

Note which ones it names. `n_large` is in the hypothesis set, is perfectly
consistent with everything, and is not blamed: the clash is minimal, so the
next question -- which of these do I have to give up -- is already answered.

The regime here is the shape the real ones take. Nobody writes `x > 10` and
`x < 1` on purpose. People do write a density floor derived in one section, a
sparsity bound assumed in another, and a parameter range that makes the two
incompatible -- and that the floor `1 - 1/kappa` exceeds 1/2 exactly when
`kappa > 2` is arithmetic nobody does while writing the third assumption.
"""
import z3

from certo import Spec


def spec():
    density, kappa, n = z3.Reals("density kappa n")
    s = Spec(title="a regime nobody is in")

    # Each of these is a reasonable thing to assume, and three of them are
    # reasonable together. Four are not.
    s.assume("n_large", n >= 100)
    s.assume("kappa_large", kappa >= 4)
    s.assume("density_high", density > 1 - 1 / kappa)
    s.assume("sparse", density <= 1 / z3.RealVal(2))
    s.claim(density * n >= n / 2)
    return s
