"""A parameter that depends on itself, and the loop that cannot close.

Three innocent lines, none of which mentions a cycle:

    k     >= tower(1/delta)        the regularity lemma's bound
    rho   <= K / (3 k**2)          what the crude count leaves
    delta <= rho                   Chebyshev

There is one: `delta -> k -> rho -> delta`. Composing gives
`delta <= K/(3 tower(1/delta)**2)`, whose right-hand side vanishes faster than
any power of delta, so no positive delta survives.

    $ certo cycle examples/dependency_cycle.py
    PROVED  [unsat]
      the cycle delta -> k -> rho -> delta cannot close: no positive delta
      survives it
      delta      >= tower      -> tower(u)^1
      k          <= poly ^-2   -> tower(u)^-2
      closes: delta (u^-1) <= rho (tower(u)^-2)

THE CLASS IS THE ARGUMENT, not a substitute for it. Finding this by hand means
inventing a stand-in a solver can see -- `k >= 1/delta` was the one actually
used -- which proves something strictly weaker and leaves the tower carried in
prose. Here the tower is what is declared and what is composed.

MONOTONICITY IS TRACKED. `rho <= K/(3k**2)` bounds rho from ABOVE only because
the map decreases in k, and it is a lower bound on k that is available. An edge
whose available side does not support the direction needed is refused by name
-- see `wrong_way()` -- because composing it anyway could declare a live regime
empty, which is the one error this must not make.

WHAT IT DOES NOT ESTABLISH. That `k` really grows like a tower: that is your
lemma, and the spec's claim. And a cycle this route does not refute comes back
`not established`, never `there is no cycle` -- see `survives()`.
"""
from certo import CycleSpec

TOWER = {"from": "delta", "to": "k", "rel": ">=",
         "fn": "tower", "of": "reciprocal"}
CRUDE = {"from": "k", "to": "rho", "rel": "<=", "fn": "poly", "degree": -2}


def spec():
    return CycleSpec(
        parameter="delta", edges=[TOWER, CRUDE],
        closes=("delta", "<=", "rho"),
        title="the Szemeredi tower closes the loop")


def survives():
    """Weaker growth, and the loop is NOT refuted -- reported as such."""
    return CycleSpec(
        parameter="delta",
        edges=[{"from": "delta", "to": "k", "rel": ">=", "fn": "poly",
                "degree": "1/2", "of": "reciprocal"},
               {"from": "k", "to": "rho", "rel": "<=", "fn": "poly",
                "degree": -1}],
        closes=("delta", "<=", "rho"),
        title="a loop these classes do not close")


def wrong_way():
    """An increasing map with only a lower bound: refused, not composed."""
    return CycleSpec(
        parameter="delta",
        edges=[TOWER, {"from": "k", "to": "rho", "rel": "<=",
                       "fn": "poly", "degree": 2}],
        closes=("delta", "<=", "rho"),
        title="the available bound points the wrong way")
