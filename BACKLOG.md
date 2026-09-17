# certo — backlog

One file, so nothing is tracked in three places. Priorities are **P0** (blocks
a release), **P1** (the next thing worth doing), **P2** (real value, more
work), **P3** (worth keeping, nobody is waiting), **Blocked**, **Won't do**.

Items marked *(user feedback)* come from an external user's report after real
use; those carry more weight than anything on this list that was invented in
the abstract.

Last updated: 2026-09-17. P1 is down to the two items that want a real instance; everything else from the user reports has landed.

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

Restructured 2026-09-17 after the observation that the opening was abstract.
It now leads with three real sessions — a false claim refuted in 4 ms with its
counterexample, a vacuous proof caught, an optimum proved with every leaf
certified — each one runnable from `examples/`, and every block of output
copied from an actual run rather than written from memory. Two blocks were
wrong when checked, including one that claimed a `branch_bound` certificate
verified *without* a solver. It does not.

After that: **Start here**, a five-row router by who you are, and **Which
command answers which question**, a table keyed on the question in the
reader's own words rather than on the command name. That second table is the
one an LLM needs, and it turns out a newcomer needs the same thing.


## P1 — next

### 1. Local loads as part of a packing certificate *(user feedback)*

The user is building a resource-packing / hypergraph-matching layer AROUND
certo: generate the physical rows automatically, and ask for "preserve these
local loads" as part of what gets certified. `PackingSpec.lists` covers the
first half. The second is new: pin named local loads and have the certificate
record that the solution holds them.

**Wants their instance before it is designed.** Which loads are worth pinning,
and whether they are equalities or bounds, is a property of the problem; the
same argument as P2 #7, and guessing produced a bad check once already.

### 2. Parametric certificates — the jump from finite case to theorem

`order` is the first step of this and it shipped. The rest: an LP dual given
as rational FUNCTIONS of `s`, whose feasibility `A^T y >= c` becomes polynomial
inequalities in `s`, certified for all `s >= s0` by `sos` or
`farkas --nonlinear` — both of which already exist.

That turns "checked for s = 7..20" into "holds for every s >= 7", which is the
one thing the tool keeps saying it cannot do. Wanted: an instance where the
dual weights follow a visible pattern in `s`.

---

## P2 — high value, more work

### 5. Flag algebras, now that the objection is gone

`sos` established the pattern: numeric search, rational reconstruction, exact
re-verification. A flag-algebra bound is the same shape one level up. Wanted:
2–3 real packing instances to build against, so the interface is designed
around a problem rather than around the method.

### 6. Resultants and elimination

`ideal` covers membership. Elimination — "remove `t` from these equations and
tell me the condition on the parameters" — is the algebraic route to the same
place `qe` would reach, and it is exact. The certificate wants the Bézout
identity `Res(f,g) = Af + Bg`, which is verifiable by expansion exactly like
the cofactors.

### 7. `SetFamily` canonicalisation for matchings and coloured hypergraphs
*(user feedback)*

`canonical()` quotients by relabelling the ground set. A family of MATCHINGS
has more structure than that — the blocks partition, and a factorisation of
K_{s+1} into perfect matchings has the matchings themselves permutable — and a
coloured hypergraph has colours that may or may not be permutable. Both would
benefit from a canonical form that knows it.

Worth building against the real instance rather than in the abstract: which
symmetries are genuine depends on the problem, and guessing wrong merges two
orbits, which nothing downstream would notice.

### 8. Combinatorial types beyond set families

`SetFamily` covers hypergraphs, designs, codes and mask systems, because they
are all one shape. What it does not cover: ordered structures (sequences,
words, permutation patterns) and edge-coloured or directed objects. Worth
adding when a real problem asks, not before — the value of a native type is
the boilerplate it removes, and boilerplate nobody is writing is not a cost.

### 9. A canonical form that scales past the cap

`SetFamily.canonical()` refuses above 200,000 candidate relabellings, which a
very regular family on more than ~10 points will hit. The fix is individual-
isation-refinement, the way nauty does it. Only worth building against a real
instance that hits the cap.

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

Current: **0.5.2**. The certificate schema has been **frozen** since 0.4.0 and `SCHEMA_VERSION` is still 4: everything since has been an optional field or a command that emits no certificate.

Frozen means an existing payload's fields do not move: no renames, no
removals, no changes of meaning. What stays allowed, permanently:

* a NEW certificate kind — additive, breaks nothing;
* an OPTIONAL field on an existing payload that older readers may ignore.

Anything else needs a `SCHEMA_VERSION` bump and a migration note. Every item
left below is of the first kind, which is why none of them is urgent.
