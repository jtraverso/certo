# certo — backlog

One file, so nothing is tracked in three places. Priorities are **P0** (blocks
a release), **P1** (the next thing worth doing), **P2** (real value, more
work), **P3** (worth keeping, nobody is waiting), **Blocked**, **Won't do**.

Items marked *(user feedback)* come from an external user's report after real
use; those carry more weight than anything on this list that was invented in
the abstract.

Last updated: 2026-09-18, at 0.9.0. Both P1 items and the first P2 item landed; what remains at P2 is the toric work, still specified from a report rather than measured against an instance. See "What changed the ranking".

---


## What is open, in one screen

**Effort** is calibrated against work that actually landed here, not against a
feeling. **Confidence** is the part worth reading twice: an estimate made from
a specification rather than from an instance somebody measured has been wrong
every time this project checked one -- coset pruning, the canonical form, and
the shape of the corpus LPs all changed the moment they were measured.
**Radius** is what else moves if this lands.

| | Item | Effort | Confidence | Radius | Unblocks |
|---|---|---|---|---|---|
| **P2** | Affine semigroups and local toric charts | **L**, or **S-M** taken as input | **low** | none | the toric route's highest-return item |
| **P2** | Chow ring and toric intersection | **L** | **low** | none | — |
| **P2** | A canonical form that scales, on its own | **L** | med | **high** | nothing that is currently blocked |

Released in 0.8.0, and struck from the table above: **certified symmetry
reduction** (`certo reduce`), **does this hypothesis earn its place**
(`certo audit`), and **exact integer linear algebra** (`certo matrix`). The
estimates held -- M, S and M -- and each of the three found a defect
underneath, which is now the expected rate rather than a surprise. See
*What landed in 0.8* below.

### The scale, with its anchors

| | Means | What landed at this size |
|---|---|---|
| **XS** | one sitting, reusing machinery that exists | `ratio` (reused the shift test), `omega` export, hollow marking |
| **S** | one focused pass: module, engine, CLI, MCP, example, tests | `peak`, `exists`, `moment`, `entry`, the Tseitin bridge, typed transport |
| **M** | a pass plus a design decision, and usually a bug found underneath | `family` (a new verification model), `parametric` regions (found a simplex bug), the correspondence parser |
| **L** | several passes, or an algorithm that is a project of its own | the branch-and-bound retie (found a soundness hole); everything toric |
| **XL** | not attempted here | — |

### Two things the table is saying quietly

**The cheapest P2 unblocks the two expensive ones.** Exact integer linear
algebra is the only mathematical item two different routes both asked for, it
has no radius, and Bareiss fraction-free elimination already exists in
`resultants.py` -- so determinant and rank fall out, and Hermite and Smith are
classical and testable against brute force. Doing it first makes the two below
it cheaper and better specified.

**The toric items can be made much smaller, by the rule this project already
follows.** A Hilbert basis is genuinely hard to COMPUTE -- Normaliz exists for
a reason -- and much easier to CHECK: that each generator lies in the cone,
that none is a sum of others, and that together they generate. Taken as INPUT
and verified, the same way `parametric` takes a dual and `labelling` takes a
permutation, that item drops from L to S-M and stops being a research project.
Computing it is somebody else's job and always was.

That is also why their confidence is low as written: they are specified from a
report rather than measured against an instance, and every estimate this
project made that way changed on contact.

---

## What landed in 0.9

### `reduce --parametric` — the symbolic quotient *(was P1, user feedback)*

Estimated **M / med-high / low radius**, and it landed at that size. The
estimate held for the reason the backlog said it would: both halves existed.

**The risk resolved in the easy direction.** The open question was whether the
orbit COUNT varies with the parameter, which would have needed either a stated
range or a refusal. Measured against three write-ups: it does not — 2, 3 and 4
orbits, fixed. What varies is the ROW SET, because a triangle type that does
not exist contributes no constraint. So the feature is built around row
existence conditions, and the regimes those conditions cut parameter space into
are derived rather than declared.

**One thing measuring did change.** An orbit is present exactly where its
multiplicity is positive, not wherever it is declared: the split family has two
edge orbits for `q >= 1` and one for `q = 0`. Declaring "two orbits" and
meaning it everywhere is how a degenerate case gets a constraint it has no
right to.

Five ways of mis-stating a family are refuted on the window, the tightest being
a single condition dropped: `3x >= 1` carried into `p = 2` fails at 7 of 35
points. The Lean export splits the same way the certificate does — the
multiplicity identity as a theorem `ring` closes, the window as examples
`norm_num` closes, and one `sorry` on the step from the window to the region.

---

## What landed in 0.8

### Domain obligations in `audit` *(defect reported against 0.8)*

Reported by a user within a day of 0.8. Division is total in SMT, so dropping
a hypothesis that guards a denominator produced an instant counterexample at
`d = 0` and the hypothesis read `needed` for a reason about the solver rather
than the theorem. Worse than reported: the witnesses also carried Z3's
internal `div0`/`mod0`, which nothing could re-apply, so on any spec
containing a division `audit` emitted a certificate that did **not verify at
all**.

Divisors are now collected up front, every search is guarded by them, and a
fourth verdict `domain` names the obligation a hypothesis was carrying. The
distinction between `domain` and `redundant` is asked, not read off the shape
of the formula.

### `certo reduce` — certified symmetry reduction *(was P1 #1)*

"Averaging over the automorphism group, an optimal solution may be assumed
constant on each orbit" was a bridge under five shipped examples. Its three
hypotheses are finite checks given a generating set, and now they are checked:
the action permutes the variables, the constraint set is invariant, the
objective is invariant. A generator that fails one is refused BY NAME, because
a wrong group does not give a weaker reduction, it gives a wrong one. The
quotient is rebuilt during verification rather than believed.

K7 triangle cover under S7: 35 variables to 1 orbit, 21 rows to 1, optimum 7
both ways. `examples/symmetry_reduction.py`.

### `certo audit` — does this hypothesis earn its place *(was P1 #2)*

Drop each hypothesis in turn and hunt a counterexample to what remains. One
satisfiability query per hypothesis, three verdicts, and `unknown` is never
folded into the other two. Every `needed` carries the assignment that breaks
it, so re-checking is evaluation rather than search.

On `examples/amgm.py` it found a hypothesis nobody suspected doing no work.
It does NOT claim minimality -- hypotheses are dropped one at a time, and a
pair can be jointly redundant with neither redundant alone -- and `verify`
says so every time, because claiming it would be the overstatement this
command exists to catch.

### `certo matrix` — exact integer linear algebra *(was P2 #1)*

rank, determinant, Hermite and Smith over Z, with the unimodular transforms
carried alongside their INVERSES, so checking is integer multiplication and
not a second elimination. `rows`/`cols` select a submatrix, which is how a
minor is asked for. The sign of the determinant is settled by one determinant
modulo an odd prime -- exact, because `U . U_inv = I` had already narrowed it
to two candidates.

This was the cheapest P2 and it unblocks the two below: the semigroup and
Chow-ring items are built on exactly this arithmetic.

---

## P2 — the substrate two routes share

### 1. Affine semigroups and local toric charts

Saturation, normality, Hilbert bases, the interior of a cone, the Gorenstein
criterion; unimodular cones of height one, SNC divisors, multiplicity and
discrepancy. The second user's highest-return item, and finite exact integer
work throughout. The arithmetic it needs landed with `certo matrix`.

**Effort L as written, S-M taken as input** -- and the second is the version
this project should build. A Hilbert basis is genuinely hard to COMPUTE;
Normaliz exists for a reason. It is much easier to CHECK: each generator lies
in the cone, none is a sum of the others, and together they generate. Take it
as INPUT and verify it, the way `parametric` takes a dual and `labelling`
takes a permutation, and this stops being a research project.

Saturation, normality and the Gorenstein criterion are the same shape: hard to
decide from nothing, cheap to check given the witness a dedicated tool already
produces.

CONFIDENCE IS LOW either way, and that is the part to weigh. This is specified
from a report rather than measured against an instance, and every estimate
made that way in this project changed on contact -- coset pruning looked like
the answer to the canonical form until the number was computed, and the corpus
LPs turned out to be the opposite shape to the one the command was built for.
Before building, get one real cone out of the route that wants it and measure
what actually blocks.


### 2. Chow ring and toric intersection

From rays, cones and linear relations: the presentation, Stanley-Reisner
relations, monomial reduction, intersection numbers, Chern classes. Needs the item
above; the integer arithmetic under both landed with `certo matrix`.

### 3. A canonical form that scales, on its own

Unchanged and unasked-for by anyone. The measurement that blocks it stands: a
1-factorisation of K6 has 15 points and one refinement class, `15!` is
1,307,674,368,000, `|Aut|` is 120, so quotienting by the whole group leaves
10,897,286,400 cosets. `labelling=` removed the pressure by taking the
labelling as input.

---

## P3 — later, or waiting on the above

| | What | Effort | Why it is down here |
|---|---|---|---|
| | Structured ring isomorphisms | **L** | Explicit maps, identity compositions, compatibility with localisation, grading and group actions. Wants the typed transport (landed) to be extended past `compose` first -- without it there is no notion of "the same object" to certify. |
| | Finite group actions | **M** | Invariants, stabilisers, fixed loci, quotient rings. Finite and exact, and downstream of the semigroup work. |
| | Finite homological algebra | **L** | Free complexes, exactness, resolutions, Ext, Tor, dimensions. Mechanical and large; nobody is blocked on it today. |
| | Jacobian criterion certificates | **S-M** | Smoothness, local dimension, singular locus, transversality via exact Jacobian ideals. `ideal` is the machinery; this is the interface. |
| | Batyrev engine, canonical form transport | **XL** | Both are geometric theorem application, which by the stated boundary is Lean's job. certo's part is the finite premises those theorems consume. |
| | Small geometric counterexample generation | **S** | The second user's request, and a special case of P1 #2 applied to fans, cones and semigroups. Follows it. |
| | CLI / metadata version sync, `export --check` progress | **XS** | Papercuts from the first user. Small, real, and worth doing in the same pass as P0. |
| | Flag algebras | **L** | Still wants 2-3 real instances to be designed around a problem. |
| | Lean statements for the sweep kinds | **L** | Graphs and set families are not mechanical. Deliberately parked. |
| | `certo qe`, Gomory-Chvatal cuts | **M** each | Distinctive, nobody waiting. |

---

## The boundary, stated

**certo is not a second Lean**, and should not try to become one. Its part is
to find and certify finite, explicit, checkable data; Lean's part is to verify
that data, apply the structural theorem, and carry the geometry. A user on the
toric route put it as a pipeline and it is the clearest statement of the
division this project has:

    certo finds and certifies the data
      -> Lean verifies the certificate
      -> Lean applies the geometric theorem
      -> Lean identifies the model

Everything in P2 is chosen to feed that first arrow. Nothing in it is an
attempt at the last three.

---

## What changed the ranking, again

Reordered 2026-09-17, after reports from two users on two different routes and
one measurement of my own. They agree in a way none of them could see alone.

**A Lean export that compiles, has no `sorry`, and says nothing.** A user
exporting an `unsat_core` over a theory certo cannot render in Mathlib got

    theorem from_core : True := by trivial

with the real statement carried verbatim in a comment above it. The comment is
honest. The artefact is not: it passes a build, it passes a `sorry` audit, it
passes `#print axioms`. The user declined to put it in their formal chain,
which was right, and which means the safeguard that worked was a person
reading carefully -- exactly the safeguard this project exists to replace.

certo already has the word for this. `status` reports HOLLOW for a vacuous
proof. Not applying it to certo's own output is the same inconsistency as a
certificate its own verifier rejects, and it is now P0.

**"The biggest risk is not in the calculations."** A second user, on a toric
geometry route, named it directly: the danger is silently moving from a
computational object to the paper's object. They asked for a TYPED TRANSPORT
GRAPH -- every certificate declares which object it speaks about (cone,
monoid, ring, spectrum, model) and every step between levels carries an
explicit map.

**And it is already load-bearing here.** Five examples written this week start
from a symmetrised program -- "averaging over the automorphism group, an
optimal cover may be assumed constant on each edge orbit" -- and certo
certifies everything downstream of that sentence and nothing about it. The
averaging argument has three hypotheses, all of them finite checks given
generators: the action permutes the variables, the constraint set is
invariant, the objective is invariant.

Three observations, one item. The calculations were never the weak part.

**What both users want that is the same substrate.** One asked for exact
determinants, rank, minors, Smith and Hermite normal forms, polytopes and
fans. The other asked for affine semigroups, toric charts and a Chow ring.
The second is built on the first. That makes exact integer linear algebra the
highest-value MATHEMATICAL item, because it is the only one two routes share.

**And the boundary, which one of them stated better than this file did:**
certo should not become a second Lean. It produces finite, explicit,
verifiable certificates; Lean proves the structural theorems and does the
geometric transport. That is now the stated policy rather than an implication.

---

## Done

| | What landed | Notes |
|---|---|---|
| ✅ | `certo compose` | Lemmas + their certificates into one proof, with the **link** between each lemma and what its certificate closes checked. Bridges are declared and reported every verification. |
| ✅ | `certo bounds` | Rigorous enclosures via Arb / `mpmath.iv`; exact-rational intervals; precision as the work budget; Python floats refused. |
| ✅ | Vacuity detection | `prove`, `core`, `farkas`, `compose`. The verdict stays PROVED; the flag travels in the certificate so `verify` repeats it later. |
| ✅ | **Sweep levels: certified / reproducible / recorded** *(user feedback P0)* | Banner, counters and warnings say what a sweep established about its **predicate**, on PASS and REFUTED alike. |
| ✅ | **Verdict vector + replay verification** *(user feedback P0)* | One code per evaluation plus a digest; `verify` re-runs the predicate and names the first item that disagrees. |
| ✅ | **Honest counters** *(user feedback P0)* | `predicate_uncertified` used to read 0 on every passing sweep however many evaluations went unchecked. |
| ✅ | **Symmetries for `DomainSpec`** *(user feedback P1)* | `canonicalize=` reports labelled count, orbit count and a representative per orbit — for the **counterexamples**, which is the question. `verify` checks the decomposition adds up. |
| ✅ | **Standard reducers** *(user feedback P1)* | `reduce="auto" / "sets" / "sequences" / "decrement" / "graphs" / "masks"`. `auto` refuses on a type it does not know rather than inventing a reduction. |
| ✅ | **`certo doctor`** *(user feedback P1)* | Capabilities present and missing, each with **what happens without it**, plus `--register-mcp` (merges, never replaces) and a real start check. |
| ✅ | **`g6` → `id` in the payload** *(user feedback P1)* | A `DomainSpec` used to label triples of sets "graph6". Readers still accept `g6`, so earlier certificates verify. |
| ✅ | `load_spec` runs the bytes it hashed | Was reading stale `__pycache__` bytecode for a spec edited within the same second to the same length — which would have silently defeated replay verification. |
| ✅ | A spec can import a sibling file *(user feedback)* | `load_spec` puts the spec's directory on `sys.path`, the way Python does for a script. |
| ✅ | MCP `verify` returns its warnings | It was dropping them entirely — and the warnings are the whole honesty layer. |
| ✅ | MCP stamps provenance | Certificates produced over MCP carried no spec path, so they could not be replayed or found by `ledger verify`. |
| ✅ | `Path("")` is `.` | `shrink_graph` and `shrink_domain` verification died with a permission error instead of saying the certificate recorded no spec path. |
| ✅ | **Native combinatorial types** *(user feedback P2)* | `SetFamily` — hypergraphs, designs, codes, mask systems. Supplies `key()`, `canonical()` and `reductions()` itself, so a `DomainSpec` over one leaves all three at `"auto"`. The canonical form is exact and **raises** rather than falling back to an invariant that could merge two orbits. |
| ✅ | **`certo induct`** *(P2)* | Base cases + step, with the join checked: no gap in `k0..base_upto`, and the step starting no later than the base ends. Z3 has no induction schema; the principle is applied here and said so on every verification. |
| ✅ | **Symmetries on graph sweeps** *(P2)* | `SweepSpec(canonicalize=...)`, for a symmetry finer than isomorphism. `"auto"` asks the item for its own canonical form. |
| ✅ | **`sweep --by-orbit`** *(P1)* | Evaluate one item per orbit. Sound only under an invariance nothing can prove, so it is named in the certificate AND spot-checked against real non-representatives; a predicate that is not invariant stops the run by name. |
| ✅ | **`sweep --witnesses`** *(user feedback P1)* | The structural story end to end: N labelled → K orbits → a minimal witness per orbit, in one certificate that verifies they came from the same run. |
| ✅ | **`certo ideal`** *(0.3.0)* | Gröbner cofactors: `1 = Σ hᵢgᵢ` refutes a polynomial system, `f = Σ hᵢgᵢ` certifies what follows. Buchberger with the transformation tracked, so the cofactors are in the user's own generators. Decides, so a negative answer is conclusive. |
| ✅ | **`certo sos`** *(0.3.0)* | Sums of squares: numeric search by alternating projections, exact rounding, exact LDLᵀ. Retracts this project's own earlier argument that SDP-based certificates could not be citable — the answer was `opt`'s all along. |
| ✅ | **`certo order`** *(user feedback)* | The exponent of a parameter once magnitudes are substituted. Asks what `prove` cannot: a Θ(1) term is not infeasible, so a solver says "satisfiable" forever while the bound never improves. Found four bugs in a user's session before it existed. |
| ✅ | **Branch and bound with certified leaves** *(0.4, P1)* | `mixed --prove-optimal`. Every leaf closed by an exact dual, a Farkas ray, or a fully-fixed residual LP; the tree checked to COVER the integer domain. Turned `ν = 7` from a design into the proved optimum on the research instance, in 73 nodes. |
| ✅ | **`farkas_ray`: LP infeasibility with a certificate** *(0.4)* | `y >= 0`, `A^T y >= 0`, `b.y < 0`. Three dot products, no solver. |
| ✅ | **`PackingSpec.lists` and `opt --gap`** *(0.4, P1)* | The shape 51 of 131 corpus scripts share, in three lines; and `mu* - nu` as one exact rational with both sides certified and checked to be the same packing. |
| ✅ | **`--by-orbit` for graph sweeps** *(0.4, P1)* | Both sweep payloads are now symmetric, which is what made it urgent before the freeze. |
| ✅ | **`examples/WALKTHROUGH.md`** *(0.4)* | One problem, end to end. |
| ✅ | **MILP levels named, `--freeze`, `opt --target`, per-kind packing integrality** *(user feedback, 2nd round)* | The taxonomy the user asked for — feasible / conditional_optimum / global_optimum — plus taking the skeleton from their own solver, certifying a target rather than an optimum, and whole-or-fractional per item kind. |
| ✅ | **`S**4` was refused as a non-constant exponent** *(user feedback)* | With a REAL base z3 makes the exponent a rational literal; `is_int_value` said no. The sort was never the question. |
| ✅ | **`certo mixed`** *(user feedback)* | Per-variable kinds, and the search-then-certify flow a user was running by hand. Certifies the construction, the exact residual dual, and the link between them; states plainly that it does not claim MILP optimality. Throws in the relaxation bound, which certifies global optimality for free when the two meet. |
| ✅ | **`certo number`** *(0.3.0)* | Pratt primality trees and factorisations. Checked by modular exponentiation alone. |
| ✅ | **A refutation showed the verdict and hid the counterexample** | The values were in the certificate and nowhere on screen, so refuting a claim meant opening a JSON file to find out WHAT refuted it — and the counterexample is the answer, not the "no". `prove`, `check` and `check --hypotheses-only` now print it. |
| ✅ | **`certo repro`** *(P1)* | Spec, certificates, versions, hashes and ledger in one directory a referee checks with nothing but certo. Nothing invalid goes in, and nothing untied goes in quietly — a bundle that silently shipped a different spec would be the worst failure available. Measured on a real directory: 132 certificates, 5 refused with reasons, 6 named as untied, and the bundle re-verified end to end. |
| ✅ | **Adversarial verification tests** *(P1)* | Every kind, every payload field mutated, and a mutation that flips no check is the finding. Three real holes: a Pratt tree never tied to the number it claimed (2³¹−1 relabelled as 2³¹ verified), an `lp_dual` accepting a primal one entry short because `zip` truncates in silence, and an `unsat_core` with multipliers never reading its own `core_smt2`. Exclusions are named with reasons, in two categories — descriptive, and weakening, since a smaller true claim is not a forgery. |
| ✅ | **`verify --spec` and `certo --version`** *(user feedback P1)* | Refuse unless the file is the one the certificate was made from, by hash; and print version, commit and the newest schema this build writes. |
| ✅ | **`cover --optimize` and `CoverSpec.to_lp`** *(user feedback P1)* | Three numbers with their statuses attached: your cover as a certified upper bound, the relaxation as an exact rational lower bound, and the integer optimum when branch and bound finishes. `candidates` required and refused rather than guessed, because minimal-relative-to-what is a modelling fact. Built for a misreading: a valid cover reported as an optimal one. |
| ✅ | **An exact rational simplex** | Surfaced by the above. Deriving a degenerate dual by choosing which tight rows carry weight is C(49,7) on a realistic exact cover, about 10^8 — right for a handful of tight rows and hopeless past it. Past that the dual is solved outright, two-phase, Bland's rule, no floats. The motivating instance came back `exact: False` and is certified now. |
| ✅ | **`certo order` shipped and nobody found it** *(user feedback P1)* | Not a missing feature: a discovery failure, which is worse, because the work was done and did not reach anyone. `asymptotics` and `decays` as aliases, a help line that leads with "does this DECAY in n", `certo commands` putting the question-to-command table in the terminal, and a `lint` note that names the command when a claim divides by a product of symbols. The last has a narrow trigger — two or more symbols at negative exponent — and fires zero times across the shipped examples. |
| ✅ | **A `mixed_design` certificate its own verifier rejected** *(user feedback P0)* | Any model with a `>=` or `==` row: `as_leq_system` renames and negates those, and the equivalence check looked up the original name in a table keyed by the normalised ones. Reported as "all variables discrete"; the empty residual was incidental and the blast radius was every quota model. The mapping now lives in `normalised_rows` and both consumers use it. |
| ✅ | **`--self-check`** *(user feedback P0)* | The real verifier, run over what was just produced: by default for solver-free certificates, opt-in otherwise. A failure exits non-zero and says it is certo's bug. This is the fix for the class — 339 tests missed both defects because every one fed verification a certificate the producer had built, so both sides were wrong in the same place. |
| ✅ | **`parametric` for cover programs** | `sense="min"` with `>=` rows, bounding from BELOW out of a feasible packing, and dual entries that may be polynomials because a cover's dual grows with the instance. Forced by three separate write-ups of one argument, all of which reduce to a symmetrised cover over edge orbits and all of which state the value as a minimum of named closed forms. Two branches of a two-orbit program and one branch of a four-orbit program are now certificates; each is EXACT against an exact rational simplex on its branch (49 and 343 points). The branch conditions come out as the dual's own feasibility. |
| ✅ | **`certo exists`: non-existence, with a refutation** *(P1)* | certo could exhibit a cover and not say "none exists". A paper in the corpus states two obstructions -- divisible graphs with no triangle decomposition -- and the honest artefact for a finite non-existence is a refutation, not an absence. The CDCL and DRAT machinery was already here with no way to reach it from a combinatorial question; this is the bridge. Two answers, both certificates: a model is a SUGGESTION whose parts go through `cover`'s own counting verifier, and a refutation is a DRAT proof checked by unit propagation. Both obstructions verify, and the encoder is not vacuously unsatisfiable -- K7 and K9 come back with decompositions. `--max-parts` found that pairwise "at most k of n" is C(n, k+1): 6,724,520 clauses at 35 candidates and a cap of 6, now 667 with a sequential counter. |
| ✅ | **`certo family`: the largest of many LPs** *(P2)* | From a script in the corpus: enumerate every bipartition, solve one LP each in floats, take the largest, re-solve just that one exactly. That confirms the winner and leaves the claim unmade -- "no bipartition does better" is about all 16,384 of them. Two claims and they are not symmetric: the winner is ATTAINED by a primal and dual that meet, every other item is BOUNDED by a feasible dual, and a dual does not have to be optimal to bound. Nothing stores an LP; each is rebuilt from the spec, so a dual for a different item does not fit and `verify` needs the spec and fails loudly without it. |
| ✅ | **`certo ratio`: a fraction inequality for every n** *(P3)* | `(n-2)/n^2 <= 1/n` for n >= 2 and its cousins, which `prove` settles with an unsat core that re-checks by running a solver again. Clearing the denominators makes it the shift test, and the step that can go wrong -- clearing them -- is the step that gets checked: a denominator not shown positive is a refusal, because a negative one flips the inequality and makes the certificate backwards. `>=` is not offered, being the same claim with the sides swapped. |
| ✅ | **`certo moment`: the first moment, exactly** *(P3)* | The probabilistic method in one line, and the line is a sum of rationals -- usually done in floating point, where `0.9999999` and `1.0000001` have both been written down as "less than one". Two shapes: by event (linearity, no independence needed) and by tail (masses as successive differences, which is the shape the active corpus work states). The existence conclusion is drawn only when the quantity is declared a COUNT, and `verify` re-earns that rather than believing the flag. |
| ✅ | **`certo entry`: the first crossing, and its window** *(P3)* | A proof walks a finite path and stops at the first index past a line. The claim that goes wrong is not "it crosses" but "it had not crossed yet". The prefix is the whole evidence -- nothing past the crossing is part of either claim, so the tail never travels. A step bound buys the WINDOW: the step before was on the near side, so the crossing overshoots by at most delta. |
| ✅ | **Typed transport: a level cannot be crossed silently** *(user feedback P1)* | Two users on two different routes reported the same risk from opposite ends, and one named it exactly: silently passing from a computational object to the paper's object. `compose` already checked the LINK between a lemma and what its certificate closes; what was missing was the OBJECT. A lemma now declares `subject=(kind, id)` and, when that differs from the theorem's, must name a `transport`. An unnamed crossing is REFUSED. certo does not check the map -- that is Lean's part and the boundary this project keeps -- but every crossing is recorded and repeated on each verification, the way bridges are. Declaring no subjects keeps the old behaviour exactly, because a proof that never mentions objects has no levels to cross. |
| ✅ | **Integer arithmetic exports to a theorem `omega` closes** *(user feedback P1)* | The exporter emitted ℤ binders and then handed the goal to `linarith` -- which reasons over ordered FIELDS, so `2x >= 1 implies x >= 1` is beyond it -- or, with no Farkas multipliers, to `sorry`. The second is the common case in combinatorics: a core over the integers exported as a hole even when the statement was DECIDABLE. Linear integer arithmetic is Presburger without quantifiers, `omega` decides it, and it needs no multipliers because it is not searching for a combination. Non-linear integer rows keep the old route, because `omega` does not do variable times variable and a tactic call that fails looks the same to a reader as a gap. And the footer no longer claims a `sorry` the file does not have -- the same lie as a hollow theorem, in the other direction. |
| ✅ | **Propositional logic reaches a DRAT proof** *(user question)* | An asymmetry, once it was named: `prove` DECIDES logic -- disjunctions, implications, quantifiers, booleans mixed with arithmetic -- and its `unsat_core` re-checks by running a solver again. `cases` refutes a CNF with a DRAT proof that re-checks by unit propagation and nothing else, and was reachable only by writing clauses by hand. So anything with an `Or` in it fell back to trusting z3 twice. `to_cnf` is the standard bridge, Tseitin, with the honest parts said out loud: EQUISATISFIABLE and not equivalent, `prove=True` encodes the NEGATION so the verdict reads backwards and the meaning is printed beside it, and the auxiliaries are dropped from the reported witness. Arithmetic inside a formula is REFUSED rather than encoded as an atom -- a CNF whose refutation says nothing about the arithmetic is a wrong answer wearing a proof. Checked against z3 on 60 random formulas for satisfiability, validity, and every model substituted back. |
| ✅ | **The exported theorem is compared against the certificate** *(user feedback P0)* | Nothing compared them. The exporter reads a certificate and writes Lean, and a bug anywhere in that path -- a dropped hypothesis, a sign, a coefficient, a goal rendered from the wrong row -- produces a theorem that COMPILES, looks right, and is not the one the certificate supports. It is the failure this project has already had twice in the other direction: producer and verifier wrong in the same place, agreeing with each other. So the check does not ask the exporter what it meant: it PARSES THE EMITTED TEXT BACK and compares, by a different route. Comparison is semantic, because `-a < 0` and `a > 0` are one row and the exporter writes hypotheses one way and the goal the other on purpose. Four mangles caught, each naming what changed rather than pooling into one boolean. The parser covers only the grammar certo emits and REFUSES the rest, because one that guessed would quietly approve a statement it misread. |
| ✅ | **A hollow Lean export says it is hollow** *(user feedback P0)* | A user exporting an `unsat_core` over a theory certo cannot render got `theorem from_core : True := by trivial` -- compiles, no `sorry`, passes `#print axioms`, states nothing. They declined to put it in their formal chain, which means the safeguard that worked was a person reading carefully. Three changes: a placeholder closes with **`sorry`** rather than `trivial`, so every audit a formalisation project already runs sees it; its name carries `_HOLLOW`, so it is not cited by accident; and `export --check` reports **HOLLOW** and exits non-zero instead of OK, because compiling was never the question. The manifest records the count per file. The route that WORKS -- linear arithmetic over the reals, with real binders and a positively stated goal -- is unmarked, which is what keeps the signal worth anything. |
| ✅ | **A dedup you can check: `labelling=`** *(P2)* | `canonicalize` hands over a FORM and asks to be believed, so "these forty are the same object" was the spec's claim and a certificate could only check that the decomposition's arithmetic held together. `labelling` hands over the PERMUTATION: certo applies it, the result is the canonical form, and the permutation travels so anyone can re-apply it. The claim becomes an arithmetic fact. No cap, because nothing is searched -- the instance that motivated the whole item, a vertex-transitive object certo's own canonical form refuses outright, deduplicates 40 labelled copies to 1 orbit with 40 witnesses, all re-applied on verification. What it still does NOT show -- that two DIFFERENT representatives are different objects -- is a warning rather than an implication. Declaring both is refused: one asks to be believed, the other to be checked. |
| ✅ | **A `SetFamily` id was ambiguous past ten points** | Found by the above, when the witness decoder refused to round-trip. `key` juxtaposed point numbers, which is unambiguous only while a point is one digit: on fifteen points `{1,2,13}` and `{12,13}` both read as `1213`, so two DIFFERENT families shared an id and `from_key` returned a third family. The id is the dedup key and what lands in a certificate. Ids separate their points above ten now and are byte-identical at or below it, which is every id any stored certificate contains. |
| ✅ | **A branch-and-bound tree tied to its own problem** *(user feedback P1)* | The item was compression and a `--fully-checkable` mode. Measuring it found something else first: a node's dual was a whole nested certificate checked ON ITS OWN TERMS, and a dual for a node's relaxation is a valid dual for SOME linear program with nothing saying which node. Exchanging two node certificates verified -- so an expensive subtree could be closed by a cheap one's, and "no design does better", the strongest thing certo says, was not established. Each node's program is DERIVED now, from a root system carried once and the node's own fixings, by the same function the producer uses. The compression and the mode came free: node data fell from ~33,654 bytes to 880 on a 98-row instance, ~150-176 bytes per node on branching trees, and `solver_free` is COMPUTED and comes back true -- every node closes by exact rational arithmetic. Certificates written before the root system existed still verify, with a warning naming exactly what they do not establish. `branch_bound` was also missing from the adversarial suite entirely, which is how the hole survived; it is in it now, and nested sub-certificates are mutated in their payload rather than their schema number. |
| ✅ | **`certo peak`** *(P1)* | The best INTEGER choice for a family of concave quadratics. A write-up completes the square, says the objective is an integer at integer argument, and concludes the maximum is the FLOOR of the continuous peak -- and the floor of a parametric expression is not a polynomial, so there is nothing to expand. Moving the origin to the claimed maximiser makes it polynomial: an integer step changes the objective by `A t^2 + q'(x*) t`, non-positive for every non-zero integer `t` exactly when `A <= q'(x*) <= -A`. Two inequalities, checked by shift, no floor and no residue inside the certificate. The bound is ATTAINED because `x*` is an integer, so a non-integral maximiser is refused rather than assumed integral. Residue classes are separate specs, the way branches are. Matches brute force on three classes for every n < 180. |
| ✅ | **`parametric` past the box: `region=`** *(P1)* | The shift proves non-negativity on a ray, so a certificate covers a BOX -- and a branch cut out by `q d + d r = d(d-1) + r(r-1)` is not one. Side conditions are now DECLARED: `g(p) >= 0` enters the certificate's scope, nothing proves it, and `verify` warns separately and loudly because a polynomial condition reads like something proved. certo finds the MULTIPLIERS, since that search is a linear program -- polynomial ones, because the multiplier of a condition is `r/2` as often as it is a number. A trichotomy that two boxes covered 68% of now takes five certificates and covers 1170 of 1170 measured points, every bound exact against the simplex. |
| ✅ | **The exact simplex could return a `y` violating its own constraints** | Found by the above, silently. Dependent rows -- one per monomial of a polynomial identity, so dependent by construction -- end phase 1 with an artificial basic at level zero, and the transition renamed it to variable index 0, which is a real variable. That states a false tableau; the answer came back wrong or as a spurious "unbounded". Artificials are now pivoted out on a real column, and a row with no real column left is dropped as redundant. Not a soundness hole anywhere it was used -- every caller re-checks what the simplex hands back -- but it was losing answers and would have gone on doing it. |
| ✅ | **A named square is a legitimate hint** | `farkas --nonlinear` searches a fixed square set -- each hypothesis squared, `x²`, `(x-y)²` -- and a margin estimate that completes the square as `(2s-q)²` or `12(u-v/4)²` is outside it, so the heuristic missed and said so. It did not need a feature: a square is a tautology, so assuming one adds a row without adding an assumption. Three comparisons from one write-up now close solver-free, with multipliers `1/16` and `1/48` that are the source's own arithmetic read back. Documented, because the mechanism existed and nobody could have guessed it. |
| ✅ | **A `>=` load priced at zero** *(user feedback P1)* | Same root cause, other consumer. Now `d(optimum)/d(bound)`, summed over the normalised rows with their signs — negative for a binding `>=`, because raising a floor costs you — with the direction stated and the source rows in the payload. |
| ✅ | **Minimisation in branch and bound** *(user feedback P1)* | Refusing it left the user negating by hand and their certificate describing a formulation nobody posed. The tree still searches `max -c.x` because that is what happens, and the payload records both what was searched and what was asked. |
| ✅ | **`--wall-timeout-ms`, and a stopped search that reports** *(user feedback P1)* | `--timeout-ms` bounds a solver call, not the search. On expiry by clock or nodes: best design, best bound, gap, node count, and no certificate of optimality. A search that runs out always knew all four. |
| ✅ | **A solver's stop reason, in words** *(user feedback)* | z3 says "canceled", which reads as if the user cancelled it. Now named as the limit it was, with the lever to raise and a hint about dividing out a common power — which in the report turned a 10 s timeout into 12 ms. |
| ✅ | **`certo cover`: exact covers and clique partitions** | Every element of a universe in exactly one part, checked by counting; with `cliques=True` the parts are vertex sets and each is refused unless every pair among them is an edge. Three failures reported as three different things, because a non-clique part is a statement about the graph and a doubled edge is one about the cover. An upper bound with an artefact attached: pair it with `opt`'s exact dual for the lower one. |
| ✅ | **Local loads in a packing certificate** *(user feedback P1)* | Named regions with bounds, declared apart from resource capacities because a capacity is part of the encoding and a load is part of the argument. They become rows, so the dual prices them: a binding region reports its shadow price, a slack one reports that it is not what constrains the answer. The certificate carries each load's coefficients so `verify` recomputes the achieved value rather than believing it. Built to the shape of the corpus model, `within-A load <= N_A`. |
| ✅ | **`certo parametric`: a bound for every parameter value** *(P1)* | Weak duality, symbolically: `y >= 0` with `A(p)ᵀy >= c(p)` bounds `opt(p)` for every `p` at once, and each dual-feasibility row is certified on a ray by substituting `p = p0 + u` and reading the coefficient signs. Turns "checked for p = 5..12" into "holds for every p >= 10". Built against the corpus instance whose duals are piecewise constant with thresholds; on a reproduced slice one dual read at p = 10 gives the EXACT optimum at 10, 11, 15 and 30. The shift is sufficient and not necessary, so a failure emits no certificate and says the route failed rather than that the bound is false. |
| ✅ | **`certo eliminate`: resultants** *(P2)* | Removes a variable from two polynomials and returns the condition on the rest, with the Bezout identity `Res = A*f + B*g` attached — so checking a determinant over a polynomial ring is expanding two products. Bareiss throughout, every division verified exact rather than assumed. A non-zero constant resultant refutes a common root over any field; `Res = 0` is necessary always and sufficient only over an algebraically closed field with a non-vanishing leading coefficient, which `verify` repeats and qualifies. |
| ✅ | **Derive the LP dual instead of reconstructing it** *(user feedback P1)* | 3 of 56 exact LPs needed the rational pair injected by hand, all on symmetric solutions: on a degenerate vertex CBC returns an arbitrary one of many optimal duals and rounding it need not be dual-feasible. Complementary slackness determines the dual from the primal in exact `Fraction`, and where it underdetermines it the choices ARE the optimal duals. Certifies now with no usable dual from the solver at all. The second cause this item claimed — a coupled denominator ladder — was **measured and refuted**; that pass was dropped rather than shipped. |
| ✅ | **A solver-free certificate for linear-arithmetic proofs** *(user feedback P1)* | An `unsat_core` meant re-running z3 to check it. Now the Farkas search runs over the core's own rows and the multipliers travel as optional fields: verification expands the combination in `Fraction` and reads off the contradiction. Floats in the search do not compromise it — the LP finds the vector, exact arithmetic accepts or rejects it. Fell out of it: the Lean export emits `linarith` instead of `sorry`, so the two gaps this user reported separately had one fix. |
| ✅ | **`check --hypotheses-only`** *(user feedback)* | Asking "is my regime non-empty?" by claiming `False` returned UNSATISFIABLE on regimes that have models -- correct, and the opposite of what it reads as. The flag asks it directly: a solver-free model when the regime is inhabited, the minimal clash when it is not. A constant claim is named in `check` and in `lint` for whoever does not know the flag exists. |
| ✅ | **`export --lean` for `unsat_core`** *(user feedback)* | The kind the most-used command produces used to be refused. Linear arithmetic gets real binders, hypotheses and a positively stated goal with `sorry`; a vacuous core becomes `h₁ → … → False`, the emptiness of the regime stated in Lean. The sort is read off the formulas. Everything else carries the SMT-LIB2 and says so. |
| ✅ | **`--check` had never compiled anything** | A relative path against a cwd inside the Lean project; lake reported "no such file or directory" and it surfaced as a compile failure. Found because the lean CI job, fixed in the same round, finally got far enough to run it. |
| ✅ | **A fractional "integral point" verified as valid** *(user feedback)* | `_verify_lp_dual` checked the declared integral point for feasibility and for matching its objective, and never that the values were integers: `x = 3/2` passed. Now checked per DECLARED KIND, so a mixed problem's continuous weights stay fractional on purpose. `mixed_design` had it right all along; `lp_dual`, which `opt` produces, did not. |
| ✅ | **`certo status`** *(P1)* | Reads a directory of certificates and reports where the work stands: RESULTS (nothing else builds on them), STILL OWED (every bridge and unclaimed optimality, including ones three levels down), HOLLOW (vacuous proofs with their clash named, sweeps that certified nothing), STALE (the spec moved under the certificate). Emits no certificate of its own: it makes no claim. |
| ✅ | **`certo lint`** *(P1)* | The dry pass before the compute. Contradictory hypotheses found BEFORE the proof rather than after a valid-and-empty win; an inductive step that starts after the base cases end, caught by comparing two integers instead of discharging six sweeps; a `bool` predicate named as `reproducible` in advance. Counts a domain without materialising it and reads a graph family's size from a table. |
| ✅ | **Deep Lean export** *(user feedback P1)* | A Farkas certificate becomes a runnable `linarith`/`nlinarith` example carrying the `sq_nonneg` hints it used; a `compose` proof becomes a skeleton with `sorry` on exactly the bridges; a sweep becomes a `List` Lean can `decide`. Plus `--manifest` (hashes) and `--check`, which compiles. All three verified against Mathlib v4.28.0. |

---

## Decisions taken

Recorded so they do not get re-litigated, and so the priorities below can be
read as following from something.

| | Decision | Consequence |
|---|---|---|
| **PyPI** | Not yet. Revisit at a stable version. | Installation stays `git clone` + `pip install -e`. No release workflow to maintain, and payload changes stay cheap until then. |
| **Certificate schema** | **Frozen from 0.4**, once that version closes. | Until 0.4 ships, payload fields may still move (readers keep accepting the old shapes). From 0.4 a payload change needs a schema bump and a migration note. Anything produced for a paper before then should be re-run after 0.4. |
| **Lean** | Deeper Lean is **not the focus**. certo helps establish the mathematics; a separate tool generates and compiles the Lean. | P1 "Lean statements, not only structure" drops to P3. What stays is the export as it is -- data, `linarith` examples with their hints, and the theorem/bridge boundary -- because those are the *mathematical* content, not a formalisation. Revisit if the handoff turns out to lose something. |
| **Admin rights** | Not available on this machine, and not coming. | `cadical` / `kissat` moves from Blocked to Closed. The built-in CDCL is the answer: correct, and slow. `certo doctor` says so in one line. |
| **Real instances** | Supplied: the Erdős 81 working corpus. | See below -- one instance has already been used, and it found a bug. |

---

## What the first real instance found

The research corpus is dominated by one computational shape: **51 of 131
scripts build an LP or ILP over a family of lists with exact rationals.** A
"list" is a set of colours; the packing puts a pair `{a,b}` from list `j` into
a solution, each pair usable once globally and each `(list, colour)` once. That
is a `PackingSpec` exactly, and the quantities computed are the integral
optimum `ν` and the fractional `μ*` -- the integrality gap.

Rebuilt as a certo packing, the canonical core instance reproduces their
numbers: `ν = 7`, `μ* = 15/2`. Two differences worth having: `μ*` comes out as
an **exact rational** rather than the float `7.5`, and the dual verifies
without a solver, reading as a load per resource.

**And it found a bug.** `opt` on an ILP reported the relaxation's value as
`meta["objective"]` -- so `ν = 7` came back as `15/2`. The detail text was
half-honest about it; every programmatic reader was not. Fixed in a way that
is better than the original intent: an ILP now certifies **both sides** -- a
feasible integral point, rounded and checked exactly, as the achievable value,
and the exact dual as the bound. When they coincide the integer optimum is
certified exactly; when they do not, the gap is reported rather than hidden.

That is the argument for real instances in one paragraph, and it is why the
items below still say "build against a real problem".


### A note on the README

Rewritten twice on 2026-09-17, for two different reasons, and the second one
is the interesting one.

The first pass replaced an abstract opening with three real sessions. The
second replaced those, because all three showed the SAME PHASE of the tool:
catch a false claim, catch a vacuous one, hand over an artefact. The tagline
said "certo tries to break it", which is a mode and not a summary. Nothing on
the front page showed it FINDING anything, measuring how much a thing fails
rather than whether, or collapsing ninety counterexamples into the two objects
they actually are.

It now leads with **the arc** — find, break, measure, reduce, establish,
assemble — as a table, and then one session per phase. The through-line is the
last column of that table rather than the verb in the tagline: every phase
returns something re-checkable, and that is the claim worth making.

Worth recording as a lesson rather than a changelog entry: a front page
written by whoever built the tool will over-represent whatever they worked on
most recently. Three sessions all drawn from the honesty layer looked like
coverage and were not.

Every block of output on both front pages is copied from a run. Two were wrong
when first checked, including one claiming a `branch_bound` certificate
verifies *without* a solver. It does not.


## Closed

**`cadical` / `kissat`.** No Windows wheel, no binaries in cadical's releases,
kissat on macOS and Linux only, no C++ compiler, and WSL needs administrator
rights that are not available on this machine and are not coming. Decided
rather than blocked: the built-in CDCL is the answer. It is correct and it is
slow, `certo doctor` says so in one line, and CI now runs the suite on Linux
where an external solver could be installed if anyone ever needs one.

---

## Won't do

**Chasing an adjacent library's coverage.** Measured 2026-09-17: 1175 modules
against 28 commands, with whole areas — topology, probability, analysis,
groups, lattices, finite fields — where certo has no analogue and no reason to
grow one. Trying would lose, and the attempt would produce a thousand commands
with no certificate.

The rule that falls out, and that has already been applied twice: **do not
build a search here because a certificate needs one.** `cover` takes a
partition, `parametric` takes a dual, `farkas` finds its own multipliers only
because that search was an LP already in the box. What another tool computes,
certo certifies and archives — and certo has no 32-variable cap because it is
not a service with a request quota.

One correction to how that is applied, from the same reading: **look at the
catalogue before building in the overlap.** `cover` would have shipped anyway,
since the persisted certificate and the pairing with a lower bound are the
point, but the plain check already existed and knowing that would have started
the work at the pairing, which is the half that fixed a real misreading.

---

The one long-standing entry that used to be here was flag algebras and
SDP, refused on the grounds that floating point cannot produce a citable
certificate. `certo sos` (0.3.0) shows that argument was wrong: the same
round-and-re-verify-exactly move that `opt` has always used applies, and the
floats stay in the search. Flag algebras are now a P2 item rather than a
refusal — still wanting 2–3 real packing instances before anyone builds it,
but for reasons of demand, not of principle.

---

## Release process

Releases are authorised by the project owner, one at a time. Work lands in
local commits; **pushing to the public repository is not automatic** and is
asked for each time. Each release bumps the version, writes its section of
[CHANGELOG.md](CHANGELOG.md), and is tagged.

Current: **0.6.1**. The certificate schema has been **frozen** since 0.4.0 and `SCHEMA_VERSION` is still 4: everything since has been an optional field or a command that emits no certificate.

Frozen means an existing payload's fields do not move: no renames, no
removals, no changes of meaning. What stays allowed, permanently:

* a NEW certificate kind — additive, breaks nothing;
* an OPTIONAL field on an existing payload that older readers may ignore.

Anything else needs a `SCHEMA_VERSION` bump and a migration note. Every item
left below is of the first kind, which is why none of them is urgent.
