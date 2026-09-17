"""Not whether it fails, but how much, and on which object.

A refutation is one bit. When you are still shaping a conjecture, the bit is
rarely the useful part: you want to know whether the thing fails by a hair or
by a mile, and which object is the worst, because that is what tells you
whether to weaken the statement or abandon it.

`SweepSpec` takes `collect` instead of (or alongside) `predicate` for exactly
that. No claim is made, nothing is refuted, and what comes back is a
measurement:

    $ certo sweep examples/calibrate_density.py
    SATISFIABLE  [sat]
      CALIBRATION over 156 graphs: min=0 (E???)  max=1 (E~~w)  mean=1/2

Two things make it worth a command rather than a loop.

The values are exact. `collect` returns `Fraction`, so `mean=1/2` is one half
and not 0.5000000000000001, and two graphs whose ratios are genuinely equal
compare equal rather than nearly so.

And the extremes are NAMED. `E???` and `E~~w` are graph6 strings, so the worst
instance is an object you can feed straight back into `prove`, `shrink` or
another sweep -- which is usually the next thing you want to do with it.

Run it with `--json` to get every value, or add a `predicate` to refute and
calibrate in the same pass, so nothing is computed twice.
"""
from fractions import Fraction

from certo import SweepSpec


def edge_density(g) -> Fraction:
    """Edges over the maximum possible, exactly."""
    edges = sum(1 for i in range(g.n)
                for j in range(i + 1, g.n) if g.has_edge(i, j))
    return Fraction(edges, max(1, g.n * (g.n - 1) // 2))


def spec():
    return SweepSpec(
        n=6,
        collect=edge_density,
        worst="min",
        title="edge density over every graph on 6 vertices",
    )
