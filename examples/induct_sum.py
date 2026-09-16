"""induct: base cases up to 8, then the step -- and the check that they join.

The property: for n >= 3, the complete graph K_n has at least 3n - 6 edges.
(True, and the bound is tight for maximal planar graphs, which is where the
expression comes from.)

The base cases are real finite checks: for each k in 3..8 a `Spec` fixing n=k
and computing both sides. The step is one `Spec` over a FREE k -- a proof with
a free variable is a proof for every value of it, so there is no quantifier to
hand a solver.

What `induct` adds over running the two halves separately is the join:

  * the base cases are exactly k0..base_upto, no gap and no duplicate;
  * the step starts no later than the base ends.

Set `step_from=10` below to see the second one fail. A base covering 3..8 with
a step valid only from 10 proves nothing about n = 9, and in prose the two
versions read identically.

    certo induct examples/induct_sum.py --cert out/induct.json
    certo verify out/induct.json
"""
import z3

from certo import InductSpec, Spec

k = z3.Int("k")


def edges(n):
    """n(n-1)/2, written so z3 sees integer arithmetic."""
    return n * (n - 1) / 2


def _base(j):
    """P(j): K_j has at least 3j - 6 edges, at one concrete j."""
    s = Spec(title="K_{} has at least 3*{} - 6 edges".format(j, j))
    s.claim(edges(z3.IntVal(j)) >= 3 * j - 6)
    return s


def _step():
    """P(k) and k >= 3  ->  P(k+1), with k free."""
    s = Spec(title="the inductive step")
    s.assume("k_ge_3", k >= 3)
    s.assume("P_k", edges(k) >= 3 * k - 6)
    s.claim(edges(k + 1) >= 3 * (k + 1) - 6)
    return s


def spec():
    return InductSpec(
        title="K_n has at least 3n - 6 edges, for n >= 3",
        k0=3,
        base_upto=8,
        base=_base,
        step=_step(),
        step_from=3,
        describe="every K_n with n >= 3 has at least 3n - 6 edges",
    )
