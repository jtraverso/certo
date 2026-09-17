"""The sentence "by symmetry" is a bridge -- this turns it into a check.

Five write-ups in this repository start from a symmetrised program, and the
step that gets them there is always some version of

    averaging over the automorphism group, an optimal solution may be
    assumed constant on each orbit

Everything downstream of that sentence is certified: the reduced program's
optimum, its dual, its branches. The sentence itself was not, and it is
load-bearing -- if the group is wrong, the reduced program is a DIFFERENT
program and every number after it is about something else.

It does not have to be a bridge. The argument has exactly three hypotheses,
and given a generating set all three are finite checks:

    $ certo reduce examples/symmetry_reduction.py
    PROVED  [unsat]
      35 variables reduce to 1 orbits, and 21 rows to 1. The averaging
      argument is checked, not asserted
      certificate: symmetry_reduction (no solver needed)

Thirty-five triangles and twenty-one edges of K7 become ONE variable and ONE
row. The optimum does not move: 7 both ways.

WHY THOSE THREE. Take an optimum `x` and average it over the group. The
region is convex and every image of `x` is feasible, so the average is
feasible -- that needs the constraint set to be invariant. The objective is
linear and invariant, so the average has the same value. And the average is
constant on orbits by construction. So an optimum constant on orbits EXISTS,
and restricting to those loses nothing. Each hypothesis is the reason one
step of that goes through, and each is checked per generator:

    the action permutes the variables      a bijection, refused by name
    the constraint set is invariant        sigma(row) is a row, same sense,
                                           same right-hand side, same bounds
    the objective is invariant             c[sigma(v)] == c[v]

A generator that fails any of them is REFUSED, not weakened. A wrong group
does not give a weaker reduction; it gives a wrong one, and a wrong one that
verifies would be worse than no command at all.

A SMALLER GROUP IS STILL SOUND, just less useful. `partial()` below declares
only the cyclic shift instead of the full symmetric group: 35 variables to 5
orbits and 21 rows to 3, rather than 1 and 1. Same optimum, 7. You never get
a wrong answer by declaring too little -- only a bigger quotient.

WHERE THE GROUP COMES FROM is not this command's problem. nauty computes it,
a paper states it, you write it down. certo takes generators and checks them.

WHAT IT DOES NOT SAY, and `verify` repeats it every time: what the optimum
IS. The certificate says the quotient has the SAME optimum as the original.
Solve the quotient with `opt`, or bound it for all n with `parametric`. And
that the group you declared is the group you meant remains the spec's claim,
like every other statement of a problem.

The quotient is REBUILT during verification rather than believed, for the
same reason a branch-and-bound node derives its own linear program: a payload
nobody recomputes is a payload anybody can edit.
"""
import itertools

from certo import LPSpec, SymmetrySpec

N = 7
TRIANGLES = list(itertools.combinations(range(N), 3))


def _name(t):
    return "t{}_{}_{}".format(*t)


def _cover():
    """Cover every edge of K7 by triangles, minimising how many you use."""
    p = LPSpec(sense="min", title="triangle cover of K{}".format(N))
    for t in TRIANGLES:
        p.variable(_name(t), 0, 1)
    p.objective({_name(t): 1 for t in TRIANGLES})
    for e in itertools.combinations(range(N), 2):
        p.constraint({_name(t): 1 for t in TRIANGLES
                      if e[0] in t and e[1] in t},
                     ">=", 1, name="e{}_{}".format(*e))
    return p


def _induced(sigma):
    """A permutation of the VERTICES, as a permutation of the variables."""
    return {_name(t): _name(sorted(sigma[v] for v in t)) for t in TRIANGLES}


def spec():
    swap = dict(enumerate(range(N)))
    swap[0], swap[1] = 1, 0
    cycle = {v: (v + 1) % N for v in range(N)}
    return SymmetrySpec(
        lp=_cover(),
        generators={"swap01": _induced(swap), "cycle": _induced(cycle)},
        title="K7 triangle cover under the full symmetric group",
    )


def partial():
    """The same program under a SMALLER group: the cyclic shift only."""
    cycle = {v: (v + 1) % N for v in range(N)}
    return SymmetrySpec(
        lp=_cover(), generators={"cycle": _induced(cycle)},
        title="K7 triangle cover under Z7",
    )
