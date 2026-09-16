# certo

A laboratory for supporting mathematical proofs, over CLI and over MCP.
**Every result comes with a certificate that verifies without trusting the solver.**

Twenty-two commands to discover objects, destroy false formulations, calibrate
constants and minimise hypotheses — before paying the cost of formalising.

```
$ certo bisect examples/bisect_ramsey.py
THRESHOLD BRACKETED by a proof and a refutation  [sat]
  threshold at 6 (holds at t=6, fails at t=5; 4 probes)

$ certo verify out/r33.json
VALID  bisect certificate (verified without a solver)
  [ok] good side t=6 (drat)        (23 RUP steps)
  [ok] bad side  t=5 (cnf_model)
```

*Español: [README.es.md](README.es.md) · run any command with `--lang es`.*

## What it is and what it is not

**It is** the lab instrument: find a contradiction fast, learn which
hypotheses are redundant, exhaustively validate a finite case, bracket a
constant with a certificate, synthesise a candidate over a bounded domain.

**It is not** a proof assistant — that is Lean, Rocq or Isabelle — nor a
computer algebra catalogue. See [What it does not do](#what-it-does-not-do),
which matters as much as the command list.

## Install

Requires Python 3.11+.

```bash
pip install -e ".[mcp,numerics]"
```

Dependencies: `z3-solver` and `pulp`, both of which ship their binaries. The
extras are `mcp` for the MCP server and `numerics` for `bounds` (`python-flint`
and `mpmath`); without them you get the CLI, minus rigorous numerics.

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

## The twenty-two commands

| Command | What it does | Engine | Certificate |
|---|---|---|---|
| `prove` | Negate the claim, look for `unsat` | Z3 | unsat core, or counterexample |
| `check` | Plain satisfiability | Z3 | model, or core |
| `core` | MUS: which hypotheses are needed | Z3 | minimal core |
| `farkas` | `linarith` / `nlinarith`, with the multipliers | exact LP | **Farkas certificate**, solver-free |
| `compose` | Assemble lemmas into one proof, checking the join | Z3 | **proof**: every lemma, its certificate, and the link |
| `induct` | Base cases + a step, and the check that the chain joins | Z3 | **induction**: both halves, and the two numbers that matter |
| `synth` | CEGIS: ∃obj ∀input ∃aux | CEGIS/Z3 | object + the counterexamples that forced it |
| `opt` | LP/ILP, or a packing | CBC | **dual in exact rationals** = the load certificate |
| `mixed` | A discrete skeleton searched, the continuous part certified | CBC + exact LP | **mixed design**: assignment, exact dual, and a bound |
| `bounds` | A numeric inequality, rigorously (`e`, `log`, `π`, `ζ`) | Arb or mpmath | **enclosure in exact rationals** |
| `ideal` | Polynomial systems: refute them, or certify what follows | Gröbner, ours | **cofactors**, checked by expanding |
| `sos` | A polynomial is non-negative, as a sum of squares | numeric + exact rounding | **rational squares**, solver-free |
| `number` | Primality, or a factorisation | Pratt | **modular-exponentiation tree** |
| `cases` | SAT with a verified DRAT proof | own CDCL or external binary | DRAT proof |
| `enum` | Non-isomorphic graphs with filters | nauty or Python | canonical list + hash |
| `sweep` | Predicate and/or value over a family or ANY finite domain | nauty or Python | family **+ predicate certificates** |
| `shrink` | Minimise a counterexample (graph or MUS) | CDCL / reduction | minimality witness |
| `bisect` | A constant's threshold | prove or cases | the pair that brackets it |
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
| `SOSSpec` | `sos` |
| `NumberSpec` | `number` |
| `BoundSpec` | `bounds` |
| `BisectSpec` | `bisect` |

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
| `ball` | a real quantity lies in an interval, and that settles the claim | **yes** for the claim; the interval needs the spec |
| `proof` | the lemmas, **and** that each is used as its certificate allows | no, re-solves |
| `induction` | the base cases, the step, **and** that they chain without a gap | no, re-solves |
| `mixed_design` | a construction exists and attains a value; NOT that it is optimal | **yes**, exact arithmetic |
| `ideal` | `f = Σ hᵢgᵢ` | **yes**, expand a product |
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

240 of them, no test framework required.

```bash
for t in smoke mcp i18n extras; do python tests/test_$t.py; done
```

Release notes in [CHANGELOG.md](CHANGELOG.md); what is planned, blocked
and deliberately refused in [BACKLOG.md](BACKLOG.md).

## Licence

MIT. The synthesis engine is a reimplementation of the CEGIS algorithm from
[marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (MIT), not of its code.
