"""A bound certified ASSUMING the fine counting estimate.

This is the certificate `examples/lean_binding.py` then ties to a Lean
declaration. Read the hypothesis name: `fine_count` is the strong estimate,
`count <= dens^3 * n^4`, and the whole point of the pair is that the packaged
lemma does not give it.

    $ certo prove examples/counting_bound.py --cert out/counting_bound.json
"""
import z3

from certo import Spec


def spec():
    count, dens, n = z3.Reals("count dens n")
    s = Spec(title="a bound resting on the fine count")
    s.assume("fine_count", count <= dens * dens * dens * n**4)
    s.assume("n_big", n >= 1)
    s.assume("dens_range", z3.And(dens > 0, dens <= 1))
    s.claim(count <= n**4)
    return s
