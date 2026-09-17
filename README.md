# certo

**Between having a mathematical idea and having a proof of it there is a lot
of work that is not proving.** certo does that work — find the object, break
the claims that are false, measure what survives, reduce it to what it really
is, and assemble the rest — and every step comes back with a **certificate
anyone can re-check without trusting certo.**

CLI and MCP. Twenty-eight commands. Runs in milliseconds where a formalisation
costs hours.

*Español: [README.es.md](README.es.md) · run any command with `--lang es`.*

---

## The arc

| Phase | What you ask | What comes back |
|---|---|---|
| **Find** | Is there an object like this? What is the best one? | the object itself — and with `mixed --prove-optimal`, a proof that it *is* the best |
| **Break** | Is this claim actually true? | a counterexample **with concrete values**, in milliseconds |
| **Measure** | Not *whether* it fails — **how much**, and where is it worst? | exact min, max and mean, and the extreme instances by name |
| **Reduce** | Ninety counterexamples. How many objects is that really? | orbits under your symmetry, and one minimal witness per orbit |
| **Establish** | Is it true for every case, every `n`, exactly? | DRAT proofs, induction with the chain checked, Farkas multipliers, Gröbner cofactors, sums of squares, rigorous enclosures |
| **Assemble** | What does my whole project rest on, and what do I still owe? | the proof with every **bridge named**, and a report of what is still assumed |

The through-line is the last column. A verdict you cannot re-check is a
rumour; everything here produces an artefact, and most of them check without a
solver at all.

---

### It finds the object — and proves it is the best one

```
$ certo mixed examples/walkthrough.py --prove-optimal
PROVED  [unsat]
  OPTIMUM 7, PROVED: 73 nodes, 37 of them closed by a certificate
  73 nodes: 19 closed by bound, 18 infeasible, 0 fully fixed
```

Not "the solver said 7". Branch and bound where **every leaf carries its own
certificate** — an exact dual, a Farkas ray, or a fully-fixed residual LP —
and the tree is checked to cover the integer domain. `certo synth` does the
same job by CEGIS when the object is a formula rather than a design, and says
plainly that its search was bounded.

### It breaks the ones that are false, and shows you what broke them

```
$ certo prove examples/refute_density.py
REFUTED  [sat]
  the counterexample:
    dens = 7/8
    kappa = 4
  certificate: model (no solver needed, id 1a76b821f2cafa42)
  engine: z3:5.1.0 | 4.2 ms
```

**Four milliseconds**, and the answer is not "no" — it is `dens = 7/8`, which
clears every hypothesis and is nowhere near the "almost complete" the claim
assumed. That number tells you which way to fix the statement.

### It measures how much, not just whether

```
$ certo sweep examples/calibrate_density.py
SATISFIABLE  [sat]
  CALIBRATION over 156 graphs: min=0 (E???)  max=1 (E~~w)  mean=1/2
```

Exact rationals, and the extremes named. A conjecture that fails is one fact;
*how badly it fails and on which object* is what tells you whether to weaken
it or abandon it.

### It turns ninety failures into the two objects they are

```
$ certo sweep examples/setfamily_sweep.py --witnesses
REFUTED  [sat]
  REFUTED: 90 counterexamples out of 120 examined -- 90 labelled, 2 up to symmetry
  orbit_count: 2
```

Ninety counterexamples is not ninety problems. Declare the symmetry and certo
quotients by it, keeps one **minimal** witness per orbit, and certifies that
the decomposition adds up.

### And it tells you when a proof was about nothing

```
$ certo prove examples/lint_vacuous_regime.py
PROVED -- symbolic and universal under the hypotheses  [unsat]
  VACUOUS: these hypotheses contradict each other, so this goal -- and every
  other goal -- follows. The proof is valid and says nothing.
  The clash is: kappa_large, density_high, sparse
```

Lean will prove that theorem, report no `sorry`, and audit clean on
`#print axioms`. None of that tells you the hypotheses were satisfiable. One
user had **four** Lean modules like it.

### Every one of those leaves something you can re-check later

```
$ certo verify out/optimal.json
VALID  branch_bound certificate (verified without a solver)
  [ok] no node appears twice  (0 duplicates)
  [ok] the incumbent design exists and attains the optimum  (declared 7)
  [ok] every branch has all its children  (0 missing: -)
  [ok] each node's dual is checked against that node's OWN problem, derived
       from the root  (1 closed nodes, each rebuilt from the root system)
  [ok] every leaf is closed by a certificate  (0 not closed: -)
```

That fourth line is newer than the others and is the one that makes the rest
mean anything. A dual for a node's relaxation is a valid dual for **some**
linear program, and nothing in it says which node it came from — so a tree
that stored one per node and checked each on its own terms accepted two of
them **exchanged**, and an expensive subtree closed by a cheap one's
certificate read exactly like a complete proof. Each node's program is derived
from the root system and that node's own fixings now, by the same function the
search used, and the dual is checked against that.

Months later, on the artefact alone, with the warnings repeated — a vacuous
proof keeps saying it is vacuous, a sweep keeps saying what it did not
certify. `certo status` does this for a whole directory, and tells you what
the project still owes.


---

## Start here

| If you are... | Go to |
|---|---|
| **new, and want to see it work** | [Install](#install), then [Two minutes in](#two-minutes-in) |
| **evaluating whether it helps you** | [examples/WALKTHROUGH.md](examples/WALKTHROUGH.md) — one problem end to end, seven commands, fifteen seconds |
| **looking for the command for your question** | [Which command answers which question](#which-command-answers-which-question) |
| **an LLM being asked to use this** | [Which command answers which question](#which-command-answers-which-question), then [The DSL](#the-dsl) and [MCP server](#mcp-server). Run [`certo lint`](#lint-before-the-compute-is-spent) on every spec before running it. |
| **wondering what it will NOT do** | [What it does not do](#what-it-does-not-do) — as important as the command list |

## Can't find the command? Ask the question

```
$ certo commands
Which command answers which question. Read the question, not the name.

  HOW BIG, HOW SMALL, HOW MANY?
    certo opt                          What is the optimum, exactly?
    certo mixed --prove-optimal        ...and is it really optimal over the integers?
    certo bisect                       Where is the threshold for this constant?
    certo bounds                       Is this numeric inequality true? (e, log, pi, zeta)
    certo order                        Does this term DECAY in n, or is it Theta(1)?
    certo parametric                   I checked it for p = 5..12. Does it hold for EVERY p?
```

Also `certo what`. It is the routing table below, in the terminal, in your
language — because the README is not where you are when you are stuck.

**This exists because of a failure worth recording.** `certo order` shipped in
0.5.0, documented with its own section, example and two table rows. A user
spent a session writing it by hand in Python three times, then asked for it as
*the one function I would want in 0.7*. They had searched for "asymptotic" and
"decays"; the command is called `order`.

So `certo asymptotics` and `certo decays` now run it, the help line leads with
*"does this term DECAY in n"* rather than with the exponent, and `lint` names
the command when a claim divides by a product of symbols — the shape of a
magnitude question, which `prove` cannot answer:

```
$ certo lint regime.py
  [--] this claim divides by a product of symbols (d, p, u). If the question is
       whether it DECAYS in a growth parameter, `prove` cannot answer it -- a
       term that is Theta(1) is satisfiable forever and never improves.
       `certo order` reports the exponent, with a certificate.
```

That trigger is deliberately narrow: **two or more** distinct symbols at
negative exponent. One is far too common to mean anything. Across the 39
shipped examples it fires zero times.


## Which command answers which question

Phrased as the question, because that is how anybody arrives.

### Is it true?

| Your question | Command | What comes back |
|---|---|---|
| Is this claim true, under these hypotheses? | `prove` | a proof, or a **counterexample with concrete values** |
| Which of my hypotheses does it actually need? | `core` | the minimal set, and which were redundant |
| Same hypotheses, several claims — which needs what? | `core` on a `MultiSpec` | a hypothesis-by-goal table |
| Is this inequality true, with the multipliers shown? | `farkas` | `linarith`/`nlinarith`, **solver-free** |
| Does this hold for every `n ≥ n₀`? | `induct` | base cases + step, **and the check that the chain joins** |

### Is my setup even sane?

| Your question | Command | What comes back |
|---|---|---|
| **Is my regime non-empty?** | `check --hypotheses-only` | a **model** if it is, the **minimal clash** if not |
| Is this spec well-posed, before I spend the compute? | `lint` | contradictory hypotheses, an empty family, a 10⁹ domain |
| Where does my whole project stand? | `status` | proved, still owed, hollow, stale |
| Can this install actually do what I need? | `doctor` | every capability, and what each gap costs |

### How big, how small, how many?

| Your question | Command | What comes back |
|---|---|---|
| What is the optimum, exactly? | `opt` | the **exact rational dual** = the certificate |
| ...and is it really optimal over the integers? | `mixed --prove-optimal` | branch and bound, **every leaf certified** |
| Where is the threshold for this constant? | `bisect` | the pair that brackets it, each side certified |
| Is this numeric inequality true? (`e`, `log`, `π`, `ζ`) | `bounds` | a rigorous enclosure in exact rationals |
| Does this term decay in `n`, or is it Θ(1)? | `order` | the **exponent**, solver-free |
| I checked it for `p = 5..12`. Does it hold for EVERY `p`? | `parametric` | a bound proved for the whole family, from one dual |

### Does it hold for every case?

| Your question | Command | What comes back |
|---|---|---|
| Does it hold for every graph on `n` vertices? | `sweep` | the family, **and what was established about the predicate** |
| ...for every item of any finite domain? | `cases` (`DomainSpec`) | same, over anything you can enumerate |
| Is this CNF unsatisfiable? | `cases` | a **DRAT proof** |
| My counterexample is huge — what is the real one? | `shrink` | a minimal witness, with the descent recorded |
| A thousand failures — how many objects is that really? | `sweep --witnesses` | orbits, and one minimal witness per orbit |

### Algebra and numbers

| Your question | Command | What comes back |
|---|---|---|
| Do these polynomial equations have a solution? | `ideal` | Gröbner cofactors, checked by expanding |
| Get rid of `t` and tell me the condition on `s` | `eliminate` | the **resultant**, with `Res = A·f + B·g` attached |
| Is this polynomial non-negative everywhere? | `sos` | exact rational squares, solver-free |
| Is this integer prime? | `number` | a Pratt tree, checked by modular exponentiation |
| Is this really a clique partition, and how big? | `cover` | every part a clique, every edge once, counted |

### Building and keeping

| Your question | Command | What comes back |
|---|---|---|
| Does an object with these properties exist? | `synth` | CEGIS, plus the counterexamples that forced it |
| How do I assemble my lemmas into one proof? | `compose` | the proof, **with every bridge named** |
| Is this stored certificate still good? | `verify` | re-checked, with the warnings repeated |
| Get this into Lean | `export --lean` | real statements for linear arithmetic; data for graphs |
| What did I run last month? | `ledger` | an audit log, re-verifiable |

Full table with engines and certificate kinds:
[The twenty-eight commands](#the-twenty-eight-commands).

## What it is and what it is not

**It is** the lab instrument: find a contradiction fast, learn which
hypotheses are redundant, exhaustively validate a finite case, bracket a
constant with a certificate, synthesise a candidate over a bounded domain.

**It is not** a proof assistant — that is Lean, Rocq or Isabelle — nor a
computer algebra catalogue. See [What it does not do](#what-it-does-not-do),
which matters as much as the command list.

**The division of labour**, in a user's words after a real session: certo
finds and certifies the small trades; the human proof explains why they
assemble globally without double-counting.

## The check your proof assistant cannot do for you

Lean will prove your theorem, report no `sorry`, and audit clean on
`#print axioms`. None of that tells you the hypotheses were satisfiable.

A user put it exactly right: `#print axioms` certifies *"I did not cheat"*. It
says nothing about *"this is not hollow"*. They had two Lean modules — no
`sorry`, axioms `[propext, Classical.choice, Quot.sound]`, everything a
formalisation is supposed to look like — and **both had an empty regime**. The
theorems were true, valid, and about nothing.

```
$ certo prove regime.py
PROVED -- symbolic and universal under the hypotheses  [unsat]
  VACUOUS: these hypotheses contradict each other, so this goal -- and every
  other goal -- follows. The proof is valid and says nothing.
  The clash is: dens_high, kappa_small
  !! the hypotheses are contradictory: this proof is vacuous
```

The verdict does not change — it really is a proof, and anything follows from
a contradiction. What changes is that you are told, **and told which
hypotheses clash**, minimally, so the next question is already answered.

It keeps being told. The flag and the clashing set travel in the certificate,
so `verify` repeats it months later when only the artefact remains:

```
WARNING: VACUOUS: the hypotheses contradict each other, so this proof holds
for any goal. The minimal clash is: dens_high, kappa_small
```

Checked on every successful `prove`, `core`, `farkas` and `compose`, at the
cost of one extra solver call on a strictly easier problem than the one just
solved.

### And the other half: a refutation with a model

The same user wrote that a density constraint "forces `G` almost complete,
hence trivial". `certo prove` refuted it in 15 ms with `dens = 27/32`
feasible. Then that `|κ| ≥ 4` sufficed for every density — refuted with
`dens = 127/128, |κ| = 7`, failing by `0.3351` against `0.3333`. The right
bound was 8.

Both would otherwise have gone to a formalisation pass. Two of those, at two
and a half hours each, on a line that had already produced four empty
regimes.


## Install

Requires Python 3.11+.

```bash
pip install -e ".[mcp,numerics]"
```

Dependencies: `z3-solver` and `pulp`, both of which ship their binaries. The
extras are `mcp` for the MCP server and `numerics` for `bounds` and `sos`
(`python-flint`, `mpmath` and `numpy`); without them you get the CLI, minus
rigorous numerics and sums of squares.

Check it works:

```bash
for t in smoke mcp i18n extras; do python tests/test_$t.py; done
```

### Optional

| Tool | What for | Without it |
|---|---|---|
| [`nauty`](https://pallini.di.uniroma1.it/) (`geng` on `PATH`) | enumerating graphs | Python engine, comfortable to n=8 |
| `cadical` or `kissat` | `cases` on large instances | our own CDCL, correct but slow |
| `drat-trim` | second opinion on DRAT proofs | the built-in Python checker suffices |
| `python-flint` (Arb) | `bounds` with special functions | `mpmath.iv`, for the elementary ones |
| `numpy` | the Gram search behind `sos` | **nothing** — `sos` cannot run without it |

None is installed automatically and none is needed to start.

## Two minutes in

```bash
certo --help
```

```bash
certo core examples/amgm.py
```

```
PROVED -- symbolic and universal under the hypotheses  [unsat]
  hypotheses needed: a_pos, b_pos, c_pos | redundant: noise
```

Every file in [`examples/`](examples/) carries in its docstring what it does
and what to expect.

## The three cross-cutting rules

1. **Every command returns a certificate, or says explicitly why not.**
   Never a bare "yes".
2. **Six result states:** `unsat`, `sat`, `unknown_solver`, `timeout`,
   `resource_exhausted`, `out_of_theory`. Only the first two are conclusive.
   The other four all mean "no answer", but for different reasons, and
   collapsing them is expensive: an LLM that reads "unknown" writes "no
   solution exists".
3. **Determinism by work budget, not by clock:** `rlimit` in Z3 and
   `conflict_budget` in SAT. *This covers our engines, not your predicate:* if
   your `sweep` predicate calls scipy or CBC, that part is outside the
   guarantee.

## The twenty-eight commands

| Command | What it does | Engine | Certificate |
|---|---|---|---|
| `prove` | Negate the claim, look for `unsat` | Z3 | unsat core, or counterexample |
| `check` | Satisfiability; `--hypotheses-only` asks if the regime is non-empty | Z3 | model, or core |
| `core` | MUS: which hypotheses are needed | Z3 | minimal core |
| `farkas` | `linarith` / `nlinarith`, with the multipliers | exact LP | **Farkas certificate**, solver-free |
| `compose` | Assemble lemmas into one proof, checking the join | Z3 | **proof**: every lemma, its certificate, and the link |
| `induct` | Base cases + a step, and the check that the chain joins | Z3 | **induction**: both halves, and the two numbers that matter |
| `synth` | CEGIS: ∃obj ∀input ∃aux | CEGIS/Z3 | object + the counterexamples that forced it |
| `opt` | LP/ILP, or a packing | CBC | **dual in exact rationals** = the load certificate |
| `mixed` | A discrete skeleton searched, the continuous part certified | CBC + exact LP | **mixed design**: assignment, exact dual, and a bound |
| `order` | The exponent of `n` once magnitudes are substituted: decays, or Θ(1)? | exact Laurent | **the exponent**, solver-free |
| `bounds` | A numeric inequality, rigorously (`e`, `log`, `π`, `ζ`) | Arb or mpmath | **enclosure in exact rationals** |
| `ideal` | Polynomial systems: refute them, or certify what follows | Gröbner, ours | **cofactors**, checked by expanding |
| `eliminate` | Remove a variable from two polynomials; keep the condition on the rest | Sylvester + Bareiss | **Res = A·f + B·g**, solver-free |
| `parametric` | A bound for EVERY value of a parameter, from a dual you already have -- packing from above, cover from below | weak duality, symbolic | **y and the shifted residuals**, solver-free |
| `peak` | The best INTEGER choice for a family of concave quadratics, and the value there | exact, no search | **the maximiser and two step inequalities**, solver-free |
| `cover` | Is this an exact cover? A clique partition is one case | counting | **the universe and the parts**, solver-free |
| `sos` | A polynomial is non-negative, as a sum of squares | numeric + exact rounding | **rational squares**, solver-free |
| `number` | Primality, or a factorisation | Pratt | **modular-exponentiation tree** |
| `cases` | SAT with a verified DRAT proof | own CDCL or external binary | DRAT proof |
| `enum` | Non-isomorphic graphs with filters | nauty or Python | canonical list + hash |
| `sweep` | Predicate and/or value over a family or ANY finite domain | nauty or Python | family **+ predicate certificates** |
| `shrink` | Minimise a counterexample (graph or MUS) | CDCL / reduction | minimality witness |
| `bisect` | A constant's threshold | prove or cases | the pair that brackets it |
| `lint` | Check a spec before spending the compute on it | — | — |
| `status` | Where a proof stands: proved, owed, hollow, stale | — | — |
| `doctor` | What this install can do, and what each gap costs | — | — |
| `verify` | Re-verify a stored certificate | — | — |
| `export` | Spec to SMT-LIB2/DIMACS, or a counterexample to Lean | — | — |
| `ledger` | Audit log of what was run | — | — |

Common options, **after** the subcommand: `--json`, `--cert FILE`, `--lang`,
`--timeout-ms`, `--rlimit`, `--max-memory-mb`, `--seed`.

Exit codes: `0` conclusive, `2` inconclusive, `1` invalid certificate,
`3` error.

## The DSL

Python as the host language: a `.py` file with a `spec()` function. No
bespoke language — an LLM writes Python far better than SMT-LIB.

```python
import z3
from certo import Spec

def spec():
    a, b, c = z3.Reals("a b c")
    s = Spec()
    s.assume("a_pos", a > 0)      # NAMED hypotheses: core reports on them
    s.assume("b_pos", b > 0)
    s.assume("c_pos", c > 0)
    s.claim((a+b)*(b+c)*(a+c) >= 8*a*b*c)
    return s
```

| Type | Commands |
|---|---|
| `Spec` | `prove`, `check`, `core` |
| `SynthSpec` | `synth` |
| `LPSpec` | `opt` |
| `CNF` / `CNFSpec` | `cases`, `shrink` |
| `SweepSpec` | `sweep`, `shrink` |
| `DomainSpec` | `sweep` over any finite domain |
| `PackingSpec` | `opt` |
| `MultiSpec` | `core` over several goals |
| `ProofSpec` | `compose` |
| `InductSpec` | `induct` |
| `IdealSpec` | `ideal` |
| `EliminateSpec` | `eliminate` |
| `ParametricSpec` | `parametric` |
| `PeakSpec` | `peak` |
| `CoverSpec` | `cover` |
| `SOSSpec` | `sos` |
| `NumberSpec` | `number` |
| `BoundSpec` | `bounds` |
| `OrderSpec` | `order` |
| `BisectSpec` | `bisect` |

The certificate schema is **frozen from 0.4**: existing payloads do not
move, so a certificate produced for a paper still verifies against a later
certo. New certificate kinds stay additive and always will.

## Why the certificate is the centre

With an LLM in the loop the dominant risk is not a shortage of ideas, it is
**plausibility without verification**. The design rule is a single one:

> The LLM proposes, the engine certifies, and the certificate survives
> without the LLM.

Certificates marked *solver-free* are checked with arithmetic, evaluation or
unit propagation — you need trust neither Z3 nor CBC:

| Kind | What it attests | Solver-free? |
|---|---|---|
| `lp_dual` | exact optimality of an LP | **yes**, rational arithmetic |
| `drat` | unsatisfiability of a CNF | **yes**, RUP/RAT |
| `cnf_model` | an assignment satisfies the CNF | **yes**, evaluation |
| `farkas` | a combination of the hypotheses that closes the system | **yes**, adding fractions |
| `asymptotic` | the exponent of a parameter in a term | **yes**, exact arithmetic |
| `ball` | a real quantity lies in an interval, and that settles the claim | **yes** for the claim; the interval needs the spec |
| `proof` | the lemmas, **and** that each is used as its certificate allows | no, re-solves |
| `induction` | the base cases, the step, **and** that they chain without a gap | no, re-solves |
| `mixed_design` | a construction exists and attains a value; NOT that it is optimal | **yes**, exact arithmetic |
| `ideal` | `f = Σ hᵢgᵢ` | **yes**, expand a product |
| `resultant` | `Res = A·f + B·g` | **yes**, expand two products |
| `parametric_bound` | `opt(p) ≤ b(p)·y` for all p, or `≥` for a cover program | **yes**, expand and read signs |
| `integer_peak` | no integer beats `x*`, and `x*` attains the value | **yes**, expand and read signs |
| `exact_cover` | every element in exactly one part | **yes**, counting |
| `sos` | `p = Σ dᵢqᵢ²` in exact rationals | **yes**, expand a product |
| `number` | primality, or a factorisation | **yes**, modular exponentiation |
| `mus` | unsatisfiability **and** minimality | **yes** |
| `graph_set` | non-isomorphic family passing the filters | **yes** |
| `sweep` | family + predicate certificates | depends on the predicate |
| `shrink_graph` | the counterexample is 1-minimal | yes (needs the spec module) |
| `bisect` | the pair bracketing the threshold | depends on its children |
| `model` | a `prove` counterexample | **yes**, substitute and simplify |
| `cegis` | the object has no counterexamples | no, re-solves |
| `unsat_core` | the hypotheses are contradictory | no, but only the core |

And they are tamper-evident. Edit a dual's objective by hand and `verify`
catches it; touch a step of a DRAT proof and it stops being RUP.

### Provenance

Every certificate carries the `certo` version that issued it and, when it came
from the CLI, the path and `sha256` of the spec. If the file changes later,
`verify` warns: the certificate is still valid on its own, but it no longer
corresponds to the file that is there now.

## `induct`: base cases, a step, and the gap between them

"Checked by hand up to n = 8, and from there by induction" is how a large
fraction of combinatorial arguments end. Both halves already had a command —
`sweep` or `cases` for the base, `prove` for the step — and the join was left
to a sentence.

That join is not decoration. A base covering 3..8 with a step valid only from
k ≥ 10 proves **nothing** about n = 9, and the sentence reads exactly the same
either way.

```python
InductSpec(
    k0=3, base_upto=8,
    base=lambda j: some_spec_at(j),      # Spec, SweepSpec, DomainSpec, or a cert
    step=step_spec,                      # assume P(k), k >= 3; claim P(k+1)
    step_from=3,
)
```

```
$ certo induct examples/induct_sum.py
PROVED  [unsat]
  6 base cases k=3..8, step from k=3, chained by induction
```

### Z3 does not do induction, and this does not pretend it does

There is no induction schema in an SMT solver and there will not be one. The
principle is applied **here**, and the certificate's structure *is* the
application. `verify` says so every single time:

> The induction over the naturals is APPLIED here, not verified by a solver.
> It is one fixed schema, unlike a bridge, but it is still a step no
> certificate in this file performs.

That is a different kind of step from a `compose` bridge: bridges are claims
about what a particular computation *means* and vary per problem, while
induction over the naturals is one fixed, named schema. So it is recorded
rather than warned about — but it is recorded.

### What is actually checked

```
$ certo verify out/induct.json
  [ok] the base cases are exactly k0..base_upto  (k=3..8, 6 cases present)
  [ok] the step starts no later than the base ends  (step from k=3, base reaches 8)
  [ok] base case k=3 holds   ... k=4 ... k=5 ... k=6 ... k=7 ... k=8
  [ok] the inductive step holds
  [ok] the step certificate entails the step statement
```

The first two are the ones worth running this for. Set `step_from=10` and it
refuses at build time — no certificate is written — and if one is forged
afterwards, verification catches it again:

```
[XX] the step starts no later than the base ends  (step from k=10, base reaches 8)
[XX] the base cases are exactly k0..base_upto     (k=3..8, 5 cases present)
```

The step is proved with the index **free**, which is what makes it universally
valid: a proof with a free variable is a proof for every value of it, so
there is no quantifier to hand a solver.

## Native combinatorial types

Set families, hypergraphs, designs and mask systems were being re-encoded by
hand in every spec: a tuple of frozensets here, bitmasks there, a `key` to
make an id, a `canonicalize` to quotient, a `reduce` to shrink. Four pieces of
boilerplate per problem, each a place to get it subtly wrong.

```python
from certo import DomainSpec, SetFamily

def spec():
    return DomainSpec(
        items=lambda: list(SetFamily.all_families(5, 2, 3)),
        predicate=lambda f: f.intersecting(),
        canonicalize="auto", reduce="auto",      # and no key= at all
    )
```

```
REFUTED: 90 counterexamples out of 120 examined -- 90 labelled, 2 up to symmetry
  5:01|02|13  x60
  5:01|02|34  x30
```

The point of a native type here is not that it holds data — a tuple does that.
It is that it supplies the three things the rest of the tool asks for:
`key()`, `canonical()` and `reductions()`. So `key`, `canonicalize` and
`reduce` can all be left at `"auto"`, and anyone's own class joins simply by
having those methods.

| | |
|---|---|
| `is_design(t, λ)` | every t-subset in exactly λ blocks |
| `is_uniform(k)`, `is_regular(r)` | the usual two |
| `intersecting()` | all pairs of blocks meet — the Erdős–Ko–Rado shape |
| `covers()` | every point used |
| `SetFamily.all_families(n, k, size)` | the domain to sweep |
| `family_from_masks(n, masks)` | a mask system, with an id and a canonical form |

### The canonical form is exact, or it refuses

Two families get the same canonical form **exactly when** a relabelling of the
ground set carries one to the other. Points are refined into classes no
relabelling can mix — degree, then the block sizes through each point, then
the same again on the refined classes — and the form is minimised over the
permutations respecting that refinement.

On a highly regular family that degenerates towards n!, so there is a cap. And
hitting it **raises** rather than falling back to a cheaper invariant: an
invariant that merged two non-isomorphic families would merge two orbits, and
nothing downstream would notice.

## Symmetries on graph sweeps

`SweepSpec` takes `canonicalize` too. The enumerator already returns one graph
per isomorphism class, so `"auto"` buys nothing there — it is for a symmetry
**finer** than isomorphism (coloured, rooted or otherwise decorated graphs),
and for a family the enumerator did not produce.

## Symmetries: three answers instead of a thousand

A combinatorial search produces relabelled copies of the same object by the
hundred. A sweep reporting 1,400 counterexamples where there are four
structural ones has not told you four things and buried them — it has told you
one thing 1,400 times and left the reading to you.

Declare when two items are the same object relabelled:

```python
DomainSpec(
    items=[(a, b, c) for a in range(1, 5) for b in range(1, 5)
           for c in range(1, 5)],
    predicate=lambda t: sum(t) != 6,
    key=lambda t: "({},{},{})".format(*t),
    canonicalize=lambda t: tuple(sorted(t)),      # the symmetry
)
```

```
$ certo sweep examples/sweep_orbits.py
REFUTED  [sat]
  REFUTED: 10 counterexamples out of 64 examined -- 10 labelled, 3 up to symmetry
  10 counterexamples, 3 up to symmetry
  orbits (of the counterexamples):
    (1,2,3)   x6   (1,2,3), (1,3,2), (2,1,3)
    (1,1,4)   x3   (1,1,4), (1,4,1), (4,1,1)
    (2,2,2)   x1   (2,2,2)
```

Nothing here knows what the group is, and it does not need to — it needs to
know when two items are equal. The representative is the one with the smallest
id: an arbitrary rule, but a **deterministic** one, so two runs never produce
certificates that look contradictory while saying the same thing.

Only the **counterexamples** are decomposed. The orbit structure of everything
that passed is rarely the question, and computing it on a large domain is not
free.

### Where the honesty line is

That two items sharing a canonical form really are in the same orbit is the
**spec's claim**. `canonicalize` is arbitrary Python and nothing here can
check it. What `verify` does check is that the decomposition holds together:

```
  [ok] the orbits partition the domain  (3 orbits covering 10 of 10 items)
  [ok] each orbit has its own representative  (0 representatives appear twice)
  [ok] each representative belongs to its orbit
```

A decomposition whose parts do not add up is wrong whatever the group was.

## Standard reducers

`shrink` has to know what "one step smaller" means, and it used to demand a
hand-written `reduce`. Honest, and also friction. The shapes that keep coming
back now have names:

| `reduce=` | Does |
|---|---|
| `"auto"` | picks from the item's type, or **refuses** |
| `"sets"` | drop one element |
| `"sequences"` | drop one element of a list or tuple |
| `"decrement"` | lower one integer coordinate by one |
| `"graphs"` | delete one vertex |
| `"masks"` | clear one set bit |
| a callable | whatever you wrote — untouched |

`auto` treats a tuple of integers as a **parameter point**, not a collection:
`(3, 1)` reduces to `(2, 1)` and `(3, 0)`, not to `(1,)` and `(3,)`. Dropping a
coordinate from a parameter point changes its arity, which is rarely the
reduction anyone meant.

And `auto` refuses on a type it does not recognise rather than inventing
something. A witness that is minimal for the wrong relation looks exactly like
one that is minimal for the right one, and nothing downstream would notice.

## `certo doctor`

Installing every extra pulls in a fair chain of dependencies, and most people
need none of it. So the answer to "what do I actually have?" should not be
read off an import error in the middle of a run.

```
$ certo doctor
  capability   present   what for
  python       [ok]      the interpreter (3.11 or newer)
  z3           [ok]      prove, check, core, synth, compose
  pulp         [ok]      opt, farkas (the exact LP behind both)
  flint        [ok]      bounds, with special functions
  nauty        [--]      fast graph enumeration for enum and sweep
  cadical      [--]      cases on large CNFs

  optional pieces missing, each with a fallback:
    nauty        the built-in Python engine, comfortable to n=8
    cadical      the built-in CDCL: correct, and slow

  MCP server
    workspace: /path/to/project
    the server module imports and starts

  everything required is present
```

Every row says three things, and the third is the one that matters: **what
happens without it**. A missing optional tool is almost never fatal here, and a
checklist of red crosses that does not say so reads as a broken install.

```bash
certo doctor --register-mcp
```

Adds `certo` to `.mcp.json` in the current directory, **merging** with whatever
is already registered rather than replacing it, and refuses to touch a file
that is not valid JSON. It also checks the server actually starts, which is a
different question from whether it is registered — and the one people mean.

## What a sweep actually establishes

A sweep that passes and a sweep that passes *with certificates* are not the
same result, and the gap is wide. So the banner names which one you got:

| Level | What holds | When |
|---|---|---|
| **certified** | every evaluation carries its own certificate; the predicate is not trusted at all | the predicate returns `Outcome(ok, cert=...)` **and** `--cert-all` stores them |
| **reproducible** | the domain, its hash, and a verdict vector: re-running the predicate gives the same answers | a bare `bool` predicate — the common case |
| **recorded** | only the domain and its hash | the spec is gone, moved, or was never stamped |

```
$ certo sweep spec.py
FINITE SWEEP REPRODUCIBLE -- the predicate is NOT certified  [unsat]
  the predicate holds on all 3481 items (FINITE DOMAIN, not the theorem)
  predicate_certified: 0
  predicate_uncertified: 3481
  !! 3481 of 3481 evaluations carry no certificate. The sweep is REPRODUCIBLE
  -- re-running the predicate gives the same answers -- but nothing here
  establishes that those answers are right.
```

Note the two independent caveats. "Not the theorem" is about **generality**:
a finite domain was checked, not every `n`. "Not certified" is about
**trust**: nothing here says the predicate answered correctly. A passing sweep
used to state only the first, and a green banner over eleven thousand
unchecked booleans is where that does the most damage — there is no
counterexample to go and look at.

### Replay: the middle level, named

The certificate stores a **verdict vector** — one character per item, in
domain order — and its digest. `verify` re-runs the predicate and compares:

```
$ certo verify out/sweep.json
VALID  domain_sweep certificate (by re-running the spec, not by trusting its answers)
  [ok] the family hash matches
  [ok] the item ids are unique
  [ok] re-running the predicate gives the same verdicts  (3481 evaluations, all identical)
  WARNING: 3481 of 3481 evaluations carry no certificate. Replaying them
  agrees, which makes the sweep reproducible; it does NOT make the
  predicate's answers verified.
  reproducible, predicate NOT certified -- domain of 3481 items
```

This is the only check that catches a predicate edited under a stable name:
the domain hash cannot — the domain did not move — and the stored
certificates cannot, because there are none. When it disagrees it names the
item:

```
  [XX] re-running the predicate gives the same verdicts
       (item a=1,b=1 (index 0) now answers differently)
```

Two consequences worth stating. Verification now costs a full re-run of the
predicate, which is the honest price of the claim. And the header says **"by
re-running the spec"** rather than "without a solver": replaying runs the
spec's own Python, which may well call a solver, so the old phrasing was the
same overclaim one level down.

### Getting to `certified`

Return an `Outcome` carrying the certificate, and store them all:

```python
def predicate(item):
    res = lp.opt(build(item))
    return Outcome(ok=res.verdict is Verdict.PROVED, cert=res.certificate)
```

```bash
certo sweep spec.py --cert-all
```

Both halves are needed. A predicate that certifies every answer but runs with
the default `--cert-all` off keeps only the counterexamples' certificates, so
the certificate carries one out of twenty-one — and says so. **A certificate
can only attest what it actually contains.**

## Vacuous proofs are caught, not celebrated

`prove` succeeds when `hypotheses ∧ ¬goal` is unsatisfiable. If the hypotheses
are already unsatisfiable *by themselves*, that happens for **every** goal.
The proof is valid — anything follows from a contradiction — and it says
nothing at all.

This is the most embarrassing way to be wrong and the easiest to miss, because
the output looks exactly like success. So it is checked on every successful
`prove`, `core`, `farkas` and `compose`:

```
$ certo prove vacuous.py
PROVED -- symbolic and universal under the hypotheses  [unsat]
  VACUOUS: the hypotheses contradict each other, so this goal -- and every
  other goal -- follows. The proof is valid and says nothing. Run `check` on
  the hypotheses alone to find which pair clashes.
  !! the hypotheses are contradictory: this proof is vacuous
```

The verdict does not change, because the verdict is not wrong. What changes is
that you are told. And it keeps being told: the flag travels in the
certificate, so `verify` repeats it months later, when the run is long
forgotten and only the artefact remains.

```
$ certo verify out/vacuous.json
VALID  unsat_core certificate (verified with a solver)
  [ok] the core is unsatisfiable  (unsat)
  WARNING: VACUOUS: this core does not include the negated goal, so the
  hypotheses contradict each other and the proof holds for any goal.
```

Two details worth knowing:

* **It costs one extra solver call, on the successful path only**, and that
  call is on a strictly easier problem than the one just solved — the
  hypotheses without the goal.
* **In `farkas` it cannot be read off the multipliers.** A zero multiplier on
  the negated goal would suggest vacuity, but the LP is free to give that row
  a non-zero weight even when it is not needed, and usually does. So the
  question is asked directly: drop the goal row (and, in `--nonlinear` mode,
  every row derived from it) and search again.

In `compose` the check lands where it matters most. Two *derived* lemmas can
never contradict each other — both are true. Only **bridges** can, because a
bridge is asserted rather than derived. Two bridges that clash make the whole
theorem vacuous, and that is reported by name.

## `mixed`: certify the construction, not the search

A MILP that chooses a discrete structure *and* a compatible fractional packing
at the same time is a shape `opt` could not express at all: `LPSpec(integer=
True)` makes **every** variable integer, which is a different problem, not a
restriction of this one. Variables now carry a kind:

```python
lp.variable("y17", kind="binary")     # reserve this triangle
lp.variable("q42")                    # pack fractionally inside what is left
```

The point is what gets certified. For an **existence proof**, whether the
discrete choice was optimal does not matter — exhibiting a construction that
reaches the target is the whole job. So the flow is deliberately not "certify
the MILP":

```
search (CBC, heuristic)  →  freeze the discrete part
                         →  residual LP over the continuous part
                         →  exact dual, exact everything
                         →  compare against the target
```

```
$ certo mixed examples/mixed_design.py --target 10
SATISFIABLE  [sat]
  certified design reaching 28/3, target 10
  achieved 28/3 = 6 discrete + 10/3 continuous | relaxation bound 28/3
  3 discrete choices: y0, y2, y3
  the achieved value meets the relaxation bound, so this IS the global optimum
```

### Three numbers, kept apart

| | What it is |
|---|---|
| **achieved** | what this construction attains. Exact, and a genuine **lower** bound on the true optimum, because the thing exists |
| **conditional** | the best the continuous part can do **with this skeleton**, from the residual LP's exact dual |
| **bound** | the relaxation over **all** skeletons: an **upper** bound |

That third number is not in the obvious design and costs one extra LP. It buys
something real: **when `achieved` meets `bound`, global MILP optimality is
certified for free.** That happens more often than people expect, and when it
does not, the gap is printed rather than left to be inferred from silence.

### What is certified, and what is not

```
$ certo verify out/mixed.json
VALID  mixed_design certificate (verified without a solver)
  [ok] the discrete assignment really is discrete
  [ok] the full point satisfies every original constraint
  [ok] it attains the value it claims
  [ok] the residual LP's own certificate holds
  [ok] and that residual IS the original problem with this assignment substituted
```

That fourth check is the one that makes this more than three files in a
folder. Without it the sub-certificate could be about a *different* problem —
the same gap `compose` closes between a lemma and the statement it is used
for.

CBC's answer is a **guess until something checks it**: it returns `0.9999997`
for a binary as often as not, so the assignment is rounded and then verified
against the original constraints in exact arithmetic. A design that does not
survive that check is refused rather than reported.

And when the bounds do not meet:

> **GLOBAL OPTIMALITY IS NOT CLAIMED.** The discrete skeleton came from a
> search that nothing here re-does; what is certified is that this
> construction exists and attains what it says.

### A shortfall is not an invalid certificate

A design that misses its target verifies as **VALID** with a warning. The
certificate is correct; the design is insufficient, and those are different
statements. Reading `INVALID` there would say something is broken when
nothing is.

Full MILP optimality — a branch-and-bound certificate with an exact dual or an
infeasibility proof at every leaf — is a different and much larger thing. It
is in the backlog, and it is not what an existence proof needs.

### Three levels, named

A user asked for exactly this taxonomy, in these words, and the names are what
a reader needs:

| Level | What holds |
|---|---|
| `feasible` | a mixed point satisfies every constraint and attains a value |
| `conditional_optimum` | and the residual LP is optimal **given this skeleton** |
| `global_optimum` | and it meets the relaxation bound, so no skeleton does better |

```
$ certo verify out/mixed.json
VALID  mixed_design certificate (verified without a solver)
  ...
  GLOBAL OPTIMUM: it meets the relaxation bound, so no skeleton does better
```

### `--freeze`: your solver, not ours

A real MILP may be solved by HiGHS, Gurobi, something bespoke or a person.
Requiring certo's own CBC to reproduce it would put **certo's limits in front
of a construction that already exists**, which is backwards.

```bash
certo mixed spec.py --freeze my_solution.json --target 602/9
```

The file is `{"y17": 1, "y23": 0, ...}` — or `{"assignment": {...}}`. It is
rounded and checked exactly like any other, so where it came from changes
nothing about what is certified. What it does change is recorded:

> The skeleton came from **another solver** and was frozen here. That changes
> nothing about what is certified — it was rounded and checked exactly like
> any other — but it means certo never saw the search that produced it.

## `opt --target`

For an existence proof the question is rarely "what is the best possible
value" and usually "is this bound reached":

```
$ certo opt examples/packing_mixed.py --target 12
  25/2 REACHES the target 12
```

The target travels in the certificate, so `verify` repeats the comparison in
exact rationals:

```
  [ok] the certified value reaches the target  (25/2 against 12, margin 1/2)
```

Falling short is a **warning on a valid certificate**, not invalidity — the
certificate is correct and the bound is insufficient, and those are different
statements.

## Whole in one kind, fractional in another

```python
PackingSpec(items=..., integer={"K3"})     # triangles whole, K4s fractional
```

`integer=True` still means all of them. A packing whose structural items are
placed whole while the rest is a fractional relaxation is the common shape,
and forcing all-or-nothing changes the problem rather than restricting it.

On such a problem `opt` reports **only the relaxation bound** and says so:
rounding every variable would turn a K4 weight of 1/6 into zero and report a
design worth nothing. The achievable value comes from freezing the discrete
part and re-solving the rest, which is `certo mixed`.

## Three engines that are not a solver

`prove`, `check`, `core`, `synth` and `compose` are Z3 wearing different hats.
These three are not, and they exist because the questions they answer are ones
an SMT solver either grinds on or cannot phrase.

### `ideal` — polynomial systems, decided algebraically

```python
IdealSpec(
    variables=["x", "y"],
    equations=[x*x + y*y - 1, x - y, x + y - 3],
    claim=None,                    # None: is the system inconsistent?
)
```

```
$ certo ideal examples/ideal_inconsistent.py
PROVED  [unsat]
  the system has NO common solution: 1 is in the ideal, and the cofactors prove it
  cofactors:
    g0 * (2/7)
    g1 * (2/7*y - 3/7)
    g2 * (-2/7*x - 3/7)
```

Multiply that out and you get `1`. That is the whole proof, and checking it is
expanding a product and comparing coefficients in exact rationals — **no
solver, no algebra system, nothing to take on trust.** Finding the cofactors is
a Gröbner basis computation; a library that merely tells you "yes, it's in the
ideal" leaves you with nothing but its word.

With a `claim`, the same machinery certifies `f = Σ hᵢgᵢ` — that `f` vanishes
on every common root.

Two properties worth knowing:

* **It decides.** Gröbner basis membership is decidable, so a negative answer
  is `REFUTED`, not `unknown_solver`. That is rare in this tool and worth
  using: `prove` on a system of polynomial equalities can grind where this
  answers.
* **The field is ℂ.** `1 ∈ I` refutes solutions over the complex numbers,
  hence over the reals, rationals and integers. The converse does **not**
  hold: a proper ideal means a complex root exists, and says nothing about a
  real one. `verify` repeats that every time.

### `sos` — a numeric search, an exact certificate

I argued twice in this project's own notes that sums of squares were not worth
having, because an SDP is solved in floating point and an inexact certificate
is not citable. That objection was aimed at the wrong half. It would rule out
`opt` too — and `opt` answers it: solve numerically, reconstruct rationals,
re-verify exactly.

```
$ certo sos examples/sos_quartic.py
PROVED  [unsat]
  a sum of 2 squares, exact, with denominator 2
  squares:
    1 * (-1/2*x^2 + y^2)^2
    3/4 * (x^2)^2
```

The pipeline: write `p = zᵀGz` (a linear condition on `G`), find a numeric `G`
by alternating projections onto that affine subspace and the PSD cone, round
it, **project back onto the subspace exactly in `Fraction`**, then do an exact
LDLᵀ. If every pivot is non-negative the decomposition *is* the sum of
squares. The floats were the search; they never reach the certificate.

Incomplete, and in a way worth knowing: every sum of squares is non-negative,
but from degree 4 in 3 variables there are non-negative polynomials that are
not sums of squares. Motzkin's is the standard one, and `certo sos` comes back
`unknown_solver` on it — never "the polynomial goes negative".

For degree 2, `farkas --nonlinear` is cheaper and gets there first.

### `number` — primality you can cite

`n.is_prime()` is true, fast and uncitable. A Pratt certificate is the same
fact with the evidence attached:

```
$ certo number --n 2147483647
PROVED  [unsat]
  2147483647 is prime, with a Pratt certificate of 53 modular checks
  witness: 7
  Pratt tree: 29 nodes, depth 5
```

`n` is prime exactly when some `a` generates `(ℤ/n)*`: `a^(n−1) ≡ 1` and
`a^((n−1)/q) ≢ 1` for every prime `q | n−1`. Those `q` need certificates too,
so the thing is a **tree** recursing down to 2 — and checking the whole tree is
a handful of `pow(a, e, n)` calls.

Three details that are the difference between a certificate and a test:

* **The factor list must be complete.** Missing one prime factor of `n−1`
  would let a composite through, so `verify` checks the factors multiply back
  to `n−1` before it looks at the witness.
* **Carmichael numbers.** 561 passes the Fermat condition for most bases; the
  order condition is what catches it, and `certo number --n 561` comes back
  `REFUTED` with no certificate.
* **The witness is reproducible.** Small bases are tried in order rather than
  randomly, so the same `n` gives the same certificate — and the same digest —
  on every machine.

`--question factor` gives the factorisation instead, each factor carrying its
own primality certificate, so "and these are prime" is not left hanging.

## `cover`: is this really a clique partition, and how large?

Somebody hands you a clique partition of a graph and says it has 47 parts. Two
things have to be true and neither is visible by looking: every part really is
a **clique**, and every edge is covered **exactly once** — not zero times,
which makes it not a cover, and not twice, which makes the count a lie.

Checking both is counting.

```
$ certo cover examples/clique_partition.py
PROVED  [unsat]
  an EXACT COVER: 7 parts, every one of the 21 elements in exactly one
  certificate: exact_cover (no solver needed)

$ certo verify out/clique_partition.json
VALID  exact_cover certificate (checked by counting, no solver)
  [ok] every element of the universe is covered  (0 missed: -)
  [ok] no part covers anything outside the universe  (0 foreign elements)
  [ok] and covered exactly once  (0 covered more than once: -)
  [ok] the declared number of parts is the number of parts  (7 counted, 7 declared)
  [ok] every part really is a clique of the graph  (0 parts are not)
```

The example is K7 partitioned into 7 triangles — the Fano plane — because it
is tight (21 edges, 7 parts, 3 each, nothing to spare) and anyone can check a
line of it by hand.

### ...and how far it is from the minimum

A cover certificate is an **upper bound**. A user read one as an optimum —
reporting a construction of 780 parts where the obvious one uses about 41, and
calling the difference a property of the graph rather than a fact about their
construction. Nothing in the certificate was wrong; the missing half was the
lower bound, and it lived in an LP they had to rebuild by hand.

```
$ certo cover examples/cover_optimize.py --optimize --prove-optimal
PROVED  [unsat]
  an EXACT COVER: 21 parts, every one of the 21 elements in exactly one

  and how close that is to the minimum:
    your cover      21 parts   (an UPPER bound, certified above)
    relaxation      7   (a LOWER bound, exact rational dual -- fractional,
                         so not a cover you can build)
    integer optimum 7   (PROVED by branch and bound)
  your cover uses 21; the minimum is 7.
```

Three numbers, three statuses, and the labels travel with them. The optimum
appears only when the search finishes; when it does not, what comes back is
the incumbent, the bound and the gap, labelled inconclusive.

`CoverSpec(candidates=...)` is **required** for this and refused rather than
guessed: a cover is only minimal relative to what you were willing to use, and
the set of all cliques of a graph is usually enormous and almost never what
anyone meant.

`CoverSpec.to_lp(integral=False)` gives the relaxation and `to_lp(integral=True)`
the physical minimum, if you want the LP itself. The rows are **equalities**
for an exact cover, which is the one thing a relaxation written by hand gets
wrong.


### Three ways it goes wrong, reported as three different things

| What is wrong | What comes back |
|---|---|
| a part is not a clique | **inconclusive**, with the offending pairs named — that is a statement about the graph, not about the cover, and no certificate is written |
| an edge is covered twice | **REFUTED**, naming the edges, and pointing out that `exact=False` would make the same data a valid cover |
| an edge is covered zero times | **REFUTED**, naming the edges |

An at-least cover is a weaker and perfectly reasonable claim, so it is
recorded as a *different* one: the certificate says which was made rather than
letting a reader assume the stronger.

### The half it does not do

This is an **upper bound** with an artefact attached. That 7 is the *smallest*
possible is a different statement, and the exact rational dual from `certo opt`
on the same edge set is a lower bound for it. Where the two meet, the number
is proved — the same pairing `opt --gap` already makes for packings.

Finding a minimum clique partition is NP-hard and deliberately not what this
does. Bring your own, from whatever found it.


## `parametric`: checked for p = 5..12, or true for every p?

This is the thing certo kept saying it could not do, and the one sentence that
carries the most unearned weight in mathematical writing: *"and similarly for
larger n"*.

For a linear program whose data are **polynomials** in a parameter, weak
duality is available symbolically. Any `y >= 0` with `A(p)ᵀy >= c(p)` gives
`opt(p) <= b(p)·y` — for every `p` at once, not for the ones you ran.

```
$ certo parametric examples/parametric_bound.py
PROVED  [unsat]
  for all p >= 10, the optimum is at most 1/6*p^2 + 1/6*p - 2/3
  and that is every value with p >= 10 -- not a sample of them
```

And it is not a loose bound. Solving that LP outright:

| p | bound | optimum |
|---|---|---|
| 10 | 53/3 | 53/3 |
| 11 | 64/3 | 64/3 |
| 15 | 118/3 | 118/3 |
| 30 | 463/3 | 463/3 |

**One dual, read off one solved instance at `p = 10`, gives the exact optimum
for every `p` above it.**

### The division of labour

certo does not search for `y` here. `certo opt` on a single instance hands you
one, and so would any other solver. What this checks is that the `y` you
already have works for the whole family — and that check is arithmetic:

> substitute `p = 10 + u`, expand, and read the signs off the coefficients

All non-negative means the polynomial is non-negative on the ray, because `u`
and its powers are. Same split as `farkas`, one level up: there the
multipliers are constants, here they are constants attached to a family.

### What it will not pretend

The shift test is **sufficient and not necessary**. `p² - 3p + 3` is positive
everywhere and fails it at `p₀ = 0`. So a failure means *"not established by
this route"*, never *"false"* — and **no certificate is emitted**, because a
route that did not work is not a bound.

`verify` repeats the rest every time: this bounds the **LP relaxation**, it
says nothing below the floor, and it says nothing about an integer optimum.

### Covers, not only packings

The above is a **packing**: maximise, `<=` rows, bounded from above.
Symmetrised **cover** programs are the other half of the same duality and turn
up at least as often — a write-up that says *"averaging over the automorphism
group, an optimal fractional cover may be assumed constant on each edge
orbit"* has just produced one. So `sense="min"` with `>=` rows is the second
shape, and what it certifies is a bound from **below**, out of a feasible
packing.

```
$ certo parametric examples/parametric_cover.py
PROVED  [unsat]
  for all p >= 3, s >= 0, the optimum is at least 1/2*p^2 - 1/2*p
  columns: 2
  sense: min
  and that is every value with p >= 3, s >= 0 -- not a sample of them
```

Two things change with it, and both are forced rather than chosen.

**The dual is not a constant.** In a packing the multipliers are rates, one
rational each. A cover's dual is itself a packing, and a packing of a growing
object grows with it — `C(p,2)` triangles, not `1/3`. So a dual entry may be a
polynomial, and `y >= 0` becomes the same shift test as every other row.

**A threshold in the value function is the dual's feasibility.** The example
above certifies the branch `q >= p - 1` of a closed form that changes shape at
`q = p - 1`. Its one non-trivial row is

```
p q - 2 C(p,2)  =  p (q - p + 1)  =  p s   >=  0
```

which is non-negative exactly on that branch. The dual stops being feasible
precisely where the closed form changes branch — which is what a threshold in
a piecewise-linear value function *is*, seen from underneath. Each branch is
its own spec and its own certificate, because each is its own claim.

`examples/parametric_orbits.py` is the same thing one size up: four edge
orbits, five triangle types, three candidate covers, and the branch conditions
falling out of the dual as one residual row and one non-negativity.

### Where this came from

A real instance, and the structure is worth seeing. A symmetrised LP solved
exactly for `p = 5..12` with a hand-written rational simplex gave duals that
are **piecewise constant with thresholds** — one vertex at `p = 6`, another
across `p = 7, 8, 9`, a third from `p = 10`. On each piece the bound is a
polynomial in `p` and the dual is fixed, which is exactly the shape this
command certifies. The thresholds are part of the answer, not something to
smooth over.

The cover shape came from the other direction: three separate write-ups of the
same argument, each reducing to a symmetrised cover program over two, three or
four edge orbits, each stating the value as a minimum of named closed forms,
and each finishing with *"duality completes the proof"*. What duality completes
it **with** is one dual per branch and a check that each stays feasible along
its branch — which is a finite object nobody had written down, and is exactly a
certificate.


## `peak`: the best WHOLE number, for every n at once

A value function peaks somewhere, and if the thing being chosen is a count — a
clique size, a block count, a number of parts — the answer has to be a whole
number. A write-up reaches it like this:

> complete the square, observe the objective is an integer at integer
> argument, conclude the maximum is the **floor** of the continuous peak, and
> attain it at the integer nearest the real vertex

Every step is right, and none of them is checkable, because **the floor of a
parametric expression is not a polynomial**: there is nothing to expand.

This certifies the same thing without one. Move the origin to the claimed
maximiser `x*`; for any integer step `t`,

```
q(x* + t) - q(x*)  =  A t^2 + q'(x*) t
```

which for `A < 0` is `<= 0` for every non-zero integer `t` **exactly when**

```
A  <=  q'(x*)  <=  -A
```

Two polynomial inequalities in the parameters, checked by the same shift
`parametric` uses. No floor anywhere.

```
$ certo peak examples/peak_residues.py
PROVED  [unsat]
  for all m >= 0, no integer beats m, where the value is 3/2*m^2 + 1/2*m
  certificate: integer_peak (no solver needed)
  and that is every integer choice with m >= 0 -- not a sample of them
```

### Why it is the maximum and not an upper bound on it

`x*` is an integer, so the value **is attained**. The certificate says two
things at once: no integer does better, and this integer does that well. Which
is why a maximiser with non-integer coefficients is **refused** rather than
assumed integral — an argument about a point that does not exist proves
nothing.

### The residues are the answer, not an obstacle

Which integer is nearest the vertex depends on the parameter modulo something,
so the family splits and **each class is its own spec**. For the example above,
`n = 3m + j`:

| class | `x*` | `q'(x*)` | value |
|---|---|---|---|
| `n = 3m` | `m` | `1/2` | `m(3m+1)/2` |
| `n = 3m+1` | `m` or `m+1` | `3/2` | `3m(m+1)/2` |
| `n = 3m+2` | `m+1` | `-1/2` | `(m+1)(3m+2)/2` |

The middle row meets the criterion with **nothing to spare**, and that is not
a near miss — it is the tie. The vertex falls exactly halfway, both neighbours
attain the maximum, and both certify. A certificate with slack there would be
describing a different problem.

Same division of labour as everywhere else: certo does not search for `x*`.
Round the real vertex and hand it over.


## `eliminate`: remove a variable, keep the condition

`ideal` says what follows from a system. This answers the other question
people ask while setting one up: **get rid of `t` and tell me what has to be
true of `s`.**

```
$ certo eliminate examples/eliminate_parameter.py
SATISFIABLE  [sat]
  eliminated t. A common root exists only where this vanishes: -4*s^3 + 1
  degrees: 3 and 2 in t
  certificate: resultant (no solver needed)
```

The answer is the **resultant**: a polynomial in the remaining variables that
vanishes exactly when the two share a root in `t`. That example is chosen so
you can check it by hand — substitute `t² = s` into `t³ + st + 1` to get
`2st + 1`, so `t = -1/(2s)`, and back into `t² = s` gives `4s³ = 1`.

What travels is not the number but the **Bézout identity**:

```
$ certo verify out/elim.json
VALID  resultant certificate (checked by expanding two products, no solver)
  [ok] Res = A*f + B*g, by expanding  (resultant: -4*s^3 + 1)
  [ok] the Bezout cofactors have the degrees the construction gives them
```

Computing a resultant is a determinant over a polynomial ring; checking one is
expanding two products and subtracting. That gap is the whole reason this is a
certificate rather than "the algebra system agreed". The determinant itself is
Bareiss — fraction-free, where every division is a polynomial division whose
remainder is **asserted to be zero** rather than assumed.

### A non-zero constant is a refutation

```
$ certo eliminate no_common_root.py
REFUTED  [unsat]
  NO common root in t, for any values of the other variables, over any field:
  the resultant is the non-zero constant 1
```

That is conclusive in the strong direction and costs one determinant.

### What it does not say

`Res = 0` is **necessary** for a common root, over any field. It is
**sufficient** over an algebraically closed field, and only where the leading
coefficients in the eliminated variable do not both vanish. Over the reals a
vanishing resultant may mean a common *complex* root and nothing more.

`verify` repeats that every time, and when both leading coefficients can
vanish it says so specifically — that locus is exactly where sufficiency is
lost.

**Exactly two polynomials**, because that is what a resultant is. Iterating it
pairwise over a larger system introduces extraneous factors that nothing here
could certify away; use `ideal` for that.


## `order`: does this term decay, or is it Theta(1)?

Some bugs are not infeasibilities. A user had this one:

```
5|k| W C^2 / (u^3 d^2 p^10)
```

with `d ≍ n²`, `C ≍ n`, `|W| ≍ n²`. The question was whether it decays in `n`.
It does not — it is **Θ(1)** — and that bug was invisible to Lean **and** to
`certo prove`, for the same reason. It is not an infeasibility. It is a
feasibility that does not improve with `n`, so a solver asked "is this
satisfiable" says yes forever, correctly, while the bound it sits in never
gets better.

```python
OrderSpec(
    expression=5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10),
    orders={"k": 0, "W": 2, "C": 1, "u": 0, "d": 2, "p": 0},
)
```

```
$ certo order examples/order_decay.py
SATISFIABLE  [sat]
  leading exponent 0: it is Theta(1) in n
  collected by exponent:
    n^0      coefficient 5

$ certo order examples/order_decay.py --expect decays
REFUTED  [sat]
  REFUTED: you claimed it decays, and it is Theta(1) -- the leading exponent
  in n is 0
```

What makes it worth a certificate rather than a calculation is that **the
substitution is written down** instead of done in someone's head, and that the
collection is exact: two terms sharing the top exponent whose coefficients
cancel really do cancel, and with `Fraction` that is decided rather than
estimated.

Two limits it states rather than hides:

* **It certifies the exponent, not the constant.** `≍` hides a factor, so a
  Θ(1) term with a coefficient of 1e-9 may be perfectly fine in practice.
  `verify` repeats that every single time.
* **You cannot divide by a sum.** `1/(x + y)` has an order that depends on
  which of `x` and `y` dominates — a question this cannot answer, so it
  refuses rather than guessing.

A symbol with no entry in `orders` is an **error**, not an assumption. The
whole value is that the substitution is explicit.


## `bounds`: numbers, rigorously

`prove` and `farkas` are exact, but algebraic. The moment a proof says "this
constant is below 0.4" and the constant involves `e`, `log`, `π` or `ζ`,
neither can see it at all — and "I computed it and it came out 0.397" is not a
claim about anything. A float carries no statement about the true value.

An enclosure does. Every operation returns an interval that provably contains
the true value, so an inequality that holds for the whole interval holds for
the number.

```python
from certo import BoundSpec

def spec():
    return BoundSpec(
        value=lambda m: m.e / m.pi,     # m = rigorous constants and functions
        claim=("<", "0.866"),           # against an EXACT rational, as a string
        describe="e / pi",
        prec=64,
    )
```

```
$ certo bounds examples/bounds_constant.py --cert out/epi.json
PROVED  [unsat]
  the value is < 0.866 -- established rigorously at 64 bits
  backend: python-flint (Arb)
  enclosure: [0.8652559794322651, 0.8652559794322651]  width 3.062e-19
  precision tried: 64 bits
```

### Precision is the work budget

Exactly as `rlimit` is for Z3. The search starts at `prec` bits and doubles
until the enclosure settles the claim. Ball arithmetic loses accuracy at
cancellations, so **how much precision an expression needs is a property of
the expression, not of the answer** — guessing once and printing whatever came
out is how people end up citing a number they have not established.

And when it runs out, it says so as the third answer, not as a refutation:

```
$ certo bounds cancellation.py       # the value is exp(1) - e, i.e. zero
INCONCLUSIVE  [resource_exhausted]
  the enclosure [-5.99e-154, 5.99e-154] still straddles the bound at 512 bits.
  This is not a refutation: raise max_prec, or tighten the expression where it
  cancels
```

That is the honest answer, and it is one a float result can never give. No
enclosure will ever prove a quantity is non-zero when it is in fact zero.

### What the certificate actually contains

The enclosure travels as **exact rationals**, so verification splits in two
and the halves fail differently:

```
$ certo verify out/epi.json
VALID  ball certificate (verified without a solver)
  [ok] the enclosure is an interval       ([0.8652559794322651, 0.865255979432265])
  [ok] the enclosure settles the claim    (the value is < 0.866)
  [ok] re-evaluating the spec lands inside it
  64 bits via python-flint (Arb)
```

Whether the interval settles the claim is decided by comparing fractions, with
no library involved at all. Whether it is the *right* interval needs the spec
and the same backend — and when that cannot be redone, it is reported as
unchecked rather than quietly passed.

### Floats are refused

`0.1` is not one tenth. It is `3602879701896397/2^55`, and an enclosure built
from it would be perfectly rigorous about the wrong number. So a Python float
anywhere in the expression raises, with that explanation:

```python
value=lambda m: m.pi * 0.5      # refused
value=lambda m: m.pi * m("1/2") # fine, and exact
```

It is the one way the guarantee could quietly be lost, so it is the one thing
that stops the run.

### Backends

| Backend | Covers | Notes |
|---|---|---|
| `python-flint` (Arb) | everything below, plus `gamma`, `lgamma`, `digamma`, `zeta`, `erf`, `erfc`, the inverse and hyperbolic functions | preferred; `pip install python-flint` |
| `mpmath.iv` | `exp`, `log`, `sqrt`, `sin`, `cos`, `tan`, `gamma` | pure Python, usually already installed |

The backend is recorded in the certificate, because a bound is only as good as
what produced it. Asking `mpmath.iv` for `zeta` says so rather than falling
back to a non-rigorous evaluation.

Leave `claim` out to **measure** instead of decide: the certificate then
records the enclosure that was reached, the way `sweep --collect` measures
without refuting.

## `compose`: from a folder of certificates to a proof

Every other command produces a leaf. A proof is "Lemma A and Lemma B,
therefore the theorem", and that join is the part nobody checks. A lemma
proved under one hypothesis and used under a slightly different one is the
classic way an assembled argument goes wrong, and it is completely invisible
when the certificates sit next to each other in a directory.

```python
from certo import ProofSpec, Spec

def spec():
    p = ProofSpec(title="R(3,3) = 6")
    p.assume("n_ge_6", n >= 6)                  # hypothesis of the THEOREM

    p.lemma("upper", certificate="out/r33_k6.json",
            states=(R33 <= 6),
            bridge="the DRAT proof closes the K6 encoding; reading that as "
                   "R(3,3) <= 6 is what the encoding means")

    p.lemma("lower", certificate="out/r33_k5.json",
            states=(R33 > 5),
            bridge="the model is a 2-colouring of K5 with no monochromatic "
                   "triangle, so R(3,3) > 5")

    p.lemma("spare", proves=some_spec)          # discharged now, by `prove`
    p.conclude(z3.And(R33 == 6, n >= R33))
    return p
```

```
$ certo compose examples/compose_proof.py
PROVED  [unsat]
  theorem assembled from 3 lemmas (1 derived and linked, 2 asserted)
  lemmas:
    upper                    BRIDGE     *
    lower                    BRIDGE     *
    spare                    linked
  NOT needed: spare
```

### What is actually checked

A lemma given by `proves=` is **discharged and linked**. Linked means: what
that lemma's certificate really closes *entails* the statement handed to the
final step. The check is uniform, because every certificate worth composing
answers the same question — "which formulas did you prove jointly
unsatisfiable?" — so the link is

```
not(statement)  =>  those formulas
```

which, together with the certificate's own verification (those formulas are
contradictory), gives exactly: the statement is valid. **If the link fails,
nothing is emitted.** A lemma proved for `x >= 1` and declared as `x >= 2` is
refused by name, at the point of assembly.

### Bridges: the honest part

A lemma given by `certificate=` is a **bridge**. A DRAT proof talks about
propositional variables called `e0_1`; it does not talk about a Ramsey number.
The step from "this encoding is unsatisfiable" to "R(3,3) ≤ 6" is the
encoding's *meaning*, and no checker can confirm it.

So bridges are not refused — they are made visible. The certificate is
verified on its own, the step is declared in prose, and it is reported by name
**every single time the proof is verified**:

```
$ certo verify out/proof.json
VALID  proof certificate (verified with a solver)
  [ok] lemma upper holds  (drat: 23 steps (23 RUP, 0 RAT, 0 deletions))
  [ok] lemma lower holds  (cnf_model)
  [ok] lemma spare: its certificate entails the statement used  (2 obligations)
  [ok] the final step holds
  [ok] the final step uses only the lemmas and the theorem's own hypotheses
  [ok] nothing entered the proof undeclared
  WARNING: BRIDGE: upper is asserted, not derived -- the DRAT proof closes...
  WARNING: BRIDGE: lower is asserted, not derived -- the model is a 2-colou...
  WARNING: lemmas the theorem does not need: spare
```

The bridge is in the author's head either way. The difference is whether the
reader can see it and weigh it.

### "NOT needed" comes from the proof, not from a guess

The final step is an ordinary `prove`, so its unsat core says which lemmas the
theorem actually used. Expect this to catch more than you think: over linear
real arithmetic Z3 rederives most auxiliary lemmas by itself, and the ones
that survive as *needed* are precisely those carrying something the theory
cannot reach — which is usually a bridge.

## `farkas`: `linarith` and `nlinarith`, with the certificate attached

Lean's `linarith` closes a goal and tells you nothing about how. `certo
farkas` runs the same search and hands you the reason: the **non-negative
rational multipliers** that combine the hypotheses with the negated goal until
everything cancels and what is left is false.

```python
# examples/farkas_linear.py
import z3
from certo import Spec

def spec():
    x, y, z = z3.Reals("x y z")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise",  z <= 100)      # true, and irrelevant
    s.claim(x + y >= 2)
    return s
```

```
$ certo farkas examples/farkas_linear.py
PROVED  [unsat]
  Farkas (linarith) certificate found: 3 hypotheses with a non-zero multiplier
  multipliers:
    x_ge_1                 1
    y_ge_1                 1
    __goal__               1
  Lean: linarith [x_ge_1, y_ge_1]
```

Three things worth noticing. `noise` is absent, because its multiplier is 0 --
**the certificate says which hypotheses the proof actually uses**, which is
`core` for free and exactly what you need to keep a Lean interface small. The
multipliers are exact rationals, so the result is a proof a referee can redo
on paper: `1*(x-1) + 1*(y-1) + 1*(2-x-y) = 0`, and the negated goal was
strict, so `0 < 0`. And the `Lean:` line is the tactic call to paste, with the
hypothesis list already narrowed.

### `--nonlinear` is `nlinarith`

`nlinarith` is not a different algorithm. It multiplies pairs of hypotheses,
throws in some squares, treats each monomial as a fresh variable, and runs the
linear search on that. `--nonlinear` does the same, faithfully, heuristic and
all:

```
$ certo farkas examples/farkas_nonlinear.py --nonlinear
PROVED  [unsat]
  degree-2 Positivstellensatz (nlinarith) certificate found: 2 hypotheses
  multipliers:
    __goal__               1
    sq_a_b                 1
  Lean: nlinarith
```

The goal was `a^2 + b^2 >= 2ab` and `sq_a_b` is the row `(a-b)^2 >= 0`. That
is the human proof of that inequality, rediscovered -- and named, so the
write-up writes itself.

### Verification uses no solver at all

```
$ certo verify out/farkas.json
VALID  farkas certificate (verified without a solver)
  [ok] every multiplier is non-negative  (2 of 5 non-zero)
  [ok] the combination cancels every monomial  (left over: )
  [ok] the remaining constant is a contradiction  (0 < 0 is false)
  [ok] the declared constant and strictness match  (0)
  WARNING: 4 rows are products or squares derived from the hypotheses
  5 rows combined; pure exact arithmetic
```

The certificate carries the rows, so checking it is adding fractions. No Z3,
no LP, nothing to trust. That warning is deliberate: in `--nonlinear` mode
some rows are *derived*, and the reader should know which.

### When it finds nothing

`farkas` is **incomplete on purpose**, in both modes -- Farkas is complete for
linear real arithmetic, but only once the right rows are present, and in
`--nonlinear` mode which products to add is a guess. So "no certificate" never
means "false"; it means this search did not close it. `prove` uses Z3's
`nlsat`, which *is* complete for real arithmetic. The division of labour:

> **`prove` to know. `farkas` to certify.**

A linear-only run on a nonlinear goal says so and points at `--nonlinear`
rather than reporting failure.

<details>
<summary>Why not a real SOS certificate through an SDP?</summary>

Because an SDP is solved in floating point, so what comes back is not exact,
and an inexact certificate is not citable -- the same reason `opt` reconstructs
rationals instead of printing the solver's floats. A degree-2 heuristic whose
output is exact beats a degree-*d* one whose output needs a caveat.
</details>

## Exact mode in `opt`

CBC works in floating point: it returns `10.66666656003499` where the answer
is `32/3`. With that you cannot assert primal-dual equality or cite a
constant.

`certo` solves in floating point, **reconstructs rationals and verifies in
`Fraction`**, accepting only if the exact check passes — so a bad
reconstruction rejects itself:

```
$ certo opt examples/lp_mixed_packing.py
  EXACT optimum certified: 25/2 (denominator <= 6)
  min_dual: 5/6

$ certo verify out/lp.json
VALID  lp_dual certificate (verified without a solver)
  [ok] primal non-negative (x >= 0)
  [ok] primal feasibility (A x <= b)
  [ok] dual non-negative (y >= 0)  (min(y)=5/6)
  [ok] dual feasibility (A^T y >= c)
  [ok] exact strong duality (c.x == b.y)  (c.x=25/2 | b.y=25/2)
  EXACT rational arithmetic, no tolerances
```

Coefficients accept `int`, `Fraction`, the string `"7/12"` or `float`:

```python
lp.objective({"x": Fraction(7, 12), "y": "1/3"})
lp.constraint({"x": 1, "y": 1}, "<=", Fraction(1, 2), name="cap")
```

`--no-exact` skips the reconstruction; the certificate stays in floating point
and `verify` flags it as **not citable**.

## Citable sweeps

A predicate returning `True`/`False` leaves the sweep half-done: the
certificate attests **which family** was examined, but not that the predicate
was evaluated correctly on each graph. If there is a floating-point LP inside,
that is precisely the part a referee would want to check.

Return an `Outcome` and the sweep becomes citable:

```python
from certo import Outcome

def pred(g):
    res = lp.opt(packing_lp(g))
    return Outcome(ok=..., cert=res.certificate,
                   detail="W* = " + res.meta["objective"])
```

`verify` checks them in cascade; if they are missing, it warns. See
[`examples/sweep_certified_lp.py`](examples/sweep_certified_lp.py).

`ok=None` means "did not conclude". A predicate that crashes or fails to
conclude no longer brings down the whole sweep, but it does block the claim
that the property holds across the family. A counterexample, by contrast,
refutes even if other graphs failed.

## Calibrate, not just refute

Often the question is not "does it fail?" but "**how much** does it fail, and
where is it worst?". `SweepSpec` takes a `collect` for that:

```python
SweepSpec(n=5, filters=["connected"], collect=lambda g: ratio(g), worst="min")
```

```
$ certo sweep spec.py --worst 3
CALIBRATION over 21 graphs: min=2/5 (D?{)  max=1 (D~{)  mean=13/21
  3 lowest: D?{ 2/5 | DCw 2/5 | DEg 2/5
```

Return a `Fraction` and the statistics stay **exact**: `2/5`, not `0.4`. The
certificate stores the values and `verify` recomputes min, max and mean to
check they agree. `predicate` is optional — you can measure without refuting
anything — and you can also return `Outcome(..., value=...)` from the
predicate so nothing is computed twice.

## From bounded candidate to theorem

`synth` searches a **bounded** domain: it finds a candidate, it proves nothing
about the rest. Getting from there to the general statement used to be a
manual step, which is where mistakes creep in. `--prove-candidate` chains it:

```
$ certo synth examples/synth_prove_identity.py --prove-candidate
CANDIDATE SYNTHESISED -- BOUNDED search  [sat]
  synthesised object:
    A = 2
    B = -2
  domain: And(x >= 1, x <= 20)

UNIVERSAL SYMBOLIC PROOF: PASS  [unsat]
```

The combined certificate carries both halves and `verify` checks each one
separately — because they say different things: the first is a **bounded
discovery**, the second a **theorem**.

The spec has to declare what the general statement is, because it is not
derivable: it usually changes the domain **and the sort**. The search runs
over bounded integers and the proof over the reals, which is where polynomial
arithmetic is decidable.

```python
SynthSpec(
    ...,
    behavior=z3.And(x >= 1, x <= 20),          # bounded search domain
    universal=lambda vals: Spec().claim(...),  # general statement
    # or, the simple case:  universal_behavior=<expr replacing behavior>
)
```

## Beyond graphs

Graphs are one domain among many. `DomainSpec` runs the same exhaustive
pattern -- same six states, same predicate certificates, same calibration --
over anything you can enumerate:

```python
from certo import DomainSpec, Outcome

def spec():
    return DomainSpec(
        items=[(s, r) for s in range(2, 8) for r in range(2, 8)],
        predicate=lambda p: bound_holds(*p),
        collect=lambda p: ratio(*p),
        key=lambda p: "s={},r={}".format(*p),
    )
```

`key` turns an item into a stable id: it is what lands in the certificate, so
it must identify the item unambiguously. `verify` checks the ids are unique;
what it cannot check is that the domain is COMPLETE -- the spec defines it.

### Programmable filters

`filters` accepts callables alongside the named ones, so a family the
catalogue does not know still gets counted properly:

```python
SweepSpec(n=6, filters=["connected", is_split], predicate=...)
```

The counts stay separate (`enumerated` before filtering, `in_family` after),
and `verify` says plainly that a programmable filter cannot be re-checked from
the certificate alone, because it lives in the spec.

### From which n does it fail?

```bash
certo sweep spec.py --n-range 3..8 --stop-on-first
```

```
n=3   proved         the predicate holds on all 2 graphs with n=3
n=4   refuted        REFUTED: 1 counterexamples out of 6 examined
range n=3..6: first failure at n=4
```

One sub-certificate per size, each verified on its own. What the range adds is
the ORDER and the claim that nothing failed below the first failure. With
`--stop-on-first` the larger sizes were never run, and the certificate records
that.

## Local loads: named regions the design has to respect

A packing certificate proves an optimum. The thing an argument usually needs
next is different: **and the design holds the bounds I put on each region, by
this much, and that one cost me this.**

```python
PackingSpec(
    items=..., capacities=1,
    loads=[("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2),
           ("within_B", {"p3": 1, "p4": 1, "p5": 1}, "<=", 5)],
)
```

```
$ certo opt examples/packing_with_loads.py
  EXACT optimum certified: 5 (denominator <= 1)
  2 declared loads, and what the design does to them:
    within_A         2 <= 2   BINDING
                     costs 1 per unit of bound -- relaxing it buys that much
    within_B         3 <= 5   slack 2
```

Read the second column. `within_A` is **binding** and its shadow price is 1:
relax that bound by one and the optimum goes up by exactly one. `within_B` has
slack 2, so it is not what is holding you back and tightening the argument
there buys nothing. That is the difference between a bound doing work and a
bound along for the ride — and it is free, because a load is a row and the
dual already priced it.

A capacity is part of the **encoding**; a load is part of the **argument**.
They are declared separately for that reason, and the certificate reports them
apart.

`verify` recomputes each achieved value from the primal rather than believing
the declared one, so a certificate that understates what a region used fails:

```
[XX] load `within_A` holds, and at the declared value   2 <= 2, slack 0
```

Loads take `<=`, `>=` or `==`. The last is exact preservation — *this region
carries exactly this much* — which is what "preserve these local loads" means
when the argument depends on the value rather than a ceiling.

Refused rather than accepted quietly: a weight on an item that is not in the
packing, and a load name that collides with a resource.


## Packings

Cliques competing for edges, blocks competing for points -- the shape recurs,
and rebuilding the LP by hand each time is where mistakes hide.

```python
from certo import PackingSpec
from certo.graphs import Graph

def spec():
    g = Graph.from_edges(6, [...])
    return PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
```

`to_lp()` hands back an `LPSpec`, so exact rationals and the verifiable dual
come for free. **The dual is the load certificate**: constraint names are
resource names, so `y_r` reads as "the load on resource r" -- usually the
object you actually wanted.

```bash
certo opt examples/packing_mixed.py --by-type
```

```
  mixed      25/2       EXACT optimum certified: 25/2
  K3         10         EXACT optimum certified: 10
  K4         25/2       EXACT optimum certified: 25/2
```

Whether mixing buys anything is the gap between the mixed optimum and the best
single kind. Here, on K6, it buys nothing over pure K4.

## When rounding a float dual stops working

`opt` reconstructs a rational primal and dual from a float solver and checks
them exactly. There is a regime where that cannot work: a **degenerate**
optimum, where many dual solutions are optimal and the one CBC returns need
not round onto any of them.

0.6.0 answered that by deriving the dual from complementary slackness and
enumerating which tight rows carry the weight. Measured on a realistic exact
cover — 98 rows, **49 of them tight, 7 active variables** — that is C(49, 7)
candidate bases, about 10⁸. The approach is right for a handful of tight rows
and hopeless past it.

So past that, certo solves the dual outright with a **two-phase simplex in
exact rationals**: no floats anywhere, Bland's rule throughout, which is
slower than steepest-edge and cannot cycle. Termination matters more than
speed in a fallback that only runs when the cheap route has already failed.

Nothing it produces is trusted for being produced there. The result goes
through the same `check_lp` as a rounded guess, so a bug in it shows up as a
certificate that does not verify — never as a wrong one that does.


## Exact mode stopped depending on CBC's dual

A user certified 56 LPs exactly and **3 needed the rational primal and dual
injected by hand** — all of them on symmetric solutions. That is not bad luck.
On a degenerate vertex several duals are optimal, CBC returns an arbitrary one
of them, and rounding *that particular one* need not be dual-feasible at all.

The fix is not a longer denominator ladder. Given an exact primal,
complementary slackness determines the dual: `yᵢ = 0` on every row with slack,
and `Σᵢ Aᵢⱼ yᵢ = cⱼ` for every `j` with `xⱼ > 0`. That is a linear system over
the tight rows, solved in `Fraction` by Gaussian elimination with no floats
anywhere. Where it underdetermines the dual — more tight rows than active
variables, which is exactly what symmetry produces — the leftover freedom **is**
the set of optimal duals, so each choice is offered in turn.

```
max 2x + 3y   s.t.  x + y ≤ 1,  x + 2y ≤ 1,  x, y ≥ 0
```

Both rows are tight at the optimum and only one variable is active. Certifying
it now works with **no usable dual from the solver at all**:

| what CBC returned | certified | dual used |
|---|---|---|
| nothing (`0, 0`) | yes | `(0, 2)` |
| nonsense (`7.3, -2.1`) | yes | `(0, 2)` |
| another vertex's dual | yes | `(0, 1.5)` → `(0, 2)` |

A derived dual is **not** trusted for being derived. It is a candidate, like a
rounded one, and it earns the certificate by passing the identical exact
`check_lp`. What changed is where candidates come from: the structure of the
problem rather than whatever a float solver landed on.

Reconstruction still runs first, so every LP that certified before certifies
the same way, with the same simplest denominator and the same digest.


## The most-used command stops needing a solver

An `unsat_core` said "z3 agreed with me", and `verify` re-ran z3 to check.
A user put the objection precisely: *useful, but not solver-free like a
rational Farkas certificate.*

It is now solver-free whenever the core is linear arithmetic. After the core
is found, the Farkas search runs on exactly those rows, and the multipliers
travel in the payload:

```
$ certo prove examples/farkas_linear.py --cert core.json
  certificate: unsat_core (no solver needed)

$ certo verify core.json
VALID  unsat_core certificate (checked by arithmetic, no solver: Farkas multipliers)
  [ok] every multiplier is non-negative
  [ok] the combination closes: sum of lambda_i * row_i is a contradiction
       (constant 0, and < 0 is false)
  3 rows carry a non-zero multiplier: x_ge_1, y_ge_1
```

Floating point in the search does not compromise that. The LP is a way of
**finding** the multipliers; `is_contradiction` accepts or rejects them in
exact `Fraction` arithmetic, independently, so a bad guess is rejected rather
than believed. Same discipline as `opt` and `sos`.

The core stays in the payload either way — `compose` reads it for the
entailment check — and the multipliers are optional fields, which the frozen
schema allows. A 0.5 reader verifies the certificate exactly as before.

### And the Lean export stops saying `sorry`

These were reported as two separate gaps. They have one fix. A core used to
export with `sorry` precisely because it says *which* hypotheses suffice and
not *why*; with the multipliers it knows why:

```lean
theorem from_core (x y : ℝ)
    (x_ge_1 : 1 - x ≤ 0)
    (y_ge_1 : 1 - y ≤ 0)
    : -2 + x + y ≥ 0 := by
  linarith [x_ge_1, y_ge_1]
```

A vacuous regime becomes a compiling proof that it is empty:

```lean
theorem regime_empty (dens : ℝ)
    (dens_floor : (3/4 : ℚ) - dens ≤ 0)
    (sparse : (-1/2 : ℚ) + dens ≤ 0)
    : False := by
  linarith [dens_floor, sparse]
```

CI compiles both against Mathlib v4.28.0 on every push. Outside linear
arithmetic nothing changes: no multipliers, `sorry`, and the file says why.


## Is my regime non-empty? Ask it directly

The natural way to ask is `s.claim(z3.BoolVal(False))` — and it is the one
phrasing that cannot answer. `check` decides `hypotheses AND claim`, so with a
claim of `False` it reports UNSATISFIABLE whatever the hypotheses are. A user
asked exactly that, on a system that has models, and was told "no model
exists". They only found out by going to `core`.

```
$ certo check regime.py
UNSATISFIABLE  [unsat]
  no model exists -- but the claim is the literal False, so this says nothing
  about the hypotheses. Ask with `--hypotheses-only`.
  !! the claim is the literal False: `check` decided `hypotheses AND False`,
     which is unsatisfiable whatever the hypotheses are.
```

```
$ certo check regime.py --hypotheses-only
SATISFIABLE  [sat]
  the regime is NON-EMPTY: all 3 hypotheses hold together, and here is a
  point where they do
  certificate: model (no solver needed)
```

The certificate is a **model**, which is solver-free: the non-emptiness of a
regime is one of the few answers here that re-checks by evaluation alone. The
same user called exhibiting the full parameter set simultaneously the first
time in four iterations they had done it rather than argued it.

And when the regime IS empty, you get the minimal clash rather than the whole
hypothesis set:

```
$ certo check empty.py --hypotheses-only
UNSATISFIABLE  [unsat]
  the regime is EMPTY: these hypotheses cannot hold together.
  The minimal clash is: dens_floor, sparse
```

`certo lint` warns about a constant claim before any of this, and `prove`
reports vacuity after the fact. This is the same question asked head on.

## An unsat core, stated in Lean

`export --lean` used to refuse an `unsat_core` — the kind the most-used
command produces. For a core over linear arithmetic it now emits real Lean:
binders, hypotheses, the goal stated positively, and `sorry`.

```lean
theorem from_core (a b : ℤ)
    (a_big : 10 - a ≤ 0)
    (b_small : -3 + b ≤ 0)
    : -7 + a - b ≥ 0 := by
  sorry    -- certo: a core says WHICH hypotheses suffice, not why.
           -- `certo farkas` on the same spec produces the multipliers.
```

The sort is read off the formulas rather than assumed, because an integer
regime emitted over the reals elaborates fine and says something weaker than
what was certified. The hypotheses certo **dropped** are listed at the bottom:
that list is the content of the certificate.

`sorry` and not a tactic call, deliberately. A core says which hypotheses
suffice; it does not say why, and nothing in it licenses `linarith`. `certo
farkas` on the same spec produces the multipliers, and its export compiles.

A **vacuous** core is the interesting one. The hypotheses are jointly
contradictory, so `h₁ → … → False` is a theorem — and that is the emptiness of
the regime, stated in Lean:

```lean
theorem regime_empty (dens : ℝ)
    (dens_floor : (3/4 : ℚ) - dens ≤ 0)
    (sparse : (-1/2 : ℚ) + dens ≤ 0)
    : False := by
  sorry
```

Outside linear arithmetic it carries the SMT-LIB2 verbatim and says so. certo
does not know your Mathlib encoding and will not guess at one.


## `lint`: before the compute is spent

Every other command answers a question. This one asks whether the question is
well posed, and it is the cheapest thing in the tool.

```
$ certo lint examples/lint_vacuous_regime.py
Spec -- for `certo prove / check / core`
  [XX] the hypotheses contradict each other, so any proof will be VACUOUS --
       valid and about nothing. The clash is: kappa_large, density_high, sparse
  1 errors, 0 warnings, 0 notes
```

`certo prove` on that same file also reports the vacuity — after reporting
`PROVED`, which is the moment somebody decides the run went well. Asking
first costs one solver call on a strictly easier problem than the proof.

Note which hypotheses it names. `n_large` is in the set, is consistent with
everything, and is not blamed: the clash is **minimal**, so the next question
is already answered.

Three more that pay for themselves:

| Finding | Why it matters |
|---|---|
| the inductive step starts after the base cases end | `induct` refuses this too — after discharging every base case, which is where the hours go. Here it is a comparison of two integers. |
| the predicate returns `bool` | Then the sweep will be `reproducible`, not `certified`. People who wrote the predicate themselves have read that difference wrong. |
| `integer=True` makes **all** variables integer | A user read it as "there are integers in here" and got a design worth nothing, every weight rounded to zero. |

It also counts the domain without building it — `items=lambda: iter(range(10**7))`
is peeked at, never materialised — and reads the size of a graph family from a
table, so `certo lint` on 11 vertices answers in the time it takes to read the
file rather than the time the sweep would take.

Loading a spec **executes** it; that is how specs work here. Beyond that, lint
calls the predicate at most once and never runs the solver on the goal.

Exit codes: `0` clean or notes only, `1` errors, `2` warnings.

## `status`: where the proof stands

Twenty-eight commands and thirty-two certificate kinds, and the shape of a
project used to live only in the head of whoever ran them.

```
$ certo status out/
19 certificates under out
  sweep 6   unsat_core 4   proof 3   farkas 2   gap 1   induction 1   sos 1   order 1

  RESULTS -- 9 certificates nothing else here builds on
  gap            out/walkthrough.json   the walkthrough's canonical core
  proof          out/main.json          every 2-connected K4-free graph...

  STILL OWED -- 3 assumptions these results rest on
  main.json: density_bound
      "the counting argument of section 3"
  walkthrough.json: optimality
      "the integral side is conditional_optimum, so nu is a value reached,
       not a proved maximum"

  HOLLOW -- 1 claims that are valid and say less than they look like
  regime.json: VACUOUS: the hypotheses contradict each other -- the clash is
               density_high, sparse

  STALE -- 2 certificates whose spec has moved
  sweep_n7.json: the spec changed since this was issued: specs/sweep7.py

  read, not verified. `certo status --verify` re-checks every one.
```

Four sections, in the order they matter.

**RESULTS** are the certificates nothing else in the directory builds on. A
lemma's certificate is not a result; the proof standing on it is.

**STILL OWED** is every bridge and every unclaimed optimality, including ones
reached three levels down — a bridge inside a lemma inside a proof is still
owed by the proof. Bridges are legitimate and often unavoidable. Losing count
of them is not, and they are easy to lose precisely because everything around
them verifies.

**HOLLOW** is what is valid and says less than it looks like: a vacuous proof
with its clash named, a sweep whose predicate nothing certified, an optimum
that is a value reached rather than a maximum proved.

**STALE** is a certificate whose spec has changed since it was issued. It is
not wrong — it verifies on its own — but it no longer describes the file next
to it, and six months later nobody remembers which.

It **emits no certificate**, deliberately. `status` makes no claim; it reads
the claims other commands made. A report that certified itself would be the
one artefact here that nobody had checked.


## Lean export

```bash
certo export out/shrink.json --lean --out Counterexample.lean
```

It emits the counterexample as Lean 4 **data** plus a skeleton around it. The
split is deliberate and the emitted header says so:

It **compiles**: checked against Lean v4.28.0 with the matching Mathlib,
including the two `example` sanity checks, which are real proofs by `decide`.
Another version may need adjusting; the edge list is exact either way.

Getting there took three rounds against a real compiler -- `loopless` could
not be `decide`d, and `edgeFinset` is not in `SimpleGraph.Basic` -- which is
precisely why emitting Lean without compiling it is a bad idea. It uses
`SimpleGraph.fromRel`, which symmetrises and drops loops itself, so there are
no obligations left to break when Mathlib moves `Irreflexive` around.

It exists because transcribing a counterexample into Lean by hand is
mechanical, and mechanical transcription is exactly where errors creep in.

## `core` over several goals

Running `core` once per goal already says which hypotheses that goal needs.
What the table adds is the COMPARISON, and that is what decides how small a
downstream Lean interface can be.

```
$ certo core examples/core_matrix.py
  hypothesis  identity  positivi  ordering
  r_ge_3            no       yes        no
  d_ge_1            no        no        no
  d_le_r            no        no       yes
  never used by any goal: d_ge_1
```

A hypothesis irrelevant to the identity but necessary for positivity is
invisible when the goals are looked at one at a time. The certificate carries
one core per goal, and `verify` also checks that **the table says exactly what
the cores say**.

## Minimise over any domain

`shrink` takes a `DomainSpec` too, but it has to know what "one step smaller"
means. There is no sensible default, so it is declared:

```python
DomainSpec(..., reduce=lambda p: [(p[0] - 1, p[1]), (p[0], p[1] - 1)])
```

The trace records the INDEX taken into `reduce()` at each step, not just the
resulting id -- which is what lets verification replay the exact descent
instead of re-running the search.

## Audit ledger

Six months later, "we checked that" is worth nothing without the artefact.

```bash
certo opt spec.py --cert c.json --log --note "K6 bound" --tag paper
certo ledger verify
```

```
  [ok] 2026-09-16T00:45:23  core     core of 4 formulas
  [!!] 2026-09-16T00:45:25  opt      digest 3653579e... != logged 681631ea...
  2 entries: 1 verified, 0 FAILED, 1 changed since logged
```

Two deliberate properties: it is **append-only** -- a later run that
contradicts an earlier one is a new line, not an edit -- and it **stores no
copies**, only each certificate's path and digest. `ledger verify` re-reads
and re-verifies them, so a tampered or missing certificate shows up as a
failure rather than being quietly duplicated into the log.

## Scope shows up on screen

A bare `PROVED` invites reading a bounded synthesis as a theorem. Each command
says which scope it is talking about: `CANDIDATE SYNTHESISED -- BOUNDED
search`, `FINITE CASE VERIFIED -- not the theorem`, `PROVED -- symbolic and
universal under the hypotheses`.

## Languages

English is the default and the source of truth. Spanish ships as an overlay:

```bash
certo core examples/amgm.py --lang es      # or CERTO_LANG=es
```

Translations live in [`src/certo/locales/`](src/certo/locales/) as JSON. A
missing key falls back to English, so a partial translation degrades instead
of breaking. To add a language, copy `en.json`, translate the values and keep
the `{placeholders}` — there is a test that enforces both invariants.

Two things deliberately stay English whatever `--lang` says, because they are
API surface rather than prose: **command names and flags**, and **MCP tool
names and descriptions**. Certificates store note **keys**, not rendered text,
so one issued in Spanish reads correctly for an English reader.

## MCP server

Every command exposed to the LLM, with no copy-pasting. The project
ships a ready [`.mcp.json`](.mcp.json); to register it by hand in Claude Code:

```bash
claude mcp add certo --env CERTO_WORKSPACE=. -- certo-mcp
```

`CERTO_WORKSPACE` (the current directory by default) holds `specs/` and
`certs/`. **Every path is confined there.**

Three design decisions:

1. **Certificates do not come back in the response.** A MUS takes 18× more on
   disk than the whole response, and the model cannot verify it by reading it.
   They are written to disk and the path, kind and digest come back.
2. **Errors come back as data, not as exceptions.** The SDK turns any
   exception into `Error executing tool X` and swallows the reason; a model
   reading that cannot fix its spec. Here it gets what happened and what to
   correct.
3. **`dsl_guide` first.** Both a tool and a resource (`certo://dsl`).

> **Specs are Python code and they get executed when loaded.** That is
> inherent to the DSL and it is the same level of trust an agent with file
> access already has. The server confines paths, but it **is not a sandbox**:
> do not point it at third-party specs.

## What it does not do

This section matters as much as the list of twelve commands.

**The hard limit is asymptotic statements with quantifiers over `n`.** "There
exists `N` such that for every `n ≥ N`, every graph…, the loss is `≤ εn²`" is
not decided by this tool. `prove` and `synth` work over decidable formulas or
bounded domains; `sweep` and `cases` over finite families.

The ladder, with Ramsey numbers as the example:

| Question | `certo`? |
|---|---|
| Is R(3,3) ≤ 6? | **Yes.** `cases`, a 23-line DRAT proof, verified |
| Is R(3,3) = 6? | **Yes.** `bisect`, threshold certified on both sides |
| Is R(5,5) ≤ 48? | **Not in practice.** Finite, but the space is 2^903 |
| Does R(k,k)^(1/k) converge? | **No, in principle.** Asymptotic: not expressible |

More limits, also stated in each run's output:

- `sweep` and `cases` settle the **finite case**, not the theorem.
- The `graph_set` certificate verifies non-isomorphism and the filters, **not
  completeness**.
- For an ILP the dual certifies the **relaxation bound**, not integer
  optimality.
- `shrink` gives a **1-minimal, not minimum** counterexample.
- `bisect` **assumes monotonicity** in the parameter; it checks the endpoints
  and warns if they do not behave, but monotonicity itself is not proved.
- Quantifier elimination over the reals is doubly exponential and hangs on
  textbook examples; that is why `qe` is not among the commands.

**The niche is clear:** discover objects, destroy false formulations and
minimise hypotheses before paying the cost of formalising them.

## FAQ

**Is this a theorem prover?**
No. It decides formulas in decidable theories and verifies finite cases. For
the theorem, Lean or Rocq. `certo` is the layer before.

**If I already trust Z3, what is the certificate for?**
So that whoever reads your paper does not have to. A Z3 `unsat` is an
assertion; a verified DRAT proof is something a referee checks on their own
machine without running your code. It is also a safety net: if the solver had
a bug, the certificate would not verify and you would get `ERROR`, not
`PROVED`.

**What does `unknown_solver` mean? Is it "does not exist"?**
No. It means the solver finished without concluding. `timeout` is the clock
running out, `resource_exhausted` the budget, `out_of_theory` the formula
falling outside the decidable fragment. All four differ from `unsat`, which
does mean "does not exist".

**Why did my `opt` come out in floating point?**
Because no rational reconstruction verified exactly. The result is still
useful for exploring, but `verify` flags it as not citable. It usually happens
when the input data were already floats: pass them as `Fraction` or as the
string `"7/12"`.

**Why is the built-in SAT solver slow?**
Because it is a CDCL in Python. It exists because pysat's proof logging does
not work on Windows — it returns 0 lines with every one of its solvers — and
without a proof there is no certificate. For large instances:
`certo cases spec.py --solver-binary /path/to/cadical`.

**Can I trust that CDCL?**
You do not have to. If it emitted a malformed proof, the DRUP checker rejects
it and you get `ERROR`. There is also a differential test against Z3 over
random CNFs. **The checker audits the solver.**

**Are results reproducible?**
Those of our engines are: the budget is work, not time. Your `sweep` predicate
is outside that guarantee.

**What if I change the spec after generating a certificate?**
`verify` still accepts it — it verifies on its own — but warns that it no
longer corresponds to the current file.

**Does `synth` prove anything?**
It finds a candidate in the bounded domain you declared. That is a discovery,
not a theorem, and the banner says so. For the general statement, use
`--prove-candidate`.

**How do I connect this to Lean?**
By hand today: `certo` gives you the counterexample, the synthesised value or
the hypotheses that are actually needed, and you write the statement.
Automatic export of counterexamples to Lean definitions is on the list.

**Can I use it offline with nothing else installed?**
Yes. `z3-solver` and `pulp` ship their binaries; the rest is pure Python.

## Tests

253 of them, no test framework required.

```bash
for t in smoke mcp i18n extras; do python tests/test_$t.py; done
```

Release notes in [CHANGELOG.md](CHANGELOG.md); what is planned, blocked
and deliberately refused in [BACKLOG.md](BACKLOG.md).

## Licence

MIT. The synthesis engine is a reimplementation of the CEGIS algorithm from
[marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (MIT), not of its code.
