# Changelog

Notable changes per release. Dates are ISO. This project uses semantic
versioning; while the major is 0, a minor bump may change a certificate
payload — each such change says so and what still reads the old shape.

## [Unreleased]

### `certo cover`: is this really a clique partition, and how large?

Somebody hands you a clique partition and says it has 47 parts. Two things
have to be true and neither is visible by looking: every part really is a
clique, and every edge is covered EXACTLY once — not zero times, which makes
it not a cover, and not twice, which makes the count a lie. Checking both is
counting: no solver, no search, no trust in whatever produced it.

```
$ certo verify out/clique_partition.json
VALID  exact_cover certificate (checked by counting, no solver)
  [ok] every element of the universe is covered  (0 missed: -)
  [ok] and covered exactly once  (0 covered more than once: -)
  [ok] every part really is a clique of the graph  (0 parts are not)
```

The general object is an exact cover — a universe and parts, each element in
exactly one — and a clique partition is that with the edge set as the universe.
So the machinery is written once and the graph case adds the check a cover
cannot make: that a part's edges really are ALL the edges among its vertices.

Three failures, reported as three different things. A part that is not a
clique is a statement about the graph, so the run stops **inconclusive** with
the offending pairs named and writes no certificate. An edge covered twice or
zero times is **REFUTED**, named, and in the first case told that `exact=False`
would make the same data valid — an at-least cover is a weaker and reasonable
claim, recorded as a different one rather than left for a reader to assume.

**It is an upper bound.** That the size is minimum is a different statement,
and the exact rational dual from `opt` on the same universe is a lower bound
for it; where the two meet the number is proved, which is the pairing
`opt --gap` already makes for packings. Finding a minimum cover is NP-hard and
deliberately not what this does.

Built from a real audit that sends a graph plus a partition, and a graph plus
dual weights, to an external service for checking. The difference in model is
the point: a certificate carries its own check, so the same audit does not
need the service to still be running in six months.


### Local loads: named regions a packing has to respect

A packing certificate proved an optimum and could not say the thing an
argument usually needs next: *and the design holds the bounds I put on each
region, by this much, and that one cost me this.*

`PackingSpec(loads=[("within_A", {...}, "<=", 2)])` declares them, and they
become rows like any other — so the dual prices them for free:

```
2 declared loads, and what the design does to them:
  within_A         2 <= 2   BINDING
                   costs 1 per unit of bound -- relaxing it buys that much
  within_B         3 <= 5   slack 2
```

That second column is the point: a binding region with a shadow price is doing
work, one with slack is along for the ride, and knowing which is which is what
tells you where to spend effort tightening an argument.

A capacity is part of the ENCODING; a load is part of the ARGUMENT. They are
declared separately for that reason, and reported apart.

The certificate carries each load's coefficients, bound, achieved value and
slack, as an **optional payload field** — which the frozen schema allows.
`verify` recomputes the achieved value from the primal rather than believing
the declared one, so a certificate that understates what a region used fails.

Senses `<=`, `>=` and `==`; the last is exact preservation. A weight on an
item that is not in the packing, or a load name colliding with a resource, is
refused rather than accepted quietly — the first makes a row silently weaker
than intended and the second makes two prices indistinguishable in the dual.

Taken from a real model whose constraints read `within-A load <= N_A`
alongside a parity condition and a divisibility one.


### `certo parametric`: the finite-to-infinite jump

The thing this project kept saying it could not do, and the sentence that
carries the most unearned weight in mathematical writing: *"and similarly for
larger n"*.

For a linear program whose data are POLYNOMIALS in a parameter, weak duality
is available symbolically: any `y >= 0` with `A(p)ᵀy >= c(p)` gives
`opt(p) <= b(p)·y` for every `p` at once. So the certificate is `y`, the
polynomial data, and per column the residual `A^T y - c` after substituting
`p = p0 + u` — whose coefficients are all non-negative, which is the whole
proof, because `u` and its powers are.

```
$ certo parametric examples/parametric_bound.py
PROVED  [unsat]
  for all p >= 10, the optimum is at most 1/6*p^2 + 1/6*p - 2/3
  and that is every value with p >= 10 -- not a sample of them
```

Not a loose bound either: solving that LP outright gives 53/3, 64/3, 118/3 and
463/3 at p = 10, 11, 15 and 30, and the polynomial gives exactly those. **One
dual, read off one solved instance, gives the exact optimum for every p above
the floor.**

certo does not search for `y`. `opt` on a single instance hands you one and so
would any other solver; what this checks is that it works for the whole
family, and that check is arithmetic. Same split as `farkas`, one level up.

The shift test is **sufficient and not necessary** — `p^2 - 3p + 3` is
positive everywhere and fails it at `p0 = 0`. A failure therefore means "not
established by this route", never "false", and **no certificate is emitted**,
because a route that did not work is not a bound.

Built against a real instance rather than in the abstract. A symmetrised LP
solved exactly for `p = 5..12` with a hand-written rational simplex turned out
to have duals that are piecewise constant with thresholds — one vertex at
p = 6, another across 7..9, a third from 10 — which is exactly the shape this
certifies. Reproducing that slice symbolically and certifying it was how the
command got its interface.


### `certo eliminate`: remove a variable, keep the condition

`ideal` says what follows from a system. This is the other question people ask
while setting one up — *get rid of `t` and tell me what has to be true of `s`*
— and the answer is the **resultant**, a polynomial in the remaining variables
that vanishes exactly when the two share a root in the eliminated one.

```
$ certo eliminate examples/eliminate_parameter.py
SATISFIABLE  [sat]
  eliminated t. A common root exists only where this vanishes: -4*s^3 + 1
```

What travels is not the number but the **Bezout identity** `Res = A*f + B*g`.
Computing a resultant is a determinant over a polynomial ring; checking one is
expanding two products and subtracting. That gap is the whole reason it is a
certificate rather than "the algebra system agreed", and `verify` does the
expansion in exact rationals with no solver.

The determinant is Bareiss — fraction-free, where every division is a
polynomial division whose **remainder is asserted to be zero** rather than
assumed. No rational functions ever appear, so nothing has to be cleared at
the end.

Three things it is careful about:

* A resultant that is a **non-zero constant** refutes a common root outright,
  for any values of anything, over any field. Conclusive, for one determinant.
* `Res = 0` is **necessary** always and **sufficient** only over an
  algebraically closed field with a non-vanishing leading coefficient.
  `verify` repeats that every time, and says so specifically when both leading
  coefficients can vanish — that locus is exactly where sufficiency is lost.
* **Exactly two polynomials.** Iterating pairwise over a larger system
  introduces extraneous factors nothing here could certify away; that is what
  `ideal` is for.

`certo lint` knows the spec: the wrong number of equations, a variable that is
not there, and a degree of zero in the eliminated variable are all caught by
comparing integers, before any determinant is computed.


## [0.5.2] — 2026-09-17

**Schema unchanged: `SCHEMA_VERSION` stays 4.** The two features here add
optional payload fields; nothing moves.

Both remaining P1 items from a user's report, and the thing writing the front
page exposed.

### An unsat core over linear arithmetic no longer needs a solver

A user's objection, quoted exactly: *`unsat_core` certificates depend on
trusting Z3 again; useful, but not solver-free like a rational Farkas
certificate.* Correct, and the machinery was already here.

After a core is found — in `prove`, in `check`, and in
`check --hypotheses-only` — the Farkas search runs on exactly those rows. When
it finds multipliers they travel in the payload as **optional fields**, which
the frozen schema allows, and `solver_free` becomes true: verification expands
`Σ λᵢ · rowᵢ` and reads off the contradiction in `Fraction`, with nothing to
trust.

Floating point in the search does not compromise that. The LP **finds** the
multipliers; `is_contradiction` accepts or rejects them in exact arithmetic,
independently. A bad guess is rejected rather than believed — the same
round-and-verify-exactly discipline as `opt` and `sos`. The core stays in the
payload, because `compose` reads it for the entailment check.

**And the Lean export stops saying `sorry`.** These were reported as two
separate gaps and they have one fix: a core exported with `sorry` precisely
because it says which hypotheses suffice and not why, and with the multipliers
it knows why. A vacuous regime now becomes a compiling Lean proof that it is
empty. CI compiles both paths against Mathlib v4.28.0 on every push.

Outside linear arithmetic nothing changes: no multipliers, `sorry`, and the
file says why.

### Exact LP certification stopped depending on CBC's dual

A user certified 56 LPs exactly and **3 needed the rational primal and dual
injected by hand**, all on symmetric solutions. On a degenerate vertex several
duals are optimal, CBC returns an arbitrary one, and rounding that particular
one need not be dual-feasible at all.

Given an exact primal, complementary slackness determines the dual: `yᵢ = 0`
on every slack row, `Σᵢ Aᵢⱼ yᵢ = cⱼ` for every active `xⱼ`. Solved in
`Fraction` by Gaussian elimination, with no floats anywhere. Where it
underdetermines the dual — more tight rows than active variables, which is
what symmetry produces — the leftover freedom IS the set of optimal duals, and
each choice is offered in turn.

A derived dual is not trusted for being derived: it is a candidate, like a
rounded one, and earns the certificate by passing the identical exact
`check_lp`. Reconstruction still runs first, so every LP that certified before
certifies the same way, with the same denominator and digest.

**One thing the backlog claimed and measurement refuted.** It said the coupled
denominator ladder was a second cause — that a primal wanting thirds and a
dual wanting halves had no rung that worked. `limit_denominator` is monotone
in accuracy, so a rung high enough for the harder of the two is high enough
for both, and pass 1 already climbs to it. Checked on three such pairs before
writing the fix; all were exact at one shared rung. The independent-ladder
pass was dropped rather than shipped, and a test pins the reason so nobody
adds it back.

### A refutation now shows what refuted it

The values were in the certificate and nowhere on screen, so refuting a claim
meant opening a JSON file to find out *what* refuted it. The counterexample is
the answer; the word "REFUTED" is not.

```
$ certo prove examples/refute_density.py
REFUTED  [sat]
  the counterexample:
    dens = 7/8
    kappa = 4
```

`check` and `check --hypotheses-only` do the same — the latter now literally
exhibits the parameter set that inhabits a regime, which is what it was for.

### The README leads with what happens, not with what it is

It opened on "a laboratory for supporting mathematical proofs". True, and it
tells you nothing about what running the thing does, which is what someone
deciding whether to try it needs and what a model being asked to use it needs
more.

It now opens on three real sessions, each runnable from `examples/`, and every
block of output is copied from an actual run. Two were wrong when checked
against one — including a claim that a `branch_bound` certificate verifies
*without* a solver. It does not, and the front page of a project about not
overclaiming is a bad place to overclaim.

Then **Start here**, a router by who the reader is, and **Which command
answers which question** — keyed on the question in the reader's own words
rather than on the command name.

## [0.5.1] — 2026-09-16

**Schema unchanged: `SCHEMA_VERSION` stays 4.** A new flag, a new Lean
exporter, and fixes. Nothing here moves a payload field.


### The last two items of a user report

**`check --hypotheses-only`.** The natural way to ask "are my hypotheses
satisfiable at all?" is `s.claim(z3.BoolVal(False))`, and it is the one
phrasing that cannot answer: `check` decides `hypotheses AND claim`, so a
claim of `False` reports UNSATISFIABLE whatever the hypotheses are. A user
asked exactly that, on a system with models, and was told "no model exists".
They found out only by going to `core`.

The flag asks it head on. Satisfiable returns a **model** — solver-free, the
whole parameter set exhibited rather than argued. Unsatisfiable returns the
**minimal clash** rather than the hypothesis set. And a constant claim is now
named wherever it appears, in `check` and in `lint`, because a flag only helps
someone who already knows it exists.

**`export --lean` for `unsat_core`.** It used to refuse the kind the most-used
command produces. For a core over linear arithmetic it now emits real Lean:
binders, hypotheses, the goal stated positively, and `sorry` — not a tactic
call, because a core says which hypotheses suffice and not why. A vacuous core
becomes `h₁ → … → False`, which is the emptiness of the regime stated in Lean.
Outside linear arithmetic it carries the SMT-LIB2 verbatim and says so.

The sort is read off the formulas rather than assumed: an integer regime
emitted over the reals elaborates fine and says something weaker.

### Fixed

- **`export --lean --check` had never compiled anything.** It passed the file
  path as given while running `lake` with its cwd inside the Lean project, so
  lake looked for `.github/lean/.github/lean/…` and reported "no such file or
  directory" — which surfaced as `compiled: FAILED`. Now absolute.
- **The lean CI job had never once passed**, for a different reason:
  `lean-action` refuses without a `lake-manifest.json` and there is no input
  that generates one. The manifest is now committed, pinning Mathlib and its
  eight transitive dependencies to exact revisions.
- **A confinement test asserted Windows path semantics on every platform.**
  `..\..\secret.json` escapes a directory on Windows and is a legal filename
  on POSIX; the tool was right on both and the test was not.
- **The "no Lean exporter for this kind" message listed a hand-kept set** that
  went stale the moment a new exporter landed. It is generated from the
  registry now.


## [0.5.0] — 2026-09-16

**The certificate schema is unchanged: `SCHEMA_VERSION` stays 4.** Everything
in this release is of the two shapes the freeze permits — an optional field a
reader may ignore, and commands that emit no certificate at all. A certificate
produced by 0.4.0 verifies here, and one produced here verifies there, minus
the optional field it will not know to look at.

### The one that matters: a fractional "integral point" verified as valid

A user reading output rather than code found it. `_verify_lp_dual` checked the
declared integral point for non-negativity, for `Ax <= b`, and for matching
its declared objective — and never that the values were **integers**. On
`max x + y` subject to `x + y <= 3`, a certificate claiming `x = 3/2,
y = 3/2` as the integral point passed all eight checks, because 3/2 is
feasible and does hit the declared value of 3.

`mixed_design` has checked this correctly since it shipped. `lp_dual` did not,
and `lp_dual` is what `opt` produces.

Now checked per **declared kind**, using the `kinds` the payload already
carried: every variable declared integer holds an integer, every binary holds
0 or 1, and a mixed problem's continuous weights stay fractional on purpose.
Both cases are pinned by a test.

No honest certificate is affected — the producer has always rounded, so the
points it wrote were integral. What changes is that the verification no longer
takes that on trust, which is the only thing that makes a certificate worth
anything.

Worth saying how it surfaced: 213 tests did not catch it, because every one of
them fed verification a certificate the producer had built correctly. **The
checker has to stand on its own**, and the only way to find out whether it
does is to hand it something wrong.


### Two commands that make no claim of their own

**`certo lint`** checks a spec before the compute is spent on it. Every other
command answers a question; this one asks whether the question is well posed.

The finding that pays for the whole thing is **contradictory hypotheses, found
first**. `prove` already reports vacuity — after reporting `PROVED`, which is
the moment somebody decides the run went well. Asking beforehand costs one
solver call on a strictly easier problem than the proof, and the clash it
names is minimal, so the next question is already answered.

Three more in the same spirit:

* an **inductive step that starts after the base cases end**. `induct` refuses
  this too, after discharging every base case, which is where the hours go.
  Here it is a comparison of two integers.
* a **predicate returning `bool`**, which means the sweep will be
  `reproducible` and not `certified` — a difference people who wrote the
  predicate themselves have read wrong.
* **`integer=True` makes every variable integer.** A user read it as "there
  are integers in here" and got a design worth nothing, every weight rounded
  to zero.

It counts a domain without building it (`items=lambda: iter(range(10**7))` is
peeked at, never materialised) and reads a graph family's size from a table,
so linting an 11-vertex sweep answers in the time it takes to read the file.
Loading a spec executes it; beyond that, lint calls the predicate at most once
and never runs the solver on the goal.

**`certo status`** reads a directory of certificates and says where the work
stands, in four sections ordered by how much they matter:

* **RESULTS** — the certificates nothing else there builds on. A lemma's
  certificate is not a result; the proof standing on it is.
* **STILL OWED** — every bridge and every unclaimed optimality, including ones
  reached three levels down. Bridges are legitimate and often unavoidable;
  losing count of them is not, and they are easy to lose precisely because
  everything around them verifies.
* **HOLLOW** — valid, and saying less than it looks like: a vacuous proof with
  its clash named, a sweep whose predicate nothing certified, a value reached
  rather than a maximum proved.
* **STALE** — the spec moved under the certificate. Not wrong; it verifies on
  its own. It just no longer describes the file next to it.

Neither emits a certificate, deliberately. They make no claims; they read the
claims other commands made. A report that certified itself would be the one
artefact here that nobody had checked.

### The question a solver cannot ask

A user found four bugs in one step they were doing by hand: take a symbolic
constraint, substitute asymptotic magnitudes (`d ≍ n²`, `C ≍ n`, `|W| ≍ n²`),
and ask whether a term decays in `n`. One of them,

```
5|κ| W C² / (u³ d² p¹⁰)
```

was **Θ(1)**, and it was invisible to Lean *and* to `certo prove`, for the same
reason: **it is not an infeasibility.** It is a feasibility that does not
improve with `n`, so a solver asked "is this satisfiable" says yes forever,
correctly, while the bound it sits in never gets better.

**`certo order`** asks that question. Substitute, collect into powers of the
parameter with exact rational coefficients, read off the leading exponent:
negative decays, positive grows, zero is the case that hurt.

What makes it worth a certificate rather than a calculation is that the
substitution is **written down** instead of done in someone's head, and that
the collection is exact — two terms landing on the same exponent whose
coefficients cancel really do cancel, and with `Fraction` that is decided
rather than estimated. Verification needs neither a solver nor the spec: the
Laurent polynomial travels.

Two limits it states rather than hides: it certifies the **exponent**, never
the constant in front of it (`≍` hides a factor, and `verify` repeats that
every time); and it refuses to divide by a **sum**, whose order depends on
which term dominates.

### Changed

- **Vacuity now names the minimal clash.** It used to say "run `check` on the
  hypotheses alone to find which pair clashes" — but the MUS machinery was
  already there, so it reports the clashing subset directly instead of making
  the user do the work twice. The set travels in the certificate as an
  optional field, which the frozen schema allows.
- **`verify` reads either shape.** `--cert FILE` writes the certificate;
  `--json` writes the RUN, which contains one. Both are right and a reader who
  guesses wrong loses an afternoon, so anything expecting a certificate now
  accepts either. They are told apart by the root key: `kind` versus
  `command`.
- **An INVALID report no longer ends on a line that reads like an
  endorsement.** The trailing detail describes what the certificate *claims*,
  and after a failure that has to be marked as such.
- **Vacuity detection is now a headline in the README**, third section in,
  rather than something to trip over. It is the check a proof assistant cannot
  do for you: `#print axioms` certifies "I did not cheat" and says nothing
  about "this is not hollow".

### Notes

- 285 tests, 32 examples. The example runner now exercises `status` over everything the other examples just produced, which is the only place it can be tried against a directory nobody built to suit it.

## [0.4.0] — 2026-09-16

**The certificate schema is frozen from here.** An existing payload's fields
do not move: no renames, no removals, no changes of meaning. Adding a new
certificate kind stays allowed and always will — that is additive and breaks
nothing — and so does adding an optional field a reader may ignore. Anything
else needs a schema bump and a migration note.

What that buys: a certificate produced for a paper today still verifies
against a later certo, which is the only way "re-verifiable" survives contact
with time. `SCHEMA_VERSION` is 4.

The release also closes the last of P1, which means the two sweep payloads are
finally symmetric — `--by-orbit` for graph sweeps needed three fields in
`sweep` that `domain_sweep` already had, and adding them after the freeze
would have cost a bump for a feature that was already designed.

### The headline: an optimum, proved

`mixed --prove-optimal` proves the MILP optimum by branch and bound, with
**every leaf carrying a certificate** and the tree checked to cover the
integer domain. A leaf closes for one of three reasons, each checkable by
arithmetic:

* its LP bound cannot beat the incumbent — an exact dual;
* it is infeasible — a **Farkas ray**, `y ≥ 0` with `A^T y ≥ 0` and `b·y < 0`,
  which checks in three dot products;
* every variable is fixed, so the residual LP *is* that design's answer.

And then the part that is easy to omit and fatal to: **the tree must cover the
integer domain**, checked node by node rather than assumed. A tree with a
missing child reads exactly like a complete one.

On the research instance this was built against, `ν = 7` went from "a design
that exists" to the proved integral optimum in 73 nodes — 19 closed by bound,
18 by Farkas rays — which pins the integrality gap at exactly `1/2` with both
sides certified.

### Added

- **`certo mixed --prove-optimal`** and the `branch_bound` certificate.
- **`farkas_ray`** — LP infeasibility with a certificate. `opt` used to report
  an infeasible LP and leave nothing behind; now there is a ray, and checking
  it needs no solver and no trust in the one that said "infeasible".
- **`PackingSpec.lists(family)`** — the `(list, pair)` packing, which is the
  shape 51 of 131 scripts in one research corpus share. Three lines instead of
  fifteen, and the constraint that goes missing by hand does not.
- **`opt --gap`** and the `gap` certificate — `μ* − ν` as **one exact
  rational**, with both sides certified and verification checking they are
  about the same packing. Two numbers from two runs are two numbers.
- **`sweep --by-orbit` for graph sweeps.** On a family quotiented by
  isomorphism it infers nothing, because the enumerator already did that — and
  it says so rather than silently doing the same work. It is for a symmetry
  *finer* than isomorphism.
- **`examples/WALKTHROUGH.md`** — one problem from not knowing the answer to
  holding an artefact a referee can check. Every other example shows one
  command; this shows one problem, and it is the only thing that explains what
  the tool is for.

### Changed

- A discrete packing item is bounded above by its tightest resource. With
  capacities of 1 that makes it binary, which it always was — and it is what
  gives branch and bound a finite tree to exhibit.
- `certo mixed` accepts a `PackingSpec` directly.
- `SCHEMA_VERSION` 3 → 4.

### Fixed

- `--by-orbit` that infers nothing is no longer reported as a failed check.
  Every orbit a singleton means the run *was* a full sweep and the invariance
  assumption was never used, which is a different thing from something being
  wrong.


### Added

- **`certo mixed`** — a discrete skeleton found by search, with the continuous
  part certified exactly. From a user's report on a MILP that chooses a
  structure and a compatible fractional packing at the same time, which
  `LPSpec(integer=True)` could not express: that flag makes **every** variable
  integer, a different problem rather than a restriction of this one.

  Variables now carry a kind — `lp.variable("y", kind="binary")` next to
  `lp.variable("q")` — and `mixed` runs the flow the user had been running by
  hand: search with CBC (heuristic, uncertified), freeze the discrete part,
  solve the residual LP with an exact rational dual, and compare against a
  `--target`.

  Three numbers come back and they are deliberately not merged: what the
  design **achieves** (exact, a genuine lower bound, because the construction
  exists), the **conditional** optimum given that skeleton, and the
  **relaxation bound** over all skeletons. That third one is not in the
  obvious design and costs one extra LP — and when the first meets it, global
  MILP optimality is certified for free.

  What is checked: the assignment is integral and in range, the full point
  satisfies every original constraint exactly, and **the residual LP really is
  the original problem with that assignment substituted** — the same gap
  `compose` closes between a lemma and the statement it is used for. CBC's
  answer is a guess until checked: it returns `0.9999997` for a binary as
  often as not, so the rounding is verified in exact arithmetic and a design
  that does not survive is refused rather than reported.

  What is not claimed, and says so: that the skeleton is the best one.

- `LPSpec.variable(kind=...)`, `spec.discrete`, `spec.continuous`,
  `spec.frozen(assignment)` and `spec.relaxed()`.

- **The three MILP levels, named.** A second round of the same user's feedback
  asked for exactly this taxonomy, in these words: `feasible` (a mixed point
  satisfies everything), `conditional_optimum` (and the residual LP is optimal
  given that skeleton), `global_optimum` (and it meets the relaxation bound).
  The information was already there; naming it is what a reader needs, and
  "declare exactly what was proved" is the whole discipline.
- **`mixed --freeze`** — take the discrete assignment from **your** solver
  rather than CBC. A real MILP may be solved by HiGHS, Gurobi, something
  bespoke or a person, and requiring certo's own solver to reproduce it would
  put certo's limits in front of a construction that already exists. The
  frozen assignment is rounded and checked exactly like any other, so where it
  came from changes nothing about what is certified — but the certificate
  records that certo never saw the search, and `verify` says so.
- **`opt --target`** — certify `objective >= T` rather than only reporting the
  optimum. For an existence proof the question is usually whether a bound is
  reached. Falling short is a warning on a valid certificate, not invalidity.
- **`PackingSpec(integer={"K3"})`** — integrality per item kind, so structural
  items can be whole while the rest stays fractional.
- Certificates record **each variable's kind** by name, so a reader of the
  certificate alone can tell a design from a relaxation.

### Fixed

- **`ideal` and `farkas` rejected `S**4`.** With a REAL base, z3 coerces the
  exponent to a rational literal, so `is_int_value` said no and an ordinary
  quartic was refused as a "non-constant exponent". The exponent's sort was
  never the question — whether it is a literal natural number is. Reported by
  a user who worked around it as `S*S*S*S`.
- **`opt` rounded every variable on a mixed problem**, turning fractional
  weights of 1/6 into zero and reporting a "design" worth nothing. On a mixed
  problem it now certifies the relaxation bound and points at `mixed`, which
  is where the achievable value comes from.
- **`opt` treated "has a discrete part" as "is entirely integer".** The
  relaxation was built from the spec's kinds, so for a mixed problem it
  rebuilt the integer problem and the dual meant nothing. A relaxation is
  continuous by definition and is now built that way.
- **`opt` on an ILP reported the relaxation as the objective.** `meta["objective"]`
  carried the LP relaxation's value, so an integer optimum of 7 came back as
  `15/2`. The detail text was half-honest about it; every programmatic reader —
  `--json`, the CLI display, the MCP response — was not. Found by rebuilding a
  real research instance as a `PackingSpec`.

  The fix goes further than the original intent: an ILP now certifies **both
  sides**. CBC's integer answer is rounded and **checked exactly** against the
  constraints, giving a feasible integral point as the achievable value, while
  the exact dual bounds the optimum. When they coincide the integer optimum is
  certified exactly; when they do not, the gap is reported rather than hidden,
  and `verify` warns that the number is a bound.

### Added

- **CI.** Tests on Linux and Windows across Python 3.11 and 3.12; every
  example run and its certificate verified; and the Lean exports compiled
  against Mathlib. Everything had only ever run on one Windows machine, and
  the three most useful bugs of the previous round were all specific to it.
- `tests/run_examples.py` — runs each example as the README shows it and
  verifies what comes out, including the two certificates `compose_proof.py`
  needs as input. An example listed nowhere is reported rather than silently
  skipped.

### Decided

- **PyPI:** not yet; revisit at a stable version.
- **Certificate schema:** frozen from 0.4, once that version closes.
- **Lean:** deeper Lean export is not the focus. certo establishes the
  mathematics; generating and compiling Lean is another tool's job.
- **`cadical`/`kissat`:** closed rather than blocked — no administrator rights
  on the target machine, and the built-in CDCL is the answer.

## [0.3.0] — 2026-09-16

The release where certo stopped being Z3 with a nicer interface.

Three engines that are not a solver, each answering a question an SMT solver
either grinds on or cannot phrase, and each producing a certificate that is
checked by arithmetic alone.

### `ideal` — polynomial systems, decided

Gröbner cofactors: `1 = Σ hᵢgᵢ` refutes a polynomial system outright,
`f = Σ hᵢgᵢ` certifies that `f` follows from it. Finding them is a Gröbner
basis computation with the transformation tracked through Buchberger; checking
them is expanding a product and comparing coefficients in exact rationals —
no solver, no algebra system. A library that says "yes, it's in the ideal"
leaves you with its word; this leaves you with the polynomials.

Two things worth knowing. **It decides**: membership is decidable, so a
negative answer is `REFUTED`, not `unknown_solver` — rare in this tool. And
**the field is ℂ**: `1 ∈ I` refutes over the complex numbers and hence over
everything smaller, while a proper ideal implies nothing about a real
solution. `verify` says so every time.

### `sos` — a numeric search, an exact certificate

This project's own notes argued twice that sums of squares were not worth
having, because an SDP is solved in floating point and an inexact certificate
is not citable. The objection was aimed at the wrong half: it would rule out
`opt` too, and `opt` answers it. Solve numerically, reconstruct rationals,
re-verify exactly.

`p = zᵀGz` is a linear condition on `G`; a numeric `G` is found by alternating
projections onto that affine subspace and the PSD cone (no SDP solver needed,
which matters, because there is not one here), then rounded, **projected back
onto the subspace exactly in `Fraction`**, and decomposed by an exact LDLᵀ.
Every pivot non-negative means the decomposition *is* the sum of squares. The
floats were the search and never reach the certificate.

Incomplete on purpose: from degree 4 in 3 variables there are non-negative
polynomials that are not sums of squares, so nothing found is
`unknown_solver`, never "it goes negative". Motzkin's polynomial is in the
tests for exactly that reason.

### `number` — primality you can cite

`n.is_prime()` is true, fast and uncitable. A Pratt certificate is the same
fact with the evidence: a witness generating `(ℤ/n)*`, plus a certificate for
each prime factor of `n−1`, recursively down to 2. Checking the tree is a
handful of `pow(a, e, n)` calls — 53 of them for 2³¹−1.

Three details that separate a certificate from a test: the factor list of
`n−1` must be complete (missing one would let a composite through, so that is
checked before the witness is looked at); Carmichael numbers like 561 pass the
Fermat condition and are caught by the order condition; and the witness is
found by trying small bases in order rather than randomly, so the same `n`
gives the same certificate and the same digest on every machine.

### Added

- **`certo induct`** — finite base cases plus an inductive step, with the join
  checked: the base cases are exactly `k0..base_upto` with no gap, and the
  step starts no later than the base ends. A base covering 3..8 with a step
  valid only from k ≥ 10 proves nothing about 9 and reads identically in
  prose. Z3 has no induction schema: the principle is applied by the tool, the
  certificate's structure is the application, and `verify` says so every time.
- **Native combinatorial types** (`SetFamily`) — hypergraphs, block designs,
  codes and mask systems are one shape. The type supplies `key()`,
  `canonical()` and `reductions()`, so a `DomainSpec` over one can leave
  `key`, `canonicalize` and `reduce` all at `"auto"`. The canonical form is
  exact under relabelling the ground set, and **raises** above a cap rather
  than falling back to a cheaper invariant that could merge two orbits.
- `SweepSpec(canonicalize=...)` — symmetries on graph sweeps, for a symmetry
  finer than isomorphism.
- `canonicalize="auto"` asks the item for its own canonical form, so any class
  with a `canonical()` method joins.

- **`sweep --by-orbit`** — evaluate one item per orbit instead of every item.
  Sound only if the predicate is invariant under the declared symmetry, which
  nothing can prove: the assumption is named in the certificate and
  **spot-checked** against real non-representatives, and a predicate that is
  not invariant stops the run naming the item and its representative.
  Inferred verdicts are marked in lower case in the verdict vector, and
  replay reproduces the inference rather than re-evaluating.
- **`sweep --witnesses`** — the structural story in one artefact: N labelled
  counterexamples → K orbits → a minimal witness for each. Verification
  checks the witnesses minimise the sweep's own representatives, which a
  directory of separate certificates cannot say.
- **Deep Lean export.** `certo export --lean` now reads the certificate's
  kind: a Farkas certificate becomes a runnable `linarith` example with the
  hypothesis list already narrowed and the `sq_nonneg` hints it actually
  used; a `compose` proof becomes a skeleton with `sorry` on exactly the
  bridges and nowhere else; a sweep becomes a `List` Lean can `decide` over,
  with completeness stated as the enumerator's claim rather than smuggled in.
  Plus `--manifest` (hashes tying the file to the run) and `--check`, which
  runs the toolchain and says so when there is not one.

### Fixed

- `subprocess` output was decoded with the Windows default codepage, so any
  Lean or tool output containing UTF-8 crashed the run.

### Notes

- 210 tests.
- New certificate kinds: `ideal`, `sos`, `number`, `induction`,
  `orbit_witnesses`. All five verify without a solver except `induction`.
- The three Lean exporters were checked by compiling them against Mathlib
  v4.28.0. `nlinarith` alone could not close the nonlinear example — the
  `sq_nonneg` hint from the certificate is what makes it compile, which is
  the clearest demonstration of what the certificate is worth.

## [0.2.0] — 2026-09-16

The release where a passing sweep stopped looking stronger than it was.

Almost everything here comes from one external user's report after using
`certo` on a real problem. It found a false lemma for them on first use, and
then it found something in `certo` worth more than the feature list: a result
that read as a certification and was not one.

### Never let a passing sweep look certified

A sweep over 11,480 elements that ended PASS printed `FINITE CASE VERIFIED`
and verified with no warning, while its certificate established **nothing** about
the boolean predicate. The refuted case did warn; the passing case did not —
and that is where it does most damage, because there is no counterexample to
go and look at. The counter meant to cover this, `predicate_uncertified`,
counted *stored counterexamples*, so it read `0` on every passing sweep.

A sweep now reports which of three levels it reached:

| Level | What holds |
|---|---|
| `certified` | every evaluation carries its own certificate |
| `reproducible` | a verdict vector is stored; re-running the predicate gives the same answers, which is **not** the same as establishing them |
| `recorded` | only the domain and its hash |

The banner, the counters and the warnings all say it, on PASS and REFUTED
alike. The level is **recomputed at verification time** rather than stored,
because `reproducible` depends on the spec still being there and a stored
label would quietly become a lie.

The two caveats are now separate, because they are different claims: *not the
theorem* is about generality, *not certified* is about trust.

### Replay verification

The certificate carries one character per evaluation plus a digest. `verify`
re-runs the predicate and compares, naming the first item that disagrees:

```
[XX] re-running the predicate gives the same verdicts
     (item a=1,b=1 (index 0) now answers differently)
```

This is the only check that catches a predicate edited under a stable name:
the domain hash cannot — the domain did not move — and there are no per-item
certificates to fall back on. Verification now costs a full re-run, which is
the honest price of the claim, and the header says **"by re-running the spec"**
rather than "without a solver", since replaying runs the spec's own Python.

### Symmetries

`DomainSpec(canonicalize=...)` declares when two items are the same object
relabelled. A refuted sweep then reports labelled count, orbit count and a
representative per orbit — of the **counterexamples**, which is the question:

```
REFUTED: 10 counterexamples out of 64 examined -- 10 labelled, 3 up to symmetry
  (1,2,3)   x6      (1,1,4)   x3      (2,2,2)   x1
```

That two items sharing a canonical form really are in one orbit is the spec's
claim. What `verify` checks is that the decomposition adds up: each
counterexample in exactly one orbit, no shared representatives, sizes
consistent.

### Added

- **`certo compose`** — assemble lemmas and their certificates into one proof,
  checking the **link**: what a lemma's certificate actually closes must
  entail the statement used downstream. If it does not, nothing is emitted.
  Lemmas supplied as a stored certificate are **bridges** — verified on their
  own, declared in prose, and reported by name on every verification.
- **`certo bounds`** — rigorous numerics via Arb (`python-flint`) or
  `mpmath.iv`. Enclosures come out as exact rationals, so the claim half of
  verification is fraction arithmetic. Precision is the work budget and runs
  out as `resource_exhausted`, never as a refutation. Python floats are
  refused: `0.1` is not one tenth.
- **`certo farkas`** — the `linarith` equivalent, with the certificate
  attached: non-negative rational multipliers that close the system, verified
  by adding fractions. `--nonlinear` is `nlinarith`. Emits the Lean tactic
  line with the hypothesis list already narrowed.
- **`certo doctor`** — what this install can and cannot do, each gap with
  **what happens without it**. `--register-mcp` merges into `.mcp.json`
  instead of replacing it, refuses invalid JSON, and checks the server
  actually starts.
- **Vacuity detection** in `prove`, `core`, `farkas` and `compose`. The
  verdict stays PROVED — it really is a proof — but it is said, and the flag
  travels in the certificate so `verify` repeats it months later.
- **Standard reducers** for `shrink`: `reduce="auto" | sets | sequences |
  decrement | graphs | masks`. `auto` refuses on a type it does not recognise
  rather than inventing a reduction.
- `BACKLOG.md`, one place for what is planned, blocked and refused.

### Fixed

- **`load_spec` read stale `__pycache__` bytecode** for a spec edited within
  the same second to the same byte length, so a replay could silently compare
  against the old code. It now compiles the bytes it hashed — which is also
  the right guarantee for a tool whose certificates carry a spec hash.
- **A spec could not import a file next to it.** `load_spec` now puts the
  spec's directory on `sys.path`, the way Python does for a script.
- **The MCP `verify` tool dropped `warnings` entirely** — the bridge, vacuity
  and predicate-level warnings never reached the model. An `ok: true` with
  those removed is the overclaim the tool exists to prevent.
- **Certificates produced over MCP carried no provenance**, so they could not
  be replayed or located by `ledger verify`.
- Verifying a `shrink` certificate with no recorded spec path died with
  `permission denied: '.'` — `Path("")` is the current directory.
- The whole `DSL_GUIDE` and the `synth` tool description were still in
  Spanish, though English is the default and the source of truth.

### Changed

- **Certificate payload:** the item id field is `id`, not `g6`. A `DomainSpec`
  used to label triples of sets "graph6". Readers still accept `g6`, so
  certificates issued by 0.1.0 still verify.
- `sweep` and `domain_sweep` payloads gain `evaluations`, `certified`,
  `outcomes`, `outcomes_sha256`, and (with a symmetry) `orbits` and
  `labelled`.
- `VerifyReport` gains `method`, because "not solver-free" and "a solver was
  used" are different statements.
- The redundant `verify.sweep.missing` warning is gone: the level warning that
  replaced it says strictly more, and two messages about one gap make readers
  skim both.

### Notes

- 149 tests, no test framework required.
- New optional extra: `pip install 'certo[numerics]'` for `bounds`.
- The default branch is now `main`.

## [0.1.0] — 2026-09-15

First public release. Twelve commands over CLI and MCP, every result carrying
a certificate that verifies without trusting the solver that produced it.
Engines: Z3, exact-rational LP over CBC, a self-contained CDCL with a
DRUP/DRAT checker, graph enumeration via nauty or a built-in engine, and
CEGIS. English by default with Spanish as an overlay.
