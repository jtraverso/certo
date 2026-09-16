# Changelog

Notable changes per release. Dates are ISO. This project uses semantic
versioning; while the major is 0, a minor bump may change a certificate
payload — each such change says so and what still reads the old shape.

## [Unreleased]

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
