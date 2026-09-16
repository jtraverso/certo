"""Is this regime non-empty? The question, and the way not to ask it.

The natural way to ask is to claim `False` and see whether the solver objects:

    s.claim(z3.BoolVal(False))

It is the one phrasing that cannot answer. `check` decides
`hypotheses AND claim`, so with a claim of `False` it reports UNSATISFIABLE
whatever the hypotheses are -- for a regime with models and for an empty one
alike. A user asked exactly that, on this shape of system, and was told "no
model exists". They found out only by going to `core`.

    $ certo check examples/regime_nonempty.py --hypotheses-only
    SATISFIABLE  [sat]
      the regime is NON-EMPTY: all 4 hypotheses hold together, and here is a
      point where they do
      certificate: model (no solver needed)

The certificate is a MODEL, so it is solver-free: whether a regime is
inhabited is one of the few answers here that re-checks by evaluation alone.
And it is the whole parameter set at once, exhibited rather than argued --
which is the thing that is easy to believe about your own hypotheses and hard
to check.

The four bounds below are individually reasonable and jointly satisfiable, but
only just: raise the density floor to 3/4 and the regime empties, and
`--hypotheses-only` then names the minimal clash rather than the whole set.
See `lint_vacuous_regime.py` for that side of it.
"""
import z3

from certo import Spec


def spec():
    dens, kappa, n = z3.Reals("dens kappa n")
    s = Spec(title="a regime somebody is actually in")

    s.assume("n_large", n >= 100)
    s.assume("kappa_large", kappa >= 4)
    s.assume("dens_floor", dens > z3.RealVal(1) / 4)
    s.assume("sparse", dens <= z3.RealVal(1) / 2)

    # Ignored by `--hypotheses-only`, and that is the point: the question is
    # about the hypotheses, whatever the claim happens to say.
    s.claim(dens * n >= n / 8)
    return s
