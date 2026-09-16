# certo — backlog

One file, so nothing is tracked in three places. Priorities are **P0** (blocks
a release), **P1** (the next thing worth doing), **P2** (real value, more
work), **P3** (worth keeping, nobody is waiting), **Blocked**, **Won't do**.

Items marked *(user feedback)* come from an external user's report after real
use; those carry more weight than anything on this list that was invented in
the abstract.

Last updated: 2026-09-16 (after 0.3.0).

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
| ✅ | **`certo number`** *(0.3.0)* | Pratt primality trees and factorisations. Checked by modular exponentiation alone. |
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


## P1 — next

### 1. `--by-orbit` for graph sweeps

It is on `DomainSpec` only. Graph sweeps take `canonicalize` but still
evaluate every graph; the same spot-checked inference applies.

### 2. Packings, from the shape the corpus actually uses

The `(list, pair)` packing above is not one instance, it is the shape 51
scripts share. A `PackingSpec.lists(L)` constructor, the integrality gap
`μ* − ν` reported as one number with both sides certified, and the family
carried as a `SetFamily` so `canonicalize="auto"` gives the orbits -- that
turns a recurring fifteen-line rebuild into three lines, on the problem the
tool is actually being used for.

### 3. Close the loop on `opt --by-type` for gaps

`--by-type` answers "does mixing buy anything". The corpus asks a neighbouring
question constantly: "how far is `ν` from `μ*`, and which resources are tight
in the dual". The dual is already exact; what is missing is reporting it as a
gap rather than as two runs someone has to subtract.

---

## P2 — high value, more work

### 4. Flag algebras, now that the objection is gone

`sos` established the pattern: numeric search, rational reconstruction, exact
re-verification. A flag-algebra bound is the same shape one level up. Wanted:
2–3 real packing instances to build against, so the interface is designed
around a problem rather than around the method.

### 5. Resultants and elimination

`ideal` covers membership. Elimination — "remove `t` from these equations and
tell me the condition on the parameters" — is the algebraic route to the same
place `qe` would reach, and it is exact. The certificate wants the Bézout
identity `Res(f,g) = Af + Bg`, which is verifiable by expansion exactly like
the cofactors.

### 6. Combinatorial types beyond set families

`SetFamily` covers hypergraphs, designs, codes and mask systems, because they
are all one shape. What it does not cover: ordered structures (sequences,
words, permutation patterns) and edge-coloured or directed objects. Worth
adding when a real problem asks, not before — the value of a native type is
the boilerplate it removes, and boilerplate nobody is writing is not a cost.

### 7. A canonical form that scales past the cap

`SetFamily.canonical()` refuses above 200,000 candidate relabellings, which a
very regular family on more than ~10 points will hit. The fix is individual-
isation-refinement, the way nauty does it. Only worth building against a real
instance that hits the cap.

---

## P3 — keep, nobody waiting

| | What | Why it is down here |
|---|---|---|
| | Lean statements, not only structure | `proof_to_lean` emits `theorem name : True` with the statement in a comment. Translating linear-arithmetic statements is mechanical; graphs and set families are not. **Deliberately parked**: Lean generation is another tool's job. |
| | `certo qe` | Quantifier elimination to **derive** the optimal constant instead of bracketing it with `bisect`. Genuinely distinctive; no demand yet. |
| | Cutting-plane certificates | Gomory–Chvátal for **integer** infeasibility, not just the LP relaxation. Relevant to packing bounds. |
| | Exact first moment | `E[X] < 1` in `Fraction` ⇒ existence. Small, and common in the probabilistic method. |
| | `certo repro` | Bundle spec + certificates + versions + hashes for a paper appendix. Partly absorbed by the Lean manifest in P1 #3. |
| | A full worked example | The published examples cover each command; none walks one problem from exploration to Lean. `examples/compose_proof.py` also needs two certificates that are deliberately not committed (they are output) — a `make examples` would remove that friction. |
| | Repository topics | `theorem-proving`, `smt`, `z3`, `lean`, `mcp`. **Needs authorisation.** |

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

Current: **0.3.0**. Next: **0.4**, which also freezes the certificate schema.
