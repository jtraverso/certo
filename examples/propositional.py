"""A formula with `Or` in it, refuted without a solver.

There was an asymmetry worth naming. `certo prove` decides logic -- it takes
z3 expressions, so disjunctions, implications, quantifiers and booleans mixed
with arithmetic all go through. Its certificate is an `unsat_core`, which
re-checks by RUNNING A SOLVER AGAIN.

`certo cases` refutes a CNF with a DRAT proof, which re-checks by unit
propagation and nothing else. That is the strongest artefact here, and it was
reachable only by writing clauses by hand. So anything with an `Or` in it fell
back to trusting z3 twice.

`to_cnf` is the bridge, and it is the standard one: Tseitin. Name every
subformula, constrain the name to mean what the subformula means, and the
result is a CNF whose size is linear in the formula rather than the
exponential blow-up of distributing `Or` over `And`.

    $ certo cases examples/propositional.py
    FINITE CASE VERIFIED (DRAT proof) -- not the theorem  [unsat]
      UNSATISFIABLE with a VERIFIED proof (1 lines)
      clauses: 23
      vars: 11
      certificate: drat (no solver needed, id e16070ab19d66486)
      the formula is VALID: its negation was encoded, and the refutation of
      that negation is the proof
      4 variables of yours, 7 added by the encoding and dropped from the answer
      checker drup-python: OK (1 RUP steps, 0 RAT, 0 deletions)

TO PROVE, ENCODE THE NEGATION. A tautology is a formula whose negation is
unsatisfiable, so `prove=True` gives the solver `Not(phi)` and an UNSAT answer
with its DRAT proof establishes `phi`. The verdict then reads backwards --
certo refuted something you never asserted -- which is why what it MEANS is
printed beside it rather than left for the reader to reconstruct.

EQUISATISFIABLE, NOT EQUIVALENT. The CNF has variables the formula never had.
What survives is exactly two things, and they are the two that are used:

  * the CNF is satisfiable if and only if the formula is;
  * a model of the CNF, restricted to the original variables, is a model of
    the formula.

Neither says the two are the same object, and the auxiliaries are dropped from
the reported witness so nobody has to work out whether `__or_7` was part of
their problem.

WHAT IT REFUSES, and why refusing is the right answer. `satisfiable()` below
is the other direction -- a formula that has a model, reported in your own
variables. `mixed()` is an arithmetic comparison inside a formula, and it is
REFUSED: encoding `x + y <= 3` as a boolean variable produces a CNF whose
refutation says nothing about the arithmetic. That is a wrong answer dressed
as an answer, and mixed problems belong with `prove`, where the arithmetic is
actually decided.
"""
import z3

from certo.propositional import to_cnf

A, B, C, D = z3.Bools("a b c d")


def spec():
    """A tautology: the constructive dilemma, with a distractor.

    `(a -> c) and (b -> d) and (a or b)` implies `c or d`, and the `d -> d`
    conjunct changes nothing -- it is there so the CNF has a subformula whose
    name is used twice, which is where a naive encoder gets it wrong.
    """
    formula = z3.Implies(
        z3.And(z3.Implies(A, C), z3.Implies(B, D), z3.Or(A, B),
               z3.Implies(D, D)),
        z3.Or(C, D))
    return to_cnf(formula, prove=True,
                  title="constructive dilemma, refuted in its negation")


def satisfiable():
    """The other question: does a model exist? Reported in your variables."""
    formula = z3.And(z3.Or(A, B), z3.Implies(A, z3.Not(C)),
                     z3.Or(z3.Not(B), C), C == D)
    return to_cnf(formula, title="a formula with a model")


def not_a_tautology():
    """`(a or b) -> a` is not valid, and what comes back is the counterexample
    rather than a failure: the negation IS satisfiable, and the model says
    which assignment breaks it."""
    return to_cnf(z3.Not(z3.Implies(z3.Or(A, B), A)),
                  title="a formula that is not valid, and why")


def mixed():
    """Refused. Encoding `x + y <= 3` as a boolean gives a CNF whose
    refutation says nothing about the arithmetic."""
    x, y = z3.Ints("x y")
    return to_cnf(z3.Or(A, x + y <= 3), title="not propositional")
