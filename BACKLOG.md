# certo — backlog

One file, so nothing is tracked in three places. Priorities are **P0** (blocks
a release), **P1** (the next thing worth doing), **P2** (real value, more
work), **P3** (worth keeping, nobody is waiting), **Blocked**, **Won't do**.

Items marked *(user feedback)* come from an external user's report after real
use; those carry more weight than anything on this list that was invented in
the abstract.

Last updated: 2026-09-17. Four items that were waiting for a real instance now have one, located in the corpus and measured rather than assumed — see each item.

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
| ✅ | **`cover --optimize` and `CoverSpec.to_lp`** *(user feedback P1)* | Three numbers with their statuses attached: your cover as a certified upper bound, the relaxation as an exact rational lower bound, and the integer optimum when branch and bound finishes. `candidates` required and refused rather than guessed, because minimal-relative-to-what is a modelling fact. Built for a misreading: a valid cover reported as an optimal one. |
| ✅ | **An exact rational simplex** | Surfaced by the above. Deriving a degenerate dual by choosing which tight rows carry weight is C(49,7) on a realistic exact cover, about 10^8 — right for a handful of tight rows and hopeless past it. Past that the dual is solved outright, two-phase, Bland's rule, no floats. The motivating instance came back `exact: False` and is certified now. |
| ✅ | **`certo order` shipped and nobody found it** *(user feedback P1)* | Not a missing feature: a discovery failure, which is worse, because the work was done and did not reach anyone. `asymptotics` and `decays` as aliases, a help line that leads with "does this DECAY in n", `certo commands` putting the question-to-command table in the terminal, and a `lint` note that names the command when a claim divides by a product of symbols. The last has a narrow trigger — two or more symbols at negative exponent — and fires zero times across the shipped examples. |
| ✅ | **A `mixed_design` certificate its own verifier rejected** *(user feedback P0)* | Any model with a `>=` or `==` row: `as_leq_system` renames and negates those, and the equivalence check looked up the original name in a table keyed by the normalised ones. Reported as "all variables discrete"; the empty residual was incidental and the blast radius was every quota model. The mapping now lives in `normalised_rows` and both consumers use it. |
| ✅ | **`--self-check`** *(user feedback P0)* | The real verifier, run over what was just produced: by default for solver-free certificates, opt-in otherwise. A failure exits non-zero and says it is certo's bug. This is the fix for the class — 339 tests missed both defects because every one fed verification a certificate the producer had built, so both sides were wrong in the same place. |
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


## P1 — next

Everything here comes from the 0.6 field report, and the two P0s it named are
already fixed.

### 1. `verify --spec` and `certo --version` *(user feedback)*

The certificate already stores `spec_path` and `spec_sha256`, and `status`
already reports staleness. What is missing is the direct form:

    certo verify cert.json --spec spec.py     # fail if the hash differs

so nobody verifies an old certificate believing it describes the file in front
of them. And `certo --version` currently reads as a missing subcommand; it
should print the version, the commit when available, and the maximum
certificate schema.

### 2. A compact, solver-free branch-and-bound certificate *(user feedback)*

63 nodes cost 842 KB, and the certificate is `solver_free: false`. Both are
honest and both are worth improving:

* document exactly what needs a solver during `verify`, and what each leaf
  stores;
* inherit bounds and decisions from the parent instead of repeating the node's
  whole state, which on a mid-sized tree is most of the bytes;
* a `--fully-checkable` mode that stores an exact dual or Farkas ray at every
  leaf, larger but solver-free, for archival.

---

### A note on adjacent tools

Checked 2026-09-17 against a library of atomic mathematical tools a user runs
alongside certo (`jacobian`, v0.21.0). The division of labour is clean and
worth stating so neither side gets rebuilt here by accident:

**That library COMPUTES.** Minimum generalized exact covers, full graph
automorphism groups, exact enclosures, algebraic number arithmetic — a large
surface of "give me the answer to this".

**certo CERTIFIES.** It takes an answer, from anywhere, and produces an
artefact that re-checks without the thing that produced it. `cover` came
directly from that split: the audit it was built for sends a graph and a
partition to a service for checking, and a certificate does the same job
without the service needing to exist later.

Two consequences worth remembering:

* Do not build a search here because a certificate needs one. `cover` takes a
  partition; `parametric` takes a dual; `farkas` finds its own multipliers
  only because the search is an LP that was already in the box.
* That library computes **full automorphism groups**, which is exactly the
  missing ingredient in P2 #5. If that item is ever built, it should be
  against a group somebody else computed, not a reimplementation of nauty.


## P2 — high value, more work

### 2. Flag algebras, now that the objection is gone

`sos` established the pattern: numeric search, rational reconstruction, exact
re-verification. A flag-algebra bound is the same shape one level up.

**The instances exist**: the corpus has over a hundred scripts solving
LP/ILP triangle packings, several of them asking whether an invariant stays
bounded or grows with `n` — which is the question a flag-algebra bound
answers. More than the 2–3 this item was waiting for.

### 3. `SetFamily` canonicalisation for matchings and coloured hypergraphs
*(user feedback)*

**The instance is confirmed**: the corpus enumerates every matching of a
complete graph on a vertex set and indexes LP columns by them, which is
precisely the structure below.

`canonical()` quotients by relabelling the ground set. A family of MATCHINGS
has more structure than that — the blocks partition, and a factorisation of
K_{s+1} into perfect matchings has the matchings themselves permutable — and a
coloured hypergraph has colours that may or may not be permutable. Both would
benefit from a canonical form that knows it.

Worth building against the real instance rather than in the abstract: which
symmetries are genuine depends on the problem, and guessing wrong merges two
orbits, which nothing downstream would notice.

### 4. Combinatorial types beyond set families

`SetFamily` covers hypergraphs, designs, codes and mask systems, because they
are all one shape. What it does not cover: ordered structures (sequences,
words, permutation patterns) and edge-coloured or directed objects. Worth
adding when a real problem asks, not before — the value of a native type is
the boilerplate it removes, and boilerplate nobody is writing is not a cost.

### 5. A canonical form that scales past the cap

`SetFamily.canonical()` refuses above 200,000 candidate relabellings.

**Measured, 2026-09-17, and it bites far earlier than this item claimed.** A
1-factorisation of K6 — 15 points, 5 blocks, which is exactly the matchings
structure of item 3 — hits the cap. So does K9 as a family, and all triples on
9 points. Below the cap it is already slow: all triples on 8 points takes 13
seconds.

**And the proposed fix was tried and does not work.** This item said "the fix
is individualisation-refinement, the way nauty does it". Implemented and
verified correct — 400 random families agreed exactly with the exhaustive
reference, and 120 families relabelled twelve ways each gave one form — and
then measured:

| | individualisation-refinement | exhaustive |
|---|---|---|
| K7 as a family | 157 ms | 89 ms |
| K8 as a family | 1809 ms | 2041 ms |
| K6 1-factorisation | still refuses | still refuses |

Refinement splits a cell only when its points differ by an isomorphism
invariant. A vertex-transitive object has none by definition, so refinement
does nothing and the search degenerates to the brute force it was meant to
replace — on precisely the objects that hit the cap.

**What the fix actually is**: automorphism pruning. When two branches of the
search produce the same form, the permutation between them is an
automorphism, and every branch related to an explored one by a known
automorphism can be skipped. That is the content of nauty, and refinement is
the cheap part around it. Reverted rather than shipped, because a second
canonical routine that must stay in agreement with the first is a maintenance
cost, and this one bought nothing where it mattered.

---

## P3 — keep, nobody waiting

| | What | Why it is down here |
|---|---|---|
| | Lean statements for `proof` and the sweep kinds | Half done since 0.5.1: `unsat_core` emits real binders, hypotheses and a positively stated goal, which shows the linear-arithmetic case IS mechanical. `proof_to_lean` still emits `theorem name : True` with the statement in a comment, and graphs and set families are not mechanical at all. **Deliberately parked**: Lean generation is another tool's job. |
| | `certo qe` | Quantifier elimination to **derive** the optimal constant instead of bracketing it with `bisect`. Genuinely distinctive; no demand yet. |
| | Cutting-plane certificates | Gomory–Chvátal for **integer** infeasibility, not just the LP relaxation. Relevant to packing bounds. |
| | Exact first moment | `E[X] < 1` in `Fraction` ⇒ existence. Small, and common in the probabilistic method. |
| | `certo repro` | Bundle spec + certificates + versions + hashes for a paper appendix. Partly absorbed by the Lean manifest in P1 #3. |

---

## Closed

**`cadical` / `kissat`.** No Windows wheel, no binaries in cadical's releases,
kissat on macOS and Linux only, no C++ compiler, and WSL needs administrator
rights that are not available on this machine and are not coming. Decided
rather than blocked: the built-in CDCL is the answer. It is correct and it is
slow, `certo doctor` says so in one line, and CI now runs the suite on Linux
where an external solver could be installed if anyone ever needs one.

---

## Won't do

**Nothing, currently.** The one long-standing entry here was flag algebras and
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
